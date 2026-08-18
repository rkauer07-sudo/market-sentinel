from __future__ import annotations

import argparse
import asyncio
import base64
import hmac
import logging
import os
import time
from statistics import fmean
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from .app import Sentinel
from .analysis import pivots
from .config import load_settings
from .models import Candle


class MemoryLogHandler(logging.Handler):
    def __init__(self, records: deque[str]):
        super().__init__(); self.records = records

    def emit(self, record):
        self.records.append(self.format(record))


class Dashboard:
    def __init__(self, config_path: str):
        self.settings = load_settings(config_path)
        self.sentinel = Sentinel(self.settings)
        self.task: asyncio.Task | None = None
        self.scan_lock = asyncio.Lock()
        self.last_opportunities = []
        self.last_error: str | None = None
        self.price_cache: dict[str, dict] = {}
        self.price_cache_at = 0.0
        self.logs: deque[str] = deque(maxlen=400)
        handler = MemoryLogHandler(self.logs)
        handler.setFormatter(logging.Formatter("%(asctime)s · %(levelname)s · %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(handler)

    async def scan(self):
        if self.scan_lock.locked(): raise HTTPException(409, "Já existe uma varredura em andamento")
        async with self.scan_lock:
            self.last_error = None
            try:
                self.last_opportunities = await self.sentinel.scan_once()
                return self.last_opportunities
            except Exception as exc:
                self.last_error = str(exc)
                logging.getLogger(__name__).exception("Falha na varredura manual")
                raise HTTPException(502, str(exc)) from exc

    async def loop(self):
        interval = int(self.settings.runtime["scan_interval_seconds"])
        while True:
            cycle_started = time.monotonic()
            try:
                async with self.scan_lock:
                    self.last_opportunities = await self.sentinel.scan_once()
                    self.last_error = None
            except asyncio.CancelledError: raise
            except Exception as exc:
                self.last_error = str(exc); logging.getLogger(__name__).exception("Falha no ciclo automático")
            await asyncio.sleep(max(0, interval - (time.monotonic() - cycle_started)))

    def start(self):
        if self.task and not self.task.done(): return False
        self.task = asyncio.create_task(self.loop(), name="sentinel-monitor")
        return True

    async def stop(self):
        if not self.task or self.task.done(): return False
        self.task.cancel()
        try: await self.task
        except asyncio.CancelledError: pass
        return True

    @property
    def running(self): return bool(self.task and not self.task.done())


def serialize_opportunity(op):
    return {
        "venue": op.market.venue, "symbol": op.market.symbol, "asset_class": op.market.asset_class.value,
        "market_type": op.market.market_type, "timeframe": op.timeframe, "direction": op.direction,
        "setup": op.setup, "entry": op.entry, "stop": op.stop, "target1": op.target1,
        "target2": op.target2, "target3": op.target3, "target4": op.target4,
        "target5": op.target5, "targets": op.targets,
        "risk_reward": op.risk_reward, "score": op.score,
        "reasons": op.reasons, "risks": op.risks, "candle_timestamp": op.candle_timestamp,
        "score_breakdown": op.score_breakdown, "confirmation_count": op.confirmation_count,
    }


def serialize_candidate(candidate):
    return {
        "venue": candidate.market.venue, "symbol": candidate.market.symbol,
        "asset_class": candidate.market.asset_class.value, "timeframe": candidate.timeframe,
        "direction": candidate.direction, "scenario": candidate.scenario,
        "trigger_price": candidate.trigger_price, "invalidation_price": candidate.invalidation_price,
        "target": candidate.target, "readiness": candidate.readiness,
        "conditions": candidate.conditions, "risks": candidate.risks,
        "candle_timestamp": candidate.candle_timestamp,
        "technical_context": candidate.technical_context, "risk_reward": candidate.risk_reward,
    }


def rolling_sma(values: list[float], period: int) -> list[float | None]:
    result = []
    for index in range(len(values)):
        result.append(fmean(values[index-period+1:index+1]) if index + 1 >= period else None)
    return result


def create_app(config_path: str = "config.yaml") -> FastAPI:
    dashboard = Dashboard(config_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if os.getenv("AUTOSTART", "false").lower() in {"1", "true", "yes", "on"}:
            dashboard.start()
        yield
        await dashboard.stop(); await dashboard.sentinel.close()

    app = FastAPI(title="Market Sentinel", version="0.1.0", lifespan=lifespan)
    app.state.dashboard = dashboard
    static_dir = Path(__file__).parent / "static"
    static = static_dir / "index.html"
    auth_user = os.getenv("DASHBOARD_USER")
    auth_password = os.getenv("DASHBOARD_PASSWORD")

    @app.middleware("http")
    async def basic_auth(request: Request, call_next):
        if request.url.path.startswith("/api/") and not dashboard.running:
            # sqlite3 connections are thread-bound by default. Keep refresh in
            # the request thread so closing/reopening the shared connection is safe.
            dashboard.sentinel.store.sync_from_remote()
        if request.url.path == "/health" or not (auth_user and auth_password):
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        try:
            scheme, encoded = header.split(" ", 1)
            supplied_user, supplied_password = base64.b64decode(encoded).decode().split(":", 1)
        except (ValueError, UnicodeDecodeError):
            scheme = supplied_user = supplied_password = ""
        valid = scheme.lower() == "basic" and hmac.compare_digest(supplied_user, auth_user) and \
            hmac.compare_digest(supplied_password, auth_password)
        if not valid:
            return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Market Sentinel"'})
        return await call_next(request)

    @app.get("/health", include_in_schema=False)
    async def health(): return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def index(): return FileResponse(static)

    @app.get("/static/i18n-full.js", include_in_schema=False)
    async def dashboard_i18n():
        return FileResponse(static_dir / "i18n-full.js", media_type="application/javascript")

    @app.get("/api/status")
    async def status():
        classes = {}
        for _, market in dashboard.sentinel.markets:
            classes[market.asset_class.value] = classes.get(market.asset_class.value, 0) + 1
        lifecycle = dashboard.sentinel.store.signal_stats()
        scheduled = bool(not dashboard.running and dashboard.sentinel.store.remote_url
                         and dashboard.sentinel.store.remote_key and not dashboard.sentinel.store.remote_error)
        return {"running": dashboard.running, "scanning": dashboard.scan_lock.locked(),
                "scheduled": scheduled, "last_scan_at": dashboard.sentinel.store.snapshot_updated_at(),
                "storage_error": dashboard.sentinel.store.remote_error,
                "telegram": dashboard.sentinel.notifier.configured, "market_count": len(dashboard.sentinel.markets),
                "classes": classes, "opportunity_count": len(dashboard.last_opportunities),
                "candidate_count": len(dashboard.sentinel.store.candidates()),
                "last_error": dashboard.last_error,
                "interval_seconds": dashboard.settings.runtime["scan_interval_seconds"],
                "lifecycle": lifecycle}

    @app.post("/api/start")
    async def start(): return {"started": dashboard.start(), "running": dashboard.running}

    @app.post("/api/stop")
    async def stop(): return {"stopped": await dashboard.stop(), "running": dashboard.running}

    @app.post("/api/scan")
    async def scan():
        await dashboard.scan()
        return dashboard.sentinel.store.signals("ACTIVE")

    @app.get("/api/opportunities")
    async def opportunities(): return dashboard.sentinel.store.signals("ACTIVE")

    @app.get("/api/candidates")
    async def candidates(): return dashboard.sentinel.store.candidates()

    @app.get("/api/live-prices")
    async def live_prices():
        """Latest forming-candle price for cards; cached to protect venue APIs."""
        if time.time() - dashboard.price_cache_at < 4:
            return dashboard.price_cache
        active = dashboard.sentinel.store.signals("ACTIVE", 200)
        wanted = {(x["venue"], x["symbol"]) for x in active}
        wanted.update((x["venue"], x["symbol"]) for x in dashboard.sentinel.store.candidates())
        if wanted and not dashboard.sentinel.markets:
            await dashboard.sentinel.refresh_markets()
        matches = [(adapter, market) for adapter, market in dashboard.sentinel.markets
                   if (market.venue, market.symbol) in wanted]
        semaphore = asyncio.Semaphore(10)

        async def quote(adapter, market):
            async with semaphore:
                try:
                    candles = await adapter.candles(market, "1h", 2)
                    if not candles: return None
                    current = candles[-1].close
                    previous = candles[-2].close if len(candles) > 1 else current
                    return f"{market.venue}:{market.symbol}", {
                        "price": current,
                        "change_pct": ((current / previous) - 1) * 100 if previous else 0,
                        "updated_at": int(time.time()),
                    }, market, candles
                except Exception:
                    return None

        results = await asyncio.gather(*(quote(a, m) for a, m in matches))
        valid = [x for x in results if x]
        dashboard.price_cache = {key: price for key, price, _, _ in valid}
        active_timeframes: dict[tuple[str, str], set[str]] = {}
        for signal in active:
            active_timeframes.setdefault((signal["venue"], signal["symbol"]), set()).add(signal["timeframe"])
        # Use a point-in-time price so highs/lows recorded before signal creation
        # cannot make qualified cards close and reappear between scans.
        for _, price, market, _ in valid:
            current = float(price["price"])
            live_point = Candle(int(time.time()), current, current, current, current, 0)
            for timeframe in active_timeframes.get((market.venue, market.symbol), ()):
                dashboard.sentinel.store.reconcile(market, timeframe, [live_point])
        dashboard.price_cache_at = time.time()
        return dashboard.price_cache

    @app.get("/api/signals")
    async def signals(status: str | None = None, limit: int = 200):
        return dashboard.sentinel.store.signals(status, min(limit, 500))

    @app.get("/api/signal-events")
    async def signal_events(limit: int = 300):
        return dashboard.sentinel.store.events(min(limit, 500))

    @app.get("/api/dashboard-snapshot")
    async def dashboard_snapshot():
        """One coherent lifecycle view; avoids mixing serverless instances."""
        return {
            "version": dashboard.sentinel.store.snapshot_updated_at() or 0,
            "lifecycle": dashboard.sentinel.store.signal_stats(),
            "signals": dashboard.sentinel.store.signals(limit=200),
            "events": dashboard.sentinel.store.events(300),
        }

    @app.get("/api/signals/{signal_id}/chart")
    async def signal_chart(signal_id: int):
        signal = dashboard.sentinel.store.signal(signal_id)
        if not signal: raise HTTPException(404, "Oportunidade não encontrada")
        match = next(((a, m) for a, m in dashboard.sentinel.markets
                      if m.venue == signal["venue"] and m.symbol == signal["symbol"]), None)
        if not match:
            await dashboard.sentinel.refresh_markets()
            match = next(((a, m) for a, m in dashboard.sentinel.markets
                          if m.venue == signal["venue"] and m.symbol == signal["symbol"]), None)
        if not match: raise HTTPException(404, "Mercado não está mais disponível na venue")
        candles = await match[0].candles(match[1], signal["timeframe"], 240)
        closed = candles[:-1]; closes = [c.close for c in closed]
        ma20, ma50, ma200 = rolling_sma(closes, 20), rolling_sma(closes, 50), rolling_sma(closes, 200)
        lows, highs = pivots(closed, int(dashboard.settings.analysis["pivot_window"]))
        view_start = max(0, len(closed) - 120)
        visible = closed[view_start:]
        last = visible[-1]
        avg_volume = fmean([c.volume for c in visible[-21:-1]]) if len(visible) >= 21 else 0
        volume_ratio = last.volume / avg_volume if avg_volume else 0
        direction = signal["direction"]
        invalid = last.low <= signal["stop"] if direction == "LONG" else last.high >= signal["stop"]
        favorable = last.close >= signal["entry"] if direction == "LONG" else last.close <= signal["entry"]
        progress = ((last.close - signal["entry"]) / (signal["target1"] - signal["entry"])) if signal["target1"] != signal["entry"] else 0
        if invalid: confirmation = "INVALIDADA"
        elif progress >= .8: confirmation = "TARDIA — preço próximo do alvo"
        elif favorable and volume_ratio >= 1: confirmation = "CONFIRMADA"
        else: confirmation = "AGUARDANDO CONFIRMAÇÃO"
        if direction == "LONG":
            acceptance = [
                f"Esperar fechamento de {signal['timeframe']} acima da entrada {signal['entry']:.8g} ou reteste com rejeição compradora.",
                "Preferir volume igual ou superior à média de 20 candles na confirmação.",
                f"Não aceitar se o preço fechar abaixo de {signal['stop']:.8g}; essa é a invalidação estrutural.",
                "Evitar perseguir o preço quando mais de 80% do caminho até o primeiro alvo já foi percorrido.",
            ]
        else:
            acceptance = [
                f"Esperar fechamento de {signal['timeframe']} abaixo da entrada {signal['entry']:.8g} ou reteste com rejeição vendedora.",
                "Preferir volume igual ou superior à média de 20 candles na confirmação.",
                f"Não aceitar se o preço fechar acima de {signal['stop']:.8g}; essa é a invalidação estrutural.",
                "Evitar perseguir o preço quando mais de 80% do caminho até o primeiro alvo já foi percorrido.",
            ]
        risks = list(signal.get("risks", [])) + [
            "Rompimento sem volume pode ser falso e retornar rapidamente à faixa anterior.",
            "Slippage, spread e baixa liquidez podem piorar a entrada e o stop executável.",
        ]
        if signal.get("asset_class") == "crypto":
            risks.append("Mudança no regime diário do BTC pode invalidar o contexto desta cripto.")
        if not signal.get("reasons"):
            signal["reasons"] = [
                f"Setup técnico identificado: {signal['setup']}.",
                f"Risco/retorno projetado de {signal['risk_reward']:.2f}.",
                f"Pontuação técnica de {signal['score']}/100 no momento da abertura.",
            ]
        return {"signal": signal, "confirmation": confirmation, "acceptance": acceptance,
                "risks": list(dict.fromkeys(risks)), "volume_ratio": volume_ratio,
                "last_price": last.close, "support_pivots": lows[-5:], "resistance_pivots": highs[-5:],
                "candles": [{"timestamp": c.timestamp, "open": c.open, "high": c.high, "low": c.low,
                             "close": c.close, "volume": c.volume} for c in visible],
                "ma20": ma20[view_start:], "ma50": ma50[view_start:], "ma200": ma200[view_start:]}

    @app.get("/api/markets")
    async def markets(refresh: bool = False):
        if refresh: await dashboard.sentinel.refresh_markets()
        return [{"venue": m.venue, "symbol": m.symbol, "base": m.base, "market_type": m.market_type,
                 "asset_class": m.asset_class.value, "volume": m.daily_quote_volume,
                 "funding": m.funding_rate, "open_interest": m.open_interest}
                for _, m in dashboard.sentinel.markets]

    @app.get("/api/logs")
    async def logs(): return list(dashboard.logs)

    return app


def main():
    parser = argparse.ArgumentParser(description="Interface web local do Market Sentinel")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8765")))
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run(create_app(args.config), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__": main()
