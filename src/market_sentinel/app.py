from __future__ import annotations
import asyncio
import logging
import time
import httpx
from .analysis import analyze, analyze_potential, btc_regime
from .config import Settings
from .models import AssetClass, Market
from .storage import Store
from .telegram import TelegramNotifier
from .venues import ArcusAdapter, BackpackAdapter, HyperliquidAdapter, NadoAdapter

log = logging.getLogger(__name__)


class Sentinel:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=30, headers={"User-Agent": "market-sentinel/0.1"})
        self.adapters = [HyperliquidAdapter(self.client, settings.core_assets),
                         BackpackAdapter(self.client, settings.core_assets),
                         NadoAdapter(self.client, settings.core_assets),
                         ArcusAdapter(self.client, settings.core_assets)]
        self.store = Store(settings.runtime["database_path"])
        self.notifier = TelegramNotifier(self.client, settings.telegram_token, settings.telegram_chat_id)
        self.markets: list[tuple[object, Market]] = []
        self.last_refresh = 0.0
        self.last_candidates = []

    async def refresh_markets(self):
        discovered = await asyncio.gather(*(x.discover_markets() for x in self.adapters), return_exceptions=True)
        markets = []
        for adapter, rows in zip(self.adapters, discovered):
            if isinstance(rows, Exception):
                log.error("Falha ao descobrir mercados em %s: %s", adapter.name, rows)
                continue
            markets.extend((adapter, market) for market in rows)
            log.debug("%s: %d mercados relevantes", adapter.name, len(rows))
        self.markets = markets; self.last_refresh = time.time()
        log.info("Mercados atualizados: %d ativos em %d plataformas", len(markets), len(self.adapters))

    async def scan_once(self):
        refresh_seconds = int(self.settings.runtime["market_refresh_hours"]) * 3600
        if not self.markets or time.time() - self.last_refresh >= refresh_seconds: await self.refresh_markets()
        btc = next(((a, m) for a, m in self.markets if m.base.upper() == "BTC" and m.venue == "hyperliquid"), None)
        if btc is None: btc = next(((a, m) for a, m in self.markets if m.base.upper() == "BTC"), None)
        if btc is None: raise RuntimeError("Nenhum mercado BTC disponível para calcular o regime")
        btc_candles = await btc[0].candles(btc[1], "1d", 260)
        regime = btc_regime(btc_candles)
        btc_closed = btc_candles[:-1]
        btc_change_30d = ((btc_closed[-1].close / btc_closed[-31].close) - 1) * 100 if len(btc_closed) >= 31 else None
        semaphore = asyncio.Semaphore(int(self.settings.runtime["max_concurrency"]))
        min_volume = float(self.settings.analysis["min_daily_quote_volume"])
        # Core assets are always monitored. RWAs with a known zero/low venue volume
        # are retained in discovery output but not polled every five minutes.
        active_markets = [(a, m) for a, m in self.markets if
            m.base.upper().replace("-PERP", "") in self.settings.core_assets or
            m.daily_quote_volume >= min_volume or
            (m.venue == "nado" and m.daily_quote_volume == 0)]
        resolutions = []

        async def inspect(adapter, market, timeframe):
            async with semaphore:
                try:
                    candles = await adapter.candles(market, timeframe, max(260, int(self.settings.analysis["min_candles"]) + 5))
                    # Full OHLC ranges are safe only after the candle closes.
                    # The live-price endpoint handles the forming candle from
                    # point-in-time prices so pre-signal highs/lows cannot close it.
                    resolutions.extend(self.store.reconcile(market, timeframe, candles[:-1]))
                    crypto_regime = regime if market.asset_class == AssetClass.CRYPTO else None
                    crypto_change = btc_change_30d if market.asset_class == AssetClass.CRYPTO else None
                    opportunity = analyze(market, timeframe, candles, crypto_regime, self.settings.analysis)
                    candidate = None if opportunity else analyze_potential(
                        market, timeframe, candles, crypto_regime, self.settings.analysis, crypto_change)
                    return opportunity, candidate, None
                except Exception as exc:
                    return None, None, f"{market.venue}:{market.symbol}:{timeframe}: {exc}"

        results = await asyncio.gather(*(inspect(a, m, tf) for a, m in active_markets for tf in self.settings.timeframes))
        failures = [x[2] for x in results if x[2]]
        ranked = sorted((x[0] for x in results if x[0]), key=lambda x: x.score, reverse=True)
        # Avoid correlated duplicate exposure: keep only the strongest venue/timeframe
        # for each underlying asset in a scan.
        opportunities, selected_assets = [], set()
        for opportunity in ranked:
            asset = opportunity.market.base.upper().replace("-PERP", "")
            if asset in selected_assets:
                continue
            selected_assets.add(asset)
            opportunities.append(opportunity)
        candidates = (x[1] for x in results if x[1] and x[1].readiness >= 70)
        self.last_candidates = sorted(candidates, key=lambda x: x.readiness, reverse=True)[:24]
        self.store.save_candidates(self.last_candidates)
        log.info("Varredura concluída: %d mercados, %d sinais, %d cenários, %d falhas",
                 len(active_markets), len(opportunities), len(self.last_candidates), len(failures))
        if failures:
            log.debug("Falhas da varredura: %s", " | ".join(failures))
        for op in opportunities:
            _, created = self.store.register_signal(
                op, int(self.settings.analysis["alert_cooldown_hours"]))
            if created:
                log.info("NOVA OPORTUNIDADE %s %s %s score=%d", op.market.key, op.timeframe, op.direction, op.score)
            if self.store.should_send(op, int(self.settings.analysis["alert_cooldown_hours"])):
                log.info("ALERTA %s %s score=%d rr=%.2f", op.market.key, op.timeframe, op.score, op.risk_reward)
                if self.notifier.configured:
                    try:
                        await self.notifier.send(op)
                    except Exception:
                        log.exception("Falha ao enviar alerta ao Telegram; snapshot será preservado")
                    else:
                        self.store.mark_sent(op)
        for resolution in resolutions:
            log.info("OPORTUNIDADE ENCERRADA %s:%s %s: %s", resolution["venue"], resolution["symbol"],
                     resolution["status"], resolution["resolution_reason"])
            if self.notifier.configured:
                try:
                    await self.notifier.send_resolution(resolution)
                except Exception:
                    log.exception("Falha ao enviar resolução ao Telegram; snapshot será preservado")
        return opportunities

    async def audit_failures(self) -> list[dict]:
        """Recheck failed signals and repair any that touched a target before stop."""
        if not self.markets:
            await self.refresh_markets()
        market_map = {(market.venue, market.symbol): (adapter, market)
                      for adapter, market in self.markets}
        repaired = []
        for signal in self.store.signals("FAILED", 500):
            match = market_map.get((signal["venue"], signal["symbol"]))
            if not match:
                log.warning("AUDITORIA sem mercado %s:%s", signal["venue"], signal["symbol"])
                continue
            adapter, market = match
            seconds = {"1h": 3600, "4h": 14400, "1d": 86400}[signal["timeframe"]]
            age_bars = max(10, int((time.time() - signal["candle_timestamp"]) / seconds) + 5)
            try:
                candles = await adapter.candles(market, signal["timeframe"], min(age_bars, 1000))
                correction = self.store.audit_failed_signal(signal["id"], candles)
            except Exception:
                log.exception("AUDITORIA falhou para %s:%s", signal["venue"], signal["symbol"])
                continue
            if correction:
                repaired.append(correction)
                log.info("AUDITORIA CORRIGIDA %s:%s %s", signal["venue"], signal["symbol"],
                         correction["resolution_reason"])
            else:
                log.info("AUDITORIA MANTIDA %s:%s FAILED", signal["venue"], signal["symbol"])
        return repaired

    async def run_forever(self):
        log.info("Market Sentinel iniciado (Telegram: %s)", "configurado" if self.notifier.configured else "desativado")
        interval = int(self.settings.runtime["scan_interval_seconds"])
        while True:
            cycle_started = time.monotonic()
            try: await self.scan_once()
            except Exception: log.exception("Falha no ciclo de varredura")
            await asyncio.sleep(max(0, interval - (time.monotonic() - cycle_started)))

    async def close(self):
        self.store.close(); await self.client.aclose()
