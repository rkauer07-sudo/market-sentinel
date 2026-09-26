from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
from statistics import fmean
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from . import __version__
from .app import Sentinel
from .analysis import pivots
from .auth import create_session, new_wallet_challenge, normalize_address, read_session, verify_signature
from .config import load_settings
from .explanations import explain_candidate
from .models import Candle
from .solana_intel import SolanaIntelService
from .payments import PaymentError, VipPayments
from .social import SocialStore, SocialUnavailable


class MemoryLogHandler(logging.Handler):
    def __init__(self, records: deque[str]):
        super().__init__(); self.records = records

    def emit(self, record):
        rendered = self.format(record)
        self.records.append(rendered)


class Dashboard:
    def __init__(self, config_path: str):
        self.settings = load_settings(config_path)
        self.sentinel = Sentinel(self.settings)
        self.solana_intel = SolanaIntelService(self.sentinel.client)
        self.social = SocialStore(self.sentinel.store)
        self.vip = VipPayments(self.social)
        self.user_cache: dict[str, tuple[float, dict | None]] = {}
        secret_source = (os.getenv("SESSION_SECRET") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                         or os.getenv("DASHBOARD_PASSWORD"))
        self.ephemeral_session_secret = not bool(secret_source)
        self.session_secret = hashlib.sha256(
            f"market-sentinel-session:{secret_source or secrets.token_urlsafe(32)}".encode()).hexdigest()
        self.task: asyncio.Task | None = None
        self.scan_lock = asyncio.Lock()
        self.last_opportunities = []
        self.last_error: str | None = None
        self.price_cache: dict[str, dict] = {}
        self.price_cache_at = 0.0
        self.logs: deque[str] = deque(maxlen=400)
        self.memory_handler = MemoryLogHandler(self.logs)
        self.memory_handler.setFormatter(
            logging.Formatter("%(asctime)s · %(levelname)s · %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(self.memory_handler)

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
            try:
                await self.solana_intel.snapshot(force=True)
                if self.sentinel.notifier.configured:
                    await self.solana_intel.deliver_pending_alerts(
                        self.sentinel.notifier.send_memecoin_purchase
                    )
            except asyncio.CancelledError: raise
            except Exception:
                logging.getLogger(__name__).exception(
                    "Falha no ciclo do monitor de smart wallets"
                )
            await asyncio.sleep(max(0, interval - (time.monotonic() - cycle_started)))

    async def handle_helius_webhook(self, payload):
        callback = (
            self.sentinel.notifier.send_memecoin_purchase
            if self.sentinel.notifier.configured else None
        )
        purchases = await self.solana_intel.process_helius_webhook(
            payload, send_alert=callback
        )
        for purchase in purchases:
            logging.getLogger(__name__).info(
                "SMART WALLET BUY #%s %s %s",
                purchase["wallet_rank"], purchase["symbol"], purchase["wallet"],
            )

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
        "base_score": op.base_score, "learning_adjustment": op.learning_adjustment,
        "learning_evidence": op.learning_evidence,
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
        "simple_explanation": explain_candidate(candidate),
    }


def live_resolution(signal: dict, price: float) -> dict | None:
    """Classify a terminal touch without mutating a serverless DB copy."""
    targets = [(number, signal.get(f"target{number}")) for number in range(1, 6)]
    targets = [(number, value) for number, value in targets if value is not None]
    if not targets:
        return None
    final_number, final_price = targets[-1]
    long = signal["direction"] == "LONG"
    final_hit = price >= final_price if long else price <= final_price
    stop_hit = price <= signal["stop"] if long else price >= signal["stop"]
    if final_hit:
        return {"id": signal["id"], "status": f"SUCCESS_T{final_number}",
                "price": final_price, "symbol": signal["symbol"]}
    if stop_hit:
        highest = int(signal.get("highest_target_hit") or 0)
        status = f"SUCCESS_T{highest}" if highest else "FAILED"
        return {"id": signal["id"], "status": status,
                "price": signal["stop"], "symbol": signal["symbol"]}
    return None


DEFAULT_OWNER_WALLET = "GVMPqSU3KZTKa58cKLZreZx46rTWVLhEWXJ7DdebDKH8"
VIP_LOCK_MESSAGE = "Oportunidade qualificada exclusiva para membros VIP"


def redact_events(events: list[dict], hidden_ids: set) -> list[dict]:
    """Keep the audit trail but hide which market an open VIP signal is on."""
    result = []
    for event in events:
        if event.get("signal_id") in hidden_ids:
            event = {**event, "symbol": "VIP", "venue": "—", "timeframe": "—", "direction": None,
                     "price": None, "message": VIP_LOCK_MESSAGE, "locked": True}
        result.append(event)
    return result


SIGNAL_LOG_PREFIXES = ("NOVA OPORTUNIDADE", "ALERTA ")


def redact_logs(rows: list[dict]) -> list[dict]:
    """Operational log lines that name a freshly opened signal are VIP-only."""
    return [row for row in rows if not str(row.get("message", "")).startswith(SIGNAL_LOG_PREFIXES)]


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
        logging.getLogger().removeHandler(dashboard.memory_handler)
        await dashboard.stop(); await dashboard.sentinel.close()

    app = FastAPI(title="Market Sentinel", version=__version__, lifespan=lifespan)
    app.state.dashboard = dashboard
    static_dir = Path(__file__).parent / "static"
    static = static_dir / "index.html"
    memecoins_page = static_dir / "memecoins.html"
    auth_user = os.getenv("DASHBOARD_USER")
    auth_password = os.getenv("DASHBOARD_PASSWORD")
    session_cookie = "sentinel_session"

    def request_wallet(request: Request) -> str | None:
        return read_session(request.cookies.get(session_cookie), dashboard.session_secret)

    def public_user(user: dict | None) -> dict | None:
        if not user:
            return None
        return {key: user.get(key) for key in (
            "wallet_address", "display_name", "plan", "subscription_status", "current_period_end")}

    def cached_user(address: str) -> dict | None:
        hit = dashboard.user_cache.get(address)
        if hit and time.time() - hit[0] < 60:
            return hit[1]
        user = dashboard.social.user(address)
        dashboard.user_cache[address] = (time.time(), user)
        return user

    def viewer_is_vip(request: Request) -> bool:
        address = request_wallet(request)
        if not address:
            return False
        try:
            return dashboard.vip.is_vip(cached_user(address))
        except SocialUnavailable:
            return False

    def active_ids() -> set:
        return {row["id"] for row in dashboard.sentinel.store.signals("ACTIVE", 500)}

    def visible_signals(request: Request, rows: list[dict]) -> list[dict]:
        if viewer_is_vip(request):
            return rows
        return [row for row in rows if row.get("status") != "ACTIVE"]

    owner_wallets = {x.strip() for x in os.getenv("FEEDBACK_ADMIN_WALLETS", DEFAULT_OWNER_WALLET).split(",")
                     if x.strip()}

    def public_user_with_vip(user: dict | None) -> dict | None:
        data = public_user(user)
        if data is not None:
            data["vip"] = dashboard.vip.is_vip(user)
            data["is_owner"] = data.get("wallet_address") in owner_wallets
        return data

    def require_owner(request: Request) -> str:
        address = request_wallet(request)
        if not address or address not in owner_wallets:
            raise HTTPException(403, "Área restrita à carteira principal")
        return address

    def client_hash(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        ip = forwarded or (request.client.host if request.client else "unknown")
        return hashlib.sha256(f"{dashboard.session_secret}:{ip}".encode()).hexdigest()[:32]

    def require_wallet(request: Request) -> tuple[str, dict]:
        address = request_wallet(request)
        if not address:
            raise HTTPException(401, "Conecte e assine com sua carteira para acessar o chat")
        try:
            user = dashboard.social.user(address)
        except SocialUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        if not user:
            raise HTTPException(401, "Sessão não corresponde a um usuário ativo")
        return address, user

    canonical_host = os.getenv("CANONICAL_HOST", "").strip().lower()
    redirect_hosts = {h.strip().lower() for h in os.getenv("REDIRECT_HOSTS", "").split(",") if h.strip()}

    @app.middleware("http")
    async def basic_auth(request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0].lower()
        if (canonical_host and host in redirect_hosts and host != canonical_host
                and request.url.path != "/api/solana-intel/helius"):
            query = f"?{request.url.query}" if request.url.query else ""
            return Response(status_code=308,
                            headers={"Location": f"https://{canonical_host}{request.url.path}{query}"})
        if request.url.path == "/api/solana-intel/helius":
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store"
            return response
        if request.url.path.startswith("/api/") and not dashboard.running:
            # sqlite3 connections are thread-bound by default. Keep refresh in
            # the request thread so closing/reopening the shared connection is safe.
            dashboard.sentinel.store.sync_from_remote()
        admin_paths = {"/api/start", "/api/stop", "/api/scan", "/api/solana-intel/refresh"}
        protect_all = os.getenv("DASHBOARD_BASIC_PROTECT_ALL", "false").lower() in {"1", "true", "yes"}
        needs_basic = request.url.path in admin_paths or (
            request.url.path == "/api/markets" and request.query_params.get("refresh") == "true")
        if not (auth_user and auth_password) or (not protect_all and not needs_basic):
            response = await call_next(request)
            if request.url.path.startswith("/api/"):
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            return response
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
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return response

    def require_writer():
        """Only the scheduled worker may mutate the authoritative snapshot."""
        store = dashboard.sentinel.store
        web_writer = os.getenv("SENTINEL_WEB_WRITER", "false").lower() in {"1", "true", "yes"}
        if store.turso_url and not store.remote_error and not web_writer:
            raise HTTPException(409, "Monitor gerenciado pela rotina central; painel em modo somente leitura")

    @app.get("/health", include_in_schema=False)
    async def health(): return {"status": "ok", "version": __version__}

    @app.get("/", include_in_schema=False)
    async def index(): return FileResponse(static)

    @app.get("/memecoins-analyser", include_in_schema=False)
    async def memecoins_analyser(): return FileResponse(memecoins_page)

    @app.get("/static/i18n-full.js", include_in_schema=False)
    async def dashboard_i18n():
        return FileResponse(static_dir / "i18n-full.js", media_type="application/javascript")

    @app.get("/static/solana-intel.css", include_in_schema=False)
    async def solana_intel_css():
        return FileResponse(static_dir / "solana-intel.css", media_type="text/css")

    @app.get("/static/solana-intel.js", include_in_schema=False)
    async def solana_intel_js():
        return FileResponse(static_dir / "solana-intel.js", media_type="application/javascript")

    @app.get("/favicon.svg", include_in_schema=False)
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(static_dir / "favicon.svg", media_type="image/svg+xml",
                            headers={"Cache-Control": "public, max-age=86400"})

    vendor_files = {"solana-web3.iife.min.js", "qrcode-generator.js"}

    @app.get("/static/vendor/{name}", include_in_schema=False)
    async def vendor_asset(name: str):
        if name not in vendor_files:
            raise HTTPException(404, "Arquivo não encontrado")
        return FileResponse(static_dir / "vendor" / name, media_type="application/javascript",
                            headers={"Cache-Control": "public, max-age=604800, immutable"})

    @app.post("/api/auth/nonce")
    async def wallet_nonce(request: Request):
        try:
            payload = await request.json()
            address = normalize_address(payload.get("address"))
            host = (request.headers.get("x-forwarded-host") or request.headers.get("host")
                    or request.url.hostname or "market-sentinel")
            nonce, message, expires_at = new_wallet_challenge(address, host.split(",")[0])
            dashboard.social.save_challenge(address, nonce, message, expires_at)
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc
        except SocialUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"nonce": nonce, "message": message, "expires_at": expires_at}

    @app.post("/api/auth/verify")
    async def wallet_verify(request: Request):
        try:
            payload = await request.json()
            address = normalize_address(payload.get("address"))
            nonce, signature = str(payload.get("nonce") or ""), str(payload.get("signature") or "")
            if not nonce or len(signature) < 20:
                raise ValueError("Desafio ou assinatura ausente")
            message = dashboard.social.challenge_message(address, nonce)
            if not message:
                raise ValueError("Desafio expirado ou já utilizado")
            if not verify_signature(address, message, signature):
                raise ValueError("A assinatura não corresponde à carteira informada")
            if not dashboard.social.consume_challenge(address, nonce):
                raise ValueError("Desafio expirado ou já utilizado")
            user = dashboard.social.upsert_user(address)
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        dashboard.user_cache.pop(address, None)
        response = JSONResponse({"authenticated": True, "user": public_user_with_vip(user)})
        secure_setting = os.getenv("SESSION_COOKIE_SECURE", "auto").lower()
        forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        secure = secure_setting in {"1", "true", "yes"} or (
            secure_setting == "auto" and forwarded_proto.split(",")[0] == "https")
        response.set_cookie(session_cookie, create_session(address, dashboard.session_secret),
            max_age=30 * 24 * 3600, httponly=True, secure=secure, samesite="lax", path="/")
        return response

    @app.get("/api/auth/me")
    async def wallet_me(request: Request):
        address = request_wallet(request)
        if not address:
            return {"authenticated": False, "user": None,
                    "session_persistent": not dashboard.ephemeral_session_secret}
        try:
            user = dashboard.social.user(address)
        except SocialUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"authenticated": bool(user), "user": public_user_with_vip(user),
                "session_persistent": not dashboard.ephemeral_session_secret}

    @app.post("/api/auth/logout")
    async def wallet_logout():
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(session_cookie, path="/")
        return response

    @app.get("/api/vip/config")
    async def vip_config():
        return dashboard.vip.public_config()

    @app.get("/api/vip/blockhash")
    async def vip_blockhash():
        try:
            return await asyncio.to_thread(dashboard.vip.latest_blockhash)
        except PaymentError as exc:
            raise HTTPException(502, str(exc)) from exc

    @app.post("/api/vip/intent")
    async def vip_intent(request: Request):
        address, _ = require_wallet(request)
        try:
            try:
                payload = await request.json()
            except ValueError:
                payload = {}
            code = str((payload or {}).get("code") or "").strip() or None
            result = dashboard.vip.create_intent(address, code)
            if result.get("status") == "paid":
                dashboard.user_cache.pop(address, None)
                result["user"] = public_user_with_vip(result.get("user"))
            return result
        except PaymentError as exc:
            raise HTTPException(400, str(exc)) from exc
        except SocialUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/api/vip/verify")
    async def vip_verify(request: Request):
        address, _ = require_wallet(request)
        try:
            payload = await request.json()
            reference = str(payload.get("reference") or "").strip()
            signature = str(payload.get("signature") or "").strip() or None
            if not reference:
                raise PaymentError("Referência do pagamento ausente")
            result = await asyncio.to_thread(dashboard.vip.verify, address, reference, signature)
        except (PaymentError, TypeError, ValueError) as exc:
            raise HTTPException(400, str(exc)) from exc
        except SocialUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        if result.get("status") == "paid":
            dashboard.user_cache.pop(address, None)
            result["user"] = public_user_with_vip(result.get("user"))
        return result

    @app.post("/api/feedback")
    async def send_feedback(request: Request):
        try:
            payload = await request.json()
        except ValueError:
            raise HTTPException(400, "Envie um JSON válido")
        if str(payload.get("website") or "").strip():  # honeypot anti-bot
            return {"ok": True}
        try:
            saved = dashboard.social.add_feedback(payload.get("body"), payload.get("contact"),
                                                  request_wallet(request), client_hash(request))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except SocialUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"ok": True, **saved}

    @app.get("/api/feedback")
    async def list_feedback(request: Request, limit: int = 200):
        require_owner(request)
        try:
            rows = dashboard.social.feedback(limit)
        except SocialUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"messages": rows, "unread": sum(1 for r in rows if not r["read_at"])}

    @app.post("/api/feedback/{message_id}/read")
    async def read_feedback(message_id: int, request: Request):
        require_owner(request)
        try:
            payload = await request.json()
        except ValueError:
            payload = {}
        dashboard.social.mark_feedback_read(message_id, bool((payload or {}).get("read", True)))
        return {"ok": True}

    @app.get("/api/chat/messages")
    async def chat_messages(request: Request, after_id: int = 0, limit: int = 100):
        address, _ = require_wallet(request)
        try:
            rows = dashboard.social.messages(after_id, limit)
            owners = dashboard.social.users(row["wallet_address"] for row in rows)
        except SocialUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"messages": [{**row, "mine": row["wallet_address"] == address,
                              "vip": dashboard.vip.is_vip(owners.get(row["wallet_address"]))}
                             for row in rows]}

    @app.post("/api/chat/messages")
    async def send_chat_message(request: Request):
        address, user = require_wallet(request)
        try:
            payload = await request.json()
            message = dashboard.social.add_message(address, payload.get("body", ""))
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc
        except SocialUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        return {**message, "mine": True, "vip": dashboard.vip.is_vip(user)}

    def status_payload():
        classes = {}
        for _, market in dashboard.sentinel.markets:
            classes[market.asset_class.value] = classes.get(market.asset_class.value, 0) + 1
        latest_run = dashboard.sentinel.store.latest_run()
        if not classes and latest_run:
            classes = latest_run.get("diagnostics", {}).get("classes", {})
        lifecycle = dashboard.sentinel.store.signal_stats()
        # O worker agendado (GitHub Actions) grava no Turso; a web só lê.
        scheduled = bool(not dashboard.running and dashboard.sentinel.store.turso_url
                         and not dashboard.sentinel.store.remote_error)
        last_scan_at = dashboard.sentinel.store.snapshot_updated_at() or (
            latest_run.get("finished_at") if latest_run else None)
        return {"running": dashboard.running, "scanning": dashboard.scan_lock.locked(),
                "scheduled": scheduled, "last_scan_at": last_scan_at,
                "storage_error": dashboard.sentinel.store.remote_error,
                "telegram": dashboard.sentinel.notifier.configured,
                "market_count": len(dashboard.sentinel.markets) or (latest_run.get("markets", 0) if latest_run else 0),
                "classes": classes, "opportunity_count": len(dashboard.last_opportunities),
                "candidate_count": len(dashboard.sentinel.store.candidates()),
                "last_error": dashboard.last_error,
                "interval_seconds": dashboard.settings.runtime["scan_interval_seconds"],
                "lifecycle": lifecycle, "latest_run": latest_run,
                "learning": dashboard.sentinel.store.latest_learning_run(),
                "social": {"backend": dashboard.social.backend,
                           "session_persistent": not dashboard.ephemeral_session_secret}}

    @app.get("/api/status")
    async def status():
        return status_payload()

    @app.post("/api/start")
    async def start():
        require_writer()
        return {"started": dashboard.start(), "running": dashboard.running}

    @app.post("/api/stop")
    async def stop():
        require_writer()
        return {"stopped": await dashboard.stop(), "running": dashboard.running}

    @app.post("/api/scan")
    async def scan(request: Request):
        require_writer()
        await dashboard.scan()
        return visible_signals(request, dashboard.sentinel.store.signals("ACTIVE"))

    @app.get("/api/opportunities")
    async def opportunities(request: Request):
        return visible_signals(request, dashboard.sentinel.store.signals("ACTIVE"))

    @app.get("/api/candidates")
    async def candidates(): return dashboard.sentinel.store.candidates()

    @app.get("/api/learning")
    async def learning():
        return {"latest": dashboard.sentinel.store.latest_learning_run(),
                "profiles": list(dashboard.sentinel.store.learning_profiles().values())}

    @app.get("/api/solana-intel")
    async def solana_intel():
        return await dashboard.solana_intel.snapshot()

    @app.post("/api/solana-intel/refresh")
    async def refresh_solana_intel():
        return await dashboard.solana_intel.snapshot(force=True)

    @app.post("/api/solana-intel/helius", include_in_schema=False)
    async def solana_intel_helius(request: Request, background_tasks: BackgroundTasks):
        supplied = (
            request.headers.get("Authorization")
            or request.headers.get("X-Helius-Auth")
        )
        if not dashboard.solana_intel.webhook_authorized(supplied):
            raise HTTPException(401, "Webhook Helius não autorizado")
        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(400, "Payload JSON inválido") from exc
        events = payload if isinstance(payload, list) else [payload]
        if not events or not all(isinstance(event, dict) for event in events):
            raise HTTPException(400, "Payload Helius inválido")
        background_tasks.add_task(dashboard.handle_helius_webhook, events)
        return {"accepted": len(events)}

    @app.get("/api/solana-intel/routes/{mint}")
    async def solana_intel_routes(mint: str, amount_sol: float = 0.25):
        try:
            return await dashboard.solana_intel.routes(mint, amount_sol=amount_sol)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/live-prices")
    async def live_prices(request: Request):
        data = await compute_live_prices()
        if viewer_is_vip(request):
            return data
        # Non-VIPs must not learn which markets hold an open qualified signal.
        candidate_keys = {f"{x['venue']}:{x['symbol']}" for x in dashboard.sentinel.store.candidates()}
        public = {key: value for key, value in data.items()
                  if key.startswith("__") or key in candidate_keys}
        public["__resolutions"] = []
        public["__active_ids"] = []
        return public

    async def compute_live_prices():
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
        signal_by_market: dict[tuple[str, str], list[dict]] = {}
        for signal in active:
            signal_by_market.setdefault((signal["venue"], signal["symbol"]), []).append(signal)
        resolutions = []
        for _, quote_data, market, _ in valid:
            for signal in signal_by_market.get((market.venue, market.symbol), ()):
                resolution = live_resolution(signal, float(quote_data["price"]))
                if resolution:
                    resolutions.append(resolution)
        dashboard.price_cache["__resolutions"] = resolutions
        dashboard.price_cache["__active_ids"] = [signal["id"] for signal in active]
        dashboard.price_cache["__lifecycle"] = dashboard.sentinel.store.signal_stats()
        # This GET endpoint must never mutate a serverless instance's local DB.
        # Reconciliation belongs exclusively to the scheduled scanner.
        dashboard.price_cache_at = time.time()
        return dashboard.price_cache

    @app.get("/api/signals")
    async def signals(request: Request, status: str | None = None, limit: int = 200):
        return visible_signals(request, dashboard.sentinel.store.signals(status, min(limit, 500)))

    def visible_events(request: Request, limit: int) -> list[dict]:
        events = dashboard.sentinel.store.events(limit)
        return events if viewer_is_vip(request) else redact_events(events, active_ids())

    @app.get("/api/signal-events")
    async def signal_events(request: Request, limit: int = 300):
        return visible_events(request, min(limit, 500))

    @app.get("/api/dashboard-snapshot")
    async def dashboard_snapshot(request: Request):
        """One coherent lifecycle view; avoids mixing serverless instances."""
        return {
            "version": dashboard.sentinel.store.snapshot_updated_at() or 0,
            "lifecycle": dashboard.sentinel.store.signal_stats(),
            "signals": visible_signals(request, dashboard.sentinel.store.signals(limit=200)),
            "events": visible_events(request, 300),
        }

    @app.get("/api/dashboard-state")
    async def dashboard_state(request: Request):
        """All non-price dashboard data from one process and one DB snapshot."""
        vip = viewer_is_vip(request)
        active = dashboard.sentinel.store.signals("ACTIVE", 200)
        return {
            "version": dashboard.sentinel.store.snapshot_updated_at() or 0,
            "status": status_payload(),
            "vip": vip,
            "opportunities_locked": not vip,
            "opportunity_count": len(active),
            "opportunities": active if vip else [],
            "candidates": dashboard.sentinel.store.candidates(),
            "events": visible_events(request, 300),
            "logs": (dashboard.sentinel.store.operational_logs(300) if vip
                     else redact_logs(dashboard.sentinel.store.operational_logs(300))),
        }

    @app.get("/api/signals/{signal_id}/chart")
    async def signal_chart(signal_id: int, request: Request):
        signal = dashboard.sentinel.store.signal(signal_id)
        if not signal: raise HTTPException(404, "Oportunidade não encontrada")
        if signal.get("status") == "ACTIVE" and not viewer_is_vip(request):
            raise HTTPException(403, "Oportunidade qualificada exclusiva para membros VIP")
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
    async def logs(request: Request):
        rows = dashboard.sentinel.store.operational_logs(300)
        return rows if viewer_is_vip(request) else redact_logs(rows)

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
