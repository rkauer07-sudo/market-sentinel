from __future__ import annotations

import asyncio
import hmac
import json
import math
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

import httpx


WSOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD9iiFxQsB4GHtQyMB55Gm"
PAYMENT_MINTS = {WSOL_MINT, USDC_MINT, USDT_MINT}
BASE58_ADDRESS = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


class UpstreamError(RuntimeError):
    pass


def _first(row: dict, *names: str, default=None):
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return default


def _number(value, default: float = 0.0) -> float:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def _integer(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _unix(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value / 1000 if value > 10_000_000_000 else value)
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def _tags(value) -> list[str]:
    if isinstance(value, str):
        return [item.strip().lower() for item in value.split(",") if item.strip()]
    if isinstance(value, dict):
        return sorted(str(key).lower() for key, enabled in value.items() if enabled)
    if isinstance(value, list):
        return sorted({str(item).lower() for item in value})
    return []


def _wilson_lower_bound(wins: int, samples: int, z: float = 1.96) -> float:
    if samples <= 0:
        return 0.0
    proportion = wins / samples
    denominator = 1 + z * z / samples
    centre = proportion + z * z / (2 * samples)
    adjustment = z * math.sqrt(
        (proportion * (1 - proportion) + z * z / (4 * samples)) / samples
    )
    return max(0.0, (centre - adjustment) / denominator)


class SolanaIntelService:
    """Read-only Solana launch and wallet intelligence.

    Jupiter supplies token metadata and quote-only route checks. Birdeye is an
    optional enrichment for wallet cohorts. No endpoint accepts, stores, signs,
    or broadcasts a transaction.
    """

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.jupiter_api_key = os.getenv("JUPITER_API_KEY", "").strip()
        self.birdeye_api_key = os.getenv("BIRDEYE_API_KEY", "").strip()
        self.helius_api_key = os.getenv("HELIUS_API_KEY", "").strip()
        self.jupiter_base = os.getenv("JUPITER_API_BASE", "https://api.jup.ag").rstrip("/")
        self.birdeye_base = os.getenv(
            "BIRDEYE_API_BASE", "https://public-api.birdeye.so"
        ).rstrip("/")
        self.helius_base = os.getenv(
            "HELIUS_API_BASE", "https://api-mainnet.helius-rpc.com"
        ).rstrip("/")
        self.helius_webhook_url = os.getenv("HELIUS_WEBHOOK_URL", "").strip()
        self.helius_webhook_secret = os.getenv("HELIUS_WEBHOOK_SECRET", "").strip()
        self.helius_webhook_id = os.getenv("HELIUS_WEBHOOK_ID", "").strip()
        self.max_tokens = max(1, min(30, _integer(os.getenv("SOLANA_INTEL_MAX_TOKENS"), 30)))
        self.max_wallets = max(
            1, min(100, _integer(os.getenv("SOLANA_INTEL_MAX_WALLETS"), 50))
        )
        self.history_limit = max(
            30, min(2_000, _integer(os.getenv("SOLANA_INTEL_HISTORY_LIMIT"), 500))
        )
        self.history_hours = max(
            1, min(168, _integer(os.getenv("SOLANA_INTEL_HISTORY_HOURS"), 24))
        )
        self.reanalyze_seconds = max(
            900, min(86_400, _integer(
                os.getenv("SOLANA_INTEL_REANALYZE_SECONDS"), 21_600
            ))
        )
        self.wallet_cache_seconds = max(
            900, min(86_400, _integer(
                os.getenv("SOLANA_INTEL_WALLET_CACHE_SECONDS"), 21_600
            ))
        )
        self.max_concurrency = max(
            1, min(10, _integer(os.getenv("SOLANA_INTEL_MAX_CONCURRENCY"), 4))
        )
        self.min_liquidity_usd = max(
            5_000, _number(os.getenv("SOLANA_INTEL_MIN_LIQUIDITY_USD"), 25_000)
        )
        self.min_token_safety = max(
            0, min(100, _integer(os.getenv("SOLANA_INTEL_MIN_TOKEN_SAFETY"), 70))
        )
        self.min_profitable_memecoins = max(
            1, min(20, _integer(
                os.getenv("SOLANA_INTEL_MIN_PROFITABLE_MEMECOINS"), 3
            ))
        )
        self.min_opportunity_score = max(
            0, min(100, _integer(os.getenv("SOLANA_INTEL_MIN_OPPORTUNITY_SCORE"), 72))
        )
        self.cache_seconds = max(
            30, min(3600, _integer(os.getenv("SOLANA_INTEL_CACHE_SECONDS"), 300))
        )
        self.monitor_wallets = max(
            1, min(100, _integer(os.getenv("SOLANA_INTEL_MONITOR_WALLETS"), 25))
        )
        self.purchase_history_limit = max(
            20, min(2_000, _integer(
                os.getenv("SOLANA_INTEL_PURCHASE_HISTORY_LIMIT"), 200
            ))
        )
        self.supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        self.history_bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "sentinel").strip()
        self.history_object = os.getenv(
            "SOLANA_INTEL_HISTORY_OBJECT", "solana-intel-history.json"
        ).strip()
        history_path = os.getenv("SOLANA_INTEL_HISTORY_PATH", "").strip()
        self.history_path = Path(history_path) if history_path else None
        self._history_state: dict = self._empty_history_state()
        self._history_loaded = False
        self._cache: dict | None = None
        self._cache_at = 0.0
        self._lock = asyncio.Lock()

    def _jupiter_headers(self) -> dict[str, str]:
        return {"x-api-key": self.jupiter_api_key} if self.jupiter_api_key else {}

    @staticmethod
    def _empty_history_state() -> dict:
        return {
            "version": 3,
            "tokens": {},
            "wallets": {},
            "wallet_mints": {},
            "purchases": {},
            "helius_webhook": {},
        }

    @property
    def configured(self) -> dict[str, bool]:
        return {
            "jupiter": bool(self.jupiter_api_key),
            "birdeye": bool(self.birdeye_api_key),
            "helius": bool(self.helius_api_key),
        }

    @property
    def webhook_configured(self) -> bool:
        return bool(
            self.helius_api_key
            and self.helius_webhook_url
            and self.helius_webhook_secret
        )

    @property
    def history_persistent(self) -> bool:
        return bool(
            (self.supabase_url and self.supabase_key and self.history_bucket)
            or self.history_path
        )

    def _history_headers(self) -> dict[str, str]:
        headers = {"apikey": self.supabase_key}
        if self.supabase_key and not self.supabase_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.supabase_key}"
        return headers

    def _history_remote_url(self) -> str:
        return (
            f"{self.supabase_url}/storage/v1/object/"
            f"{self.history_bucket}/{self.history_object}"
        )

    @staticmethod
    def _valid_history_state(payload: Any) -> dict:
        if not isinstance(payload, dict):
            return SolanaIntelService._empty_history_state()
        tokens = payload.get("tokens")
        wallets = payload.get("wallets")
        wallet_mints = payload.get("wallet_mints")
        purchases = payload.get("purchases")
        helius_webhook = payload.get("helius_webhook")
        return {
            "version": 3,
            "updated_at": _integer(payload.get("updated_at")),
            "tokens": tokens if isinstance(tokens, dict) else {},
            "wallets": wallets if isinstance(wallets, dict) else {},
            "wallet_mints": wallet_mints if isinstance(wallet_mints, dict) else {},
            "purchases": purchases if isinstance(purchases, dict) else {},
            "helius_webhook": (
                helius_webhook if isinstance(helius_webhook, dict) else {}
            ),
        }

    async def _load_history(self) -> str | None:
        if self._history_loaded:
            return None
        self._history_loaded = True
        try:
            if self.supabase_url and self.supabase_key and self.history_bucket:
                response = await self.client.get(
                    self._history_remote_url(),
                    params={"snapshot": str(time.time_ns())},
                    headers={**self._history_headers(), "Cache-Control": "no-cache, no-store"},
                )
                detail = response.text[:300]
                missing = response.status_code == 404 or (
                    response.status_code == 400
                    and any(term in detail.lower() for term in (
                        "not found", "does not exist", '"statuscode":"404"',
                    ))
                )
                if not missing:
                    if response.status_code >= 400:
                        raise UpstreamError(
                            f"Supabase Storage respondeu {response.status_code}: {detail}"
                        )
                    self._history_state = self._valid_history_state(response.json())
            elif self.history_path and self.history_path.exists():
                self._history_state = self._valid_history_state(
                    json.loads(self.history_path.read_text(encoding="utf-8"))
                )
        except Exception as exc:
            self._history_state = self._empty_history_state()
            return f"{type(exc).__name__}: {exc}"
        return None

    async def _save_history(self) -> str | None:
        self._history_state["updated_at"] = int(time.time())
        encoded = json.dumps(
            self._history_state, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        try:
            if self.supabase_url and self.supabase_key and self.history_bucket:
                response = await self.client.post(
                    self._history_remote_url(),
                    headers={
                        **self._history_headers(),
                        "x-upsert": "true",
                        "Content-Type": "application/json",
                    },
                    content=encoded,
                )
                if response.status_code >= 400:
                    raise UpstreamError(
                        f"Supabase Storage respondeu {response.status_code}: "
                        f"{response.text[:300]}"
                    )
            elif self.history_path:
                self.history_path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.history_path.with_suffix(
                    f"{self.history_path.suffix}.tmp"
                )
                temporary.write_bytes(encoded)
                temporary.replace(self.history_path)
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"
        return None

    async def _get_json(
        self, url: str, *, params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        response = await self.client.get(url, params=params, headers=headers)
        if response.status_code >= 400:
            body = response.text[:240].strip()
            raise UpstreamError(f"HTTP {response.status_code}: {body or 'resposta sem detalhes'}")
        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamError("Resposta JSON inválida") from exc

    async def _recent_tokens(self) -> list[dict]:
        payload = await self._get_json(
            f"{self.jupiter_base}/tokens/v2/recent", headers=self._jupiter_headers()
        )
        if not isinstance(payload, list):
            raise UpstreamError("Jupiter não retornou a lista esperada de tokens")
        return [self._normalize_token(row) for row in payload[: self.max_tokens]
                if isinstance(row, dict) and row.get("id")]

    def _normalize_token(self, row: dict) -> dict:
        audit = row.get("audit") if isinstance(row.get("audit"), dict) else {}
        first_pool = row.get("firstPool") if isinstance(row.get("firstPool"), dict) else {}
        stats = row.get("stats5m") if isinstance(row.get("stats5m"), dict) else {}
        mint_disabled = _first(audit, "mintAuthorityDisabled")
        freeze_disabled = _first(audit, "freezeAuthorityDisabled")
        top_holders = _number(_first(audit, "topHoldersPercentage"), -1)
        liquidity = _number(row.get("liquidity"))
        organic_score = _number(row.get("organicScore"))
        organic_label = str(row.get("organicScoreLabel") or "unknown").lower()
        risk_flags: list[str] = []
        if mint_disabled is False:
            risk_flags.append("mint_authority_active")
        if freeze_disabled is False:
            risk_flags.append("freeze_authority_active")
        if top_holders >= 20:
            risk_flags.append("high_holder_concentration")
        if liquidity and liquidity < 10_000:
            risk_flags.append("thin_liquidity")
        if organic_label == "low":
            risk_flags.append("low_organic_activity")

        safety = 35
        safety += 15 if mint_disabled is True else 0
        safety += 15 if freeze_disabled is True else 0
        safety += 12 if 0 <= top_holders < 20 else 0
        safety += 13 if liquidity >= 25_000 else 6 if liquidity >= 10_000 else 0
        safety += 10 if organic_score >= 60 else 5 if organic_score >= 30 else 0

        return {
            "mint": str(row.get("id")),
            "name": str(row.get("name") or "Token sem nome"),
            "symbol": str(row.get("symbol") or "?")[:24],
            "icon": row.get("icon"),
            "decimals": max(0, min(18, _integer(row.get("decimals"), 6))),
            "first_pool": first_pool.get("id"),
            "first_pool_at": first_pool.get("createdAt"),
            "first_pool_unix": _unix(first_pool.get("createdAt")),
            "holder_count": _integer(row.get("holderCount")),
            "liquidity_usd": liquidity,
            "mcap_usd": _number(row.get("mcap")),
            "fdv_usd": _number(row.get("fdv")),
            "usd_price": _number(row.get("usdPrice")),
            "organic_score": organic_score,
            "organic_label": organic_label,
            "verified": bool(row.get("isVerified")),
            "mint_authority_disabled": mint_disabled,
            "freeze_authority_disabled": freeze_disabled,
            "top_holders_pct": None if top_holders < 0 else round(top_holders, 3),
            "buyers_5m": _integer(_first(stats, "numBuys")),
            "sellers_5m": _integer(_first(stats, "numSells")),
            "traders_5m": _integer(_first(stats, "numTraders")),
            "organic_buyers_5m": _integer(_first(stats, "numOrganicBuyers")),
            "net_buyers_5m": _integer(_first(stats, "numNetBuyers")),
            "buy_volume_5m": _number(_first(stats, "buyVolume")),
            "sell_volume_5m": _number(_first(stats, "sellVolume")),
            "safety_score": min(100, safety),
            "risk_flags": risk_flags,
            "jupiter_url": f"https://jup.ag/swap/SOL-{row.get('id')}",
        }

    async def _top_traders(self, token: dict) -> list[dict]:
        payload = await self._get_json(
            f"{self.birdeye_base}/defi/v2/tokens/top_traders",
            params={
                "address": token["mint"],
                "time_frame": "all_time",
                "sort_type": "desc",
                "sort_by": "realized_pnl",
                "offset": 0,
                "limit": 10,
                "wallet_tags": "sniper,smart_trader",
            },
            headers={"X-API-KEY": self.birdeye_api_key, "x-chain": "solana"},
        )
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        if isinstance(data, list):
            return data
        for key in ("items", "traders", "result"):
            rows = data.get(key) if isinstance(data, dict) else None
            if isinstance(rows, list):
                return rows
        return []

    async def _wallet_pnl_summary(self, wallet: str) -> dict:
        payload = await self._get_json(
            f"{self.birdeye_base}/wallet/v2/pnl/summary",
            params={
                "wallet": wallet,
                "duration": "90d",
                "position_scope": "cumulative",
                "pnl_method": "wac",
            },
            headers={"X-API-KEY": self.birdeye_api_key, "x-chain": "solana"},
        )
        data = payload.get("data", payload) if isinstance(payload, dict) else {}
        return data if isinstance(data, dict) else {}

    def _observation(self, token: dict, row: dict) -> dict | None:
        address = str(_first(row, "owner", "address", "wallet", "walletAddress", default=""))
        if not BASE58_ADDRESS.fullmatch(address):
            return None
        first_trade = _unix(_first(row, "firstTradeUnixTime", "first_trade_unix_time"))
        delay = None
        if first_trade is not None and token.get("first_pool_unix") is not None:
            delay = max(0, first_trade - token["first_pool_unix"])
            if delay > 30 * 86400:
                delay = None
        tags = _tags(_first(row, "walletTags", "wallet_tags", "tags", default=[]))
        realized = _number(_first(row, "realizedPnl", "realized_pnl"))
        unrealized = _number(_first(row, "unrealizedPnl", "unrealized_pnl"))
        total = _number(_first(row, "totalPnl", "total_pnl"), realized + unrealized)
        return {
            "wallet": address,
            "mint": token["mint"],
            "symbol": token["symbol"],
            "first_trade_at": first_trade,
            "entry_delay_seconds": delay,
            "realized_pnl_usd": realized,
            "unrealized_pnl_usd": unrealized,
            "total_pnl_usd": total,
            "volume_usd": _number(_first(row, "volumeUsd", "volume_usd")),
            "buy_trades": _integer(_first(row, "tradeBuy", "trade_buy")),
            "sell_trades": _integer(_first(row, "tradeSell", "trade_sell")),
            "tags": tags,
            "token_liquidity_usd": token["liquidity_usd"],
        }

    def _structural_rejections(self, token: dict) -> list[str]:
        reasons = []
        if token["mint_authority_disabled"] is False:
            reasons.append("mint_authority_active")
        if token["freeze_authority_disabled"] is False:
            reasons.append("freeze_authority_active")
        if token["liquidity_usd"] < self.min_liquidity_usd:
            reasons.append("thin_liquidity")
        if token["top_holders_pct"] is not None and token["top_holders_pct"] >= 20:
            reasons.append("high_holder_concentration")
        if token["organic_score"] < 30:
            reasons.append("low_organic_activity")
        if token["safety_score"] < self.min_token_safety:
            reasons.append("low_safety_score")
        return sorted(set(reasons))

    def _wallet_candidates(self, observations: list[dict]) -> list[str]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for observation in observations:
            grouped[observation["wallet"]].append(observation)
        candidates = []
        for wallet, rows in grouped.items():
            tags = {tag for row in rows for tag in row["tags"]}
            if tags.intersection({"dev", "insider", "bundler"}):
                continue
            if "smart_trader" not in tags and not any(
                row["realized_pnl_usd"] > 0 for row in rows
            ):
                continue
            candidates.append((
                wallet,
                "smart_trader" in tags,
                len({row["mint"] for row in rows}),
                sum(max(0, row["realized_pnl_usd"]) for row in rows),
            ))
        candidates.sort(key=lambda item: (-int(item[1]), -item[2], -item[3], item[0]))
        return [item[0] for item in candidates[: self.max_wallets]]

    @staticmethod
    def _flatten_wallet_summary(history: dict) -> dict:
        flattened = {}

        def visit(value: dict) -> None:
            for key, item in value.items():
                if isinstance(item, dict):
                    visit(item)
                else:
                    flattened[key] = item

        visit(history)
        return flattened

    def _wallet_profile(
        self, wallet: str, history: dict, observations: list[dict]
    ) -> dict:
        row = self._flatten_wallet_summary(history)
        wallet_observations = [item for item in observations if item["wallet"] == wallet]
        tags = sorted({tag for item in wallet_observations for tag in item["tags"]})
        total_buy = _integer(_first(
            row, "total_buy", "totalBuy", "total_buy_count", "totalBuyCount"
        ))
        total_sell = _integer(_first(
            row, "total_sell", "totalSell", "total_sell_count", "totalSellCount"
        ))
        total_trade = _integer(
            _first(row, "total_trade", "totalTrade", "total_trade_count", "totalTradeCount"),
            total_buy + total_sell,
        )
        wins = _integer(_first(row, "total_win", "totalWin", "win_count", "winCount"))
        losses = _integer(_first(
            row, "total_loss", "totalLoss", "loss_count", "lossCount"
        ))
        outcomes = wins + losses
        raw_win_rate = _number(_first(row, "win_rate", "winRate"), -1)
        if raw_win_rate < 0:
            win_rate = wins / outcomes if outcomes else 0.0
        else:
            win_rate = raw_win_rate / 100 if raw_win_rate > 1 else raw_win_rate
        win_rate = max(0.0, min(1.0, win_rate))
        realized = _number(_first(
            row, "realized_profit_usd", "realizedProfitUsd", "realized_pnl",
            "realizedPnl", "realized_profit", "realizedProfit",
        ))
        unrealized = _number(_first(
            row, "unrealized_profit_usd", "unrealizedProfitUsd", "unrealized_pnl",
            "unrealizedPnl", "unrealized_profit", "unrealizedProfit", "unrealized_usd",
        ))
        total_pnl = _number(_first(
            row, "total_profit_usd", "totalProfitUsd", "total_pnl", "totalPnl",
            "total_usd",
        ), realized + unrealized)
        avg_profit = _number(_first(
            row, "avg_profit_per_trade", "avgProfitPerTrade", "average_profit_per_trade",
            "avg_profit_per_trade_usd",
        ))
        confidence = _wilson_lower_bound(wins, outcomes)
        accuracy_points = confidence * 45
        profit_points = min(
            20, math.log1p(max(0, realized)) / math.log(100_001) * 20
        )
        sample_points = min(15, math.log1p(outcomes) / math.log(51) * 15)
        exit_points = min(1.0, total_sell / max(1, total_buy)) * 10
        average_points = 5 if avg_profit > 0 else 0
        tag_points = 5 if "smart_trader" in tags else 0
        risk_penalty = 100 if set(tags).intersection({"dev", "insider", "bundler"}) else 0
        score = round(max(0, min(
            100,
            accuracy_points + profit_points + sample_points + exit_points
            + average_points + tag_points - risk_penalty,
        )))
        profile = {
            "wallet": wallet,
            "score": score,
            "qualified": False,
            "history_window": "90d",
            "total_buy": total_buy,
            "total_sell": total_sell,
            "total_trade": total_trade,
            "outcomes": outcomes,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(win_rate * 100, 1),
            "confidence_win_rate_pct": round(confidence * 100, 1),
            "realized_pnl_usd": round(realized, 2),
            "unrealized_pnl_usd": round(unrealized, 2),
            "total_pnl_usd": round(total_pnl, 2),
            "avg_profit_per_trade_usd": round(avg_profit, 2),
            "recent_tokens_seen": 0,
            "profitable_memecoins": 0,
            "profitable_memecoin_mints": [],
            "early_buys": 0,
            "median_entry_seconds": None,
            "earliest_entry_seconds": None,
            "tags": tags,
            "risk_penalty": risk_penalty,
            "confidence": "aggressive",
            "observations": [],
            "solscan_url": f"https://solscan.io/account/{wallet}",
        }
        return self._refresh_wallet_profile(profile, wallet_observations)

    def _refresh_wallet_profile(
        self, profile: dict, observations: list[dict]
    ) -> dict:
        """Merge distinct profitable mints and reapply the monitoring rule.

        The profitable-mint list is persisted independently of the compact UI
        observation sample. Current Birdeye evidence replaces older evidence
        for the same mint, so a PnL that later turns non-positive stops counting.
        """
        wallet = str(profile.get("wallet") or "")
        previous_rows = profile.get("observations")
        if not isinstance(previous_rows, list):
            previous_rows = []
        current_rows = [
            item for item in observations
            if isinstance(item, dict) and item.get("wallet") == wallet
        ]

        evidence_by_mint: dict[str, dict] = {}
        for item in previous_rows:
            mint = str(item.get("mint") or "")
            if BASE58_ADDRESS.fullmatch(mint):
                evidence_by_mint[mint] = item
        current_by_mint: dict[str, dict] = {}
        for item in current_rows:
            mint = str(item.get("mint") or "")
            if not BASE58_ADDRESS.fullmatch(mint):
                continue
            current = current_by_mint.get(mint)
            if (
                current is None
                or _number(item.get("realized_pnl_usd"))
                >= _number(current.get("realized_pnl_usd"))
            ):
                current_by_mint[mint] = item
        evidence_by_mint.update(current_by_mint)

        stored_mints = profile.get("profitable_memecoin_mints")
        profitable_mints: set[str] = set()
        if isinstance(stored_mints, list):
            profitable_mints.update(
                str(mint) for mint in stored_mints
                if BASE58_ADDRESS.fullmatch(str(mint))
            )
        if not profitable_mints:
            profitable_mints.update(
                mint for mint, item in evidence_by_mint.items()
                if _number(item.get("realized_pnl_usd")) > 0
            )
        for mint, item in current_by_mint.items():
            if _number(item.get("realized_pnl_usd")) > 0:
                profitable_mints.add(mint)
            else:
                profitable_mints.discard(mint)

        tags = {
            str(tag).lower() for tag in profile.get("tags", [])
            if str(tag).strip()
        }
        tags.update(
            str(tag).lower() for item in current_rows
            for tag in item.get("tags", []) if str(tag).strip()
        )
        risk_penalty = 100 if tags.intersection(
            {"dev", "insider", "bundler"}
        ) else 0
        profitable_count = len(profitable_mints)
        delays = [
            _integer(item.get("entry_delay_seconds"))
            for item in evidence_by_mint.values()
            if item.get("entry_delay_seconds") is not None
        ]
        ordered_observations = sorted(evidence_by_mint.values(), key=lambda item: (
            item.get("entry_delay_seconds") is None,
            _integer(item.get("entry_delay_seconds"), 10**9),
        ))
        profile.update({
            "qualified": bool(
                risk_penalty == 0
                and profitable_count >= self.min_profitable_memecoins
            ),
            "recent_tokens_seen": max(
                _integer(profile.get("recent_tokens_seen")),
                len(evidence_by_mint),
                profitable_count,
            ),
            "profitable_memecoins": profitable_count,
            "profitable_memecoin_mints": sorted(profitable_mints),
            "early_buys": max(
                _integer(profile.get("early_buys")),
                sum(delay <= 120 for delay in delays),
            ),
            "median_entry_seconds": (
                round(median(delays), 1) if delays
                else profile.get("median_entry_seconds")
            ),
            "earliest_entry_seconds": (
                min(delays) if delays else profile.get("earliest_entry_seconds")
            ),
            "tags": sorted(tags),
            "risk_penalty": risk_penalty,
            "confidence": (
                "robust" if profitable_count >= 8
                else "established" if profitable_count >= 5
                else "aggressive"
            ),
            "qualification_rule": (
                f">={self.min_profitable_memecoins} memecoins distintas com "
                "PnL realizado positivo"
            ),
            "observations": ordered_observations[:12],
        })
        return profile

    def _remember_wallet_mints(self, wallet: str, mints: set[str]) -> None:
        if not mints:
            return
        records = self._history_state.setdefault("wallet_mints", {})
        current = records.get(wallet, [])
        seen = {str(mint) for mint in current if BASE58_ADDRESS.fullmatch(str(mint))}
        seen.update(mint for mint in mints if BASE58_ADDRESS.fullmatch(mint))
        records[wallet] = sorted(seen)[-2_000:]

    def _build_opportunities(
        self, tokens: list[dict], observations: list[dict], wallets: list[dict]
    ) -> tuple[list[dict], dict[str, int], dict[str, list[str]]]:
        wallet_by_address = {
            wallet["wallet"]: wallet for wallet in wallets if wallet["qualified"]
        }
        observations_by_mint: dict[str, list[dict]] = defaultdict(list)
        for observation in observations:
            observations_by_mint[observation["mint"]].append(observation)
        rejected: dict[str, int] = defaultdict(int)
        rejected_by_mint: dict[str, list[str]] = {}
        opportunities = []
        for token in tokens:
            structural_rejections = self._structural_rejections(token)
            if structural_rejections:
                rejected_by_mint[token["mint"]] = structural_rejections
                for reason in structural_rejections:
                    rejected[reason] += 1
                continue
            evidence_by_wallet = {}
            for observation in observations_by_mint[token["mint"]]:
                wallet = wallet_by_address.get(observation["wallet"])
                if not wallet:
                    continue
                current = evidence_by_wallet.get(observation["wallet"])
                if current is None or observation["total_pnl_usd"] > current[1]["total_pnl_usd"]:
                    evidence_by_wallet[observation["wallet"]] = (wallet, observation)
            evidence = sorted(
                evidence_by_wallet.values(), key=lambda item: -item[0]["score"]
            )
            if not evidence:
                rejected_by_mint[token["mint"]] = ["no_quality_wallet"]
                rejected["no_quality_wallet"] += 1
                continue
            top_evidence = evidence[:3]
            best_score = top_evidence[0][0]["score"]
            average_score = sum(item[0]["score"] for item in top_evidence) / len(top_evidence)
            early_count = sum(
                (
                    item[1]["entry_delay_seconds"] is not None
                    and item[1]["entry_delay_seconds"] <= 120
                ) or "sniper" in item[1]["tags"]
                for item in top_evidence
            )
            wallet_points = best_score * 0.35 + average_score * 0.20
            safety_points = token["safety_score"] * 0.25
            early_points = early_count / len(top_evidence) * 8
            evidence_points = min(1.0, len(evidence) / 3) * 7
            activity_points = (
                min(1.0, token["organic_score"] / 60)
                + min(1.0, token["traders_5m"] / 25)
            ) / 2 * 5
            opportunity_score = round(min(
                100,
                wallet_points + safety_points + early_points
                + evidence_points + activity_points,
            ))
            if opportunity_score < self.min_opportunity_score:
                rejected_by_mint[token["mint"]] = ["below_opportunity_score"]
                rejected["below_opportunity_score"] += 1
                continue
            best_wallet = top_evidence[0][0]
            reasons = [
                f"{len(evidence)} carteira(s) com histórico qualificado",
                (
                    f"melhor carteira: {best_wallet['profitable_memecoins']} "
                    "memecoins distintas com lucro realizado"
                ),
                f"PnL realizado 90d: ${best_wallet['realized_pnl_usd']:,.0f}",
            ]
            if early_count:
                reasons.append(f"{early_count} entrada(s) precoce(s) qualificada(s)")
            wallet_evidence = []
            for wallet, observation in top_evidence:
                wallet_evidence.append({
                    "wallet": wallet["wallet"],
                    "score": wallet["score"],
                    "win_rate_pct": wallet["win_rate_pct"],
                    "confidence_win_rate_pct": wallet["confidence_win_rate_pct"],
                    "outcomes": wallet["outcomes"],
                    "total_buy": wallet["total_buy"],
                    "total_sell": wallet["total_sell"],
                    "realized_pnl_usd": wallet["realized_pnl_usd"],
                    "profitable_memecoins": wallet["profitable_memecoins"],
                    "entry_delay_seconds": observation["entry_delay_seconds"],
                    "early": bool(
                        (
                            observation["entry_delay_seconds"] is not None
                            and observation["entry_delay_seconds"] <= 120
                        ) or "sniper" in observation["tags"]
                    ),
                    "tags": observation["tags"],
                    "solscan_url": wallet["solscan_url"],
                })
            opportunities.append({
                **token,
                "opportunity_score": opportunity_score,
                "conviction": (
                    "high" if opportunity_score >= 82 and len(evidence) >= 2
                    else "selective"
                ),
                "quality_wallet_count": len(evidence),
                "early_quality_wallet_count": early_count,
                "best_wallet_score": best_score,
                "reasons": reasons,
                "wallet_evidence": wallet_evidence,
            })
        opportunities.sort(key=lambda item: (
            -item["opportunity_score"], -item["quality_wallet_count"],
            -item["liquidity_usd"],
        ))
        return (
            opportunities,
            dict(sorted(rejected.items())),
            rejected_by_mint,
        )

    def _merge_launch_history(self, recent_tokens: list[dict], now: int) -> None:
        records = self._history_state.setdefault("tokens", {})
        for token in recent_tokens:
            mint = token["mint"]
            record = records.get(mint)
            if not isinstance(record, dict):
                record = {
                    "discovered_at": now,
                    "analyzed_at": 0,
                    "analysis": None,
                    "wallets": [],
                    "rejection_reasons": [],
                }
            record["token"] = token
            record["last_seen_at"] = now
            if self._structural_rejections(token):
                record["analysis"] = None
                record["wallets"] = []
            records[mint] = record

        cutoff = now - self.history_hours * 3600
        retained = [
            (mint, record) for mint, record in records.items()
            if isinstance(record, dict)
            and _integer(record.get("discovered_at"), now) >= cutoff
            and isinstance(record.get("token"), dict)
        ]
        retained.sort(
            key=lambda item: _integer(item[1].get("discovered_at")), reverse=True
        )
        self._history_state["tokens"] = dict(retained[: self.history_limit])

        wallet_cache = self._history_state.setdefault("wallets", {})
        wallet_cutoff = now - max(self.history_hours * 3600, self.wallet_cache_seconds * 2)
        cached = [
            (wallet, record) for wallet, record in wallet_cache.items()
            if isinstance(record, dict)
            and _integer(record.get("audited_at")) >= wallet_cutoff
            and isinstance(record.get("profile"), dict)
        ]
        cached.sort(key=lambda item: _integer(item[1].get("audited_at")), reverse=True)
        self._history_state["wallets"] = dict(cached[:1_000])

    def _history_tokens(self) -> list[dict]:
        records = self._history_state.get("tokens", {})
        ordered = sorted(
            (record for record in records.values() if isinstance(record, dict)),
            key=lambda record: _integer(record.get("discovered_at")),
            reverse=True,
        )
        return [record["token"] for record in ordered if isinstance(record.get("token"), dict)]

    def _tokens_due_for_analysis(self, now: int) -> list[dict]:
        due = []
        for record in self._history_state.get("tokens", {}).values():
            token = record.get("token") if isinstance(record, dict) else None
            if not isinstance(token, dict):
                continue
            structural_rejections = self._structural_rejections(token)
            analyzed_at = _integer(record.get("analyzed_at"))
            if structural_rejections:
                record["analyzed_at"] = now
                record["analysis"] = None
                record["wallets"] = []
                record["rejection_reasons"] = structural_rejections
                continue
            if not analyzed_at or now - analyzed_at >= self.reanalyze_seconds:
                due.append((not bool(analyzed_at), analyzed_at, record))
        due.sort(key=lambda item: (
            -int(item[0]), item[1], -_integer(item[2].get("discovered_at")),
        ))
        return [item[2]["token"] for item in due[: self.max_tokens]]

    def _aggregate_history(self) -> tuple[list[dict], list[dict], dict[str, int]]:
        opportunities = []
        rejection_reasons: dict[str, int] = defaultdict(int)
        records = self._history_state.get("tokens", {})
        for record in records.values():
            if not isinstance(record, dict):
                continue
            token = record.get("token")
            if not isinstance(token, dict):
                continue
            analysis = record.get("analysis")
            if isinstance(analysis, dict) and not self._structural_rejections(token):
                opportunities.append({**token, **analysis})
            elif _integer(record.get("analyzed_at")):
                for reason in record.get("rejection_reasons", []):
                    rejection_reasons[str(reason)] += 1
        opportunities.sort(key=lambda item: (
            -item["opportunity_score"], -item["quality_wallet_count"],
            -item["liquidity_usd"],
        ))
        wallet_cache = self._history_state.get("wallets", {})
        wallets = []
        for record in wallet_cache.values():
            if not isinstance(record, dict) or not isinstance(
                record.get("profile"), dict
            ):
                continue
            profile = self._refresh_wallet_profile(record["profile"], [])
            record["profile"] = profile
            if profile.get("qualified"):
                wallets.append(profile)
        # Qualification is deliberately aggressive: the configured number of
        # distinct memecoins with positive realized PnL. The ranking itself is
        # led by aggregate realized PnL rather than the context score.
        wallets.sort(key=lambda row: (
            -_number(row.get("realized_pnl_usd")),
            -_number(row.get("score")),
            -_integer(row.get("outcomes")),
            row.get("wallet", ""),
        ))
        return opportunities, wallets, dict(sorted(rejection_reasons.items()))

    def _purchase_rows(self) -> list[dict]:
        purchases = self._history_state.get("purchases", {})
        rows = [row for row in purchases.values() if isinstance(row, dict)]
        rows.sort(key=lambda row: (
            -_integer(row.get("purchased_at_unix")), row.get("event_id", "")
        ))
        return rows[: self.purchase_history_limit]

    def webhook_authorized(self, supplied: str | None) -> bool:
        if not self.helius_webhook_secret or not supplied:
            return False
        candidates = {supplied.strip()}
        if supplied.lower().startswith("bearer "):
            candidates.add(supplied[7:].strip())
        return any(
            hmac.compare_digest(candidate, self.helius_webhook_secret)
            for candidate in candidates
        )

    async def _sync_helius_webhook(self, wallets: list[dict]) -> dict:
        addresses = sorted([
            wallet["wallet"] for wallet in wallets[: self.monitor_wallets]
            if BASE58_ADDRESS.fullmatch(str(wallet.get("wallet", "")))
        ])
        if not self.webhook_configured:
            return {
                "configured": False,
                "available": None,
                "mode": "webhook-not-configured",
                "wallets_monitored": 0,
            }
        if not addresses:
            return {
                "configured": True,
                "available": True,
                "mode": "webhook-awaiting-ranked-wallets",
                "wallets_monitored": 0,
            }

        state = self._history_state.setdefault("helius_webhook", {})
        stored_addresses = state.get("account_addresses", [])
        webhook_id = self.helius_webhook_id or str(state.get("webhook_id") or "")
        if addresses == stored_addresses and webhook_id:
            return {
                "configured": True,
                "available": True,
                "mode": "enhanced-webhook",
                "wallets_monitored": len(addresses),
            }

        params = {"api-key": self.helius_api_key}
        if not webhook_id:
            response = await self.client.get(
                f"{self.helius_base}/v0/webhooks", params=params
            )
            if response.status_code >= 400:
                raise UpstreamError(
                    f"Helius webhooks respondeu {response.status_code}: {response.text[:240]}"
                )
            rows = response.json()
            if isinstance(rows, list):
                match = next((
                    row for row in rows if isinstance(row, dict)
                    and row.get("webhookURL") == self.helius_webhook_url
                ), None)
                if match:
                    webhook_id = str(match.get("webhookID") or "")
                    remote_addresses = sorted(
                        str(address) for address in match.get("accountAddresses", [])
                    )
                    remote_types = {
                        str(value).upper() for value in match.get("transactionTypes", [])
                    }
                    if (
                        webhook_id and remote_addresses == addresses
                        and {"SWAP", "BUY"}.issubset(remote_types)
                        and match.get("active", True)
                    ):
                        state.update({
                            "webhook_id": webhook_id,
                            "webhook_url": self.helius_webhook_url,
                            "account_addresses": addresses,
                            "synced_at": int(time.time()),
                        })
                        return {
                            "configured": True,
                            "available": True,
                            "mode": "enhanced-webhook",
                            "wallets_monitored": len(addresses),
                        }

        body = {
            "webhookURL": self.helius_webhook_url,
            "transactionTypes": ["SWAP", "BUY"],
            "accountAddresses": addresses,
            "webhookType": "enhanced",
            "authHeader": self.helius_webhook_secret,
            "txnStatus": "success",
        }
        if webhook_id:
            response = await self.client.put(
                f"{self.helius_base}/v0/webhooks/{webhook_id}",
                params=params,
                json=body,
            )
        else:
            response = await self.client.post(
                f"{self.helius_base}/v0/webhooks", params=params, json=body
            )
        if response.status_code >= 400:
            raise UpstreamError(
                f"Helius webhooks respondeu {response.status_code}: {response.text[:240]}"
            )
        payload = response.json()
        webhook_id = str(payload.get("webhookID") or webhook_id)
        state.update({
            "webhook_id": webhook_id,
            "webhook_url": self.helius_webhook_url,
            "account_addresses": addresses,
            "synced_at": int(time.time()),
        })
        return {
            "configured": True,
            "available": True,
            "mode": "enhanced-webhook",
            "wallets_monitored": len(addresses),
        }

    @staticmethod
    def _outgoing_payment(event: dict, wallet: str, incoming_mint: str) -> dict | None:
        native_amount = sum(
            max(0, _number(transfer.get("amount")))
            for transfer in event.get("nativeTransfers", [])
            if isinstance(transfer, dict)
            and transfer.get("fromUserAccount") == wallet
            and transfer.get("toUserAccount") != wallet
        )
        if native_amount > 0:
            return {
                "payment_mint": WSOL_MINT,
                "payment_symbol": "SOL",
                "payment_amount": round(native_amount / 1_000_000_000, 9),
            }
        outgoing = [
            transfer for transfer in event.get("tokenTransfers", [])
            if isinstance(transfer, dict)
            and transfer.get("fromUserAccount") == wallet
            and transfer.get("mint") != incoming_mint
            and _number(transfer.get("tokenAmount")) > 0
        ]
        if outgoing:
            payment = outgoing[0]
            mint = str(payment.get("mint") or "")
            symbol = "USDC" if mint == USDC_MINT else "USDT" if mint == USDT_MINT \
                else "WSOL" if mint == WSOL_MINT else "TOKEN"
            return {
                "payment_mint": mint,
                "payment_symbol": symbol,
                "payment_amount": round(_number(payment.get("tokenAmount")), 9),
            }
        if event.get("feePayer") == wallet:
            return {
                "payment_mint": None,
                "payment_symbol": "não identificado",
                "payment_amount": None,
            }
        return None

    async def _token_by_mint(self, mint: str) -> dict:
        token_records = self._history_state.get("tokens", {})
        record = token_records.get(mint)
        if isinstance(record, dict) and isinstance(record.get("token"), dict):
            return record["token"]
        try:
            payload = await self._get_json(
                f"{self.jupiter_base}/tokens/v2/search",
                params={"query": mint}, headers=self._jupiter_headers(),
            )
            exact = next((
                row for row in payload if isinstance(row, dict) and row.get("id") == mint
            ), None) if isinstance(payload, list) else None
            if exact:
                return self._normalize_token(exact)
        except Exception:
            pass
        return {
            "mint": mint,
            "name": "Token novo",
            "symbol": "?",
            "icon": None,
            "decimals": 0,
            "first_pool_at": None,
            "liquidity_usd": 0,
            "mcap_usd": 0,
            "usd_price": 0,
            "holder_count": 0,
            "organic_score": 0,
            "safety_score": 0,
            "risk_flags": ["metadata_unavailable"],
            "jupiter_url": f"https://jup.ag/swap/SOL-{mint}",
        }

    async def process_helius_webhook(
        self, payload: Any, *, send_alert=None
    ) -> list[dict]:
        events = payload if isinstance(payload, list) else [payload]
        created: list[dict] = []
        async with self._lock:
            await self._load_history()
            _, ranked_wallets, _ = self._aggregate_history()
            ranked = {
                wallet["wallet"]: {**wallet, "rank": index + 1}
                for index, wallet in enumerate(ranked_wallets[: self.monitor_wallets])
            }
            purchases = self._history_state.setdefault("purchases", {})
            wallet_mints = self._history_state.setdefault("wallet_mints", {})
            for event in events:
                if not isinstance(event, dict):
                    continue
                event_type = str(event.get("type") or "").upper()
                signature = str(event.get("signature") or "")
                if event_type not in {"SWAP", "BUY"} or not signature:
                    continue
                for transfer in event.get("tokenTransfers", []):
                    if not isinstance(transfer, dict):
                        continue
                    wallet = str(transfer.get("toUserAccount") or "")
                    mint = str(transfer.get("mint") or "")
                    standard = str(transfer.get("tokenStandard") or "").lower()
                    amount = _number(transfer.get("tokenAmount"))
                    if (
                        wallet not in ranked or mint in PAYMENT_MINTS or amount <= 0
                        or "nonfungible" in standard
                        or not BASE58_ADDRESS.fullmatch(mint)
                    ):
                        continue
                    payment = self._outgoing_payment(event, wallet, mint)
                    if payment is None:
                        continue
                    event_id = f"{signature}:{wallet}:{mint}"
                    seen = {
                        str(item) for item in wallet_mints.get(wallet, [])
                        if BASE58_ADDRESS.fullmatch(str(item))
                    }
                    if event_id in purchases or mint in seen:
                        continue
                    token = await self._token_by_mint(mint)
                    purchased_at = _integer(
                        event.get("timestamp"), int(time.time())
                    )
                    profile = ranked[wallet]
                    purchase = {
                        "event_id": event_id,
                        "signature": signature,
                        "purchased_at_unix": purchased_at,
                        "wallet": wallet,
                        "wallet_rank": profile["rank"],
                        "wallet_score": profile.get("score", 0),
                        "wallet_realized_pnl_usd": profile.get("realized_pnl_usd", 0),
                        "wallet_profitable_memecoins": profile.get(
                            "profitable_memecoins", 0
                        ),
                        "wallet_win_rate_pct": profile.get("win_rate_pct", 0),
                        "wallet_outcomes": profile.get("outcomes", 0),
                        "mint": mint,
                        "token_amount": round(amount, 9),
                        "symbol": token.get("symbol", "?"),
                        "name": token.get("name", "Token novo"),
                        "icon": token.get("icon"),
                        "usd_price": token.get("usd_price", 0),
                        "liquidity_usd": token.get("liquidity_usd", 0),
                        "mcap_usd": token.get("mcap_usd", 0),
                        "holder_count": token.get("holder_count", 0),
                        "safety_score": token.get("safety_score", 0),
                        "risk_flags": token.get("risk_flags", []),
                        "source": str(event.get("source") or "UNKNOWN"),
                        "transaction_type": event_type,
                        "first_wallet_buy": True,
                        "alert_sent_at": 0,
                        "alert_error": None,
                        "solscan_url": f"https://solscan.io/account/{wallet}",
                        "transaction_url": f"https://solscan.io/tx/{signature}",
                        "jupiter_url": f"https://jup.ag/swap/SOL-{mint}",
                        **payment,
                    }
                    purchases[event_id] = purchase
                    seen.add(mint)
                    wallet_mints[wallet] = sorted(seen)[-2_000:]
                    created.append(purchase)

            retained = self._purchase_rows()
            self._history_state["purchases"] = {
                row["event_id"]: row for row in retained
            }
            if created:
                await self._save_history()
                self._cache = None

        if send_alert:
            await self.deliver_pending_alerts(send_alert)
        return created

    async def deliver_pending_alerts(self, send_alert) -> int:
        async with self._lock:
            await self._load_history()
            pending_ids = [
                row["event_id"] for row in reversed(self._purchase_rows())
                if not _integer(row.get("alert_sent_at"))
            ]
        delivered = 0
        for event_id in pending_ids:
            async with self._lock:
                event = self._history_state.get("purchases", {}).get(event_id)
                if not isinstance(event, dict) or _integer(event.get("alert_sent_at")):
                    continue
                outgoing = dict(event)
            try:
                await send_alert(outgoing)
            except Exception as exc:
                async with self._lock:
                    current = self._history_state.get("purchases", {}).get(event_id)
                    if isinstance(current, dict):
                        current["alert_error"] = f"{type(exc).__name__}: {exc}"[:300]
                        await self._save_history()
                continue
            async with self._lock:
                current = self._history_state.get("purchases", {}).get(event_id)
                if isinstance(current, dict):
                    current["alert_sent_at"] = int(time.time())
                    current["alert_error"] = None
                    await self._save_history()
                    self._cache = None
            delivered += 1
        return delivered

    async def snapshot(self, *, force: bool = False) -> dict:
        now = time.time()
        if not force and self._cache and now - self._cache_at < self.cache_seconds:
            return self._cache
        async with self._lock:
            now = time.time()
            if not force and self._cache and now - self._cache_at < self.cache_seconds:
                return self._cache
            generated_at = int(time.time())
            errors: list[dict] = []
            providers = {
                "jupiter": {"configured": bool(self.jupiter_api_key), "available": False,
                            "mode": "api-key" if self.jupiter_api_key else "keyless"},
                "birdeye": {"configured": bool(self.birdeye_api_key), "available": False,
                            "mode": "api-key-required"},
                "helius": {
                    "configured": self.webhook_configured,
                    "available": None,
                    "mode": "webhook-not-configured",
                    "wallets_monitored": 0,
                },
                "history": {
                    "configured": self.history_persistent,
                    "available": True,
                    "persistent": self.history_persistent,
                    "mode": (
                        "supabase-storage" if self.supabase_url and self.supabase_key
                        else "local-file" if self.history_path else "memory"
                    ),
                },
            }
            history_load_error = await self._load_history()
            if history_load_error:
                providers["history"]["available"] = False
                errors.append({"provider": "history", "message": history_load_error})
            try:
                recent_tokens = await self._recent_tokens()
                providers["jupiter"]["available"] = True
            except Exception as exc:
                recent_tokens = []
                errors.append({"provider": "jupiter", "message": str(exc)})

            self._merge_launch_history(recent_tokens, generated_at)
            tokens = self._history_tokens()
            analysis_tokens = self._tokens_due_for_analysis(generated_at)
            observations: list[dict] = []
            enriched_tokens = 0
            wallet_profiles: list[dict] = []
            wallet_candidates: list[str] = []
            successfully_enriched: set[str] = set()
            failed_wallets: set[str] = set()
            if self.birdeye_api_key and analysis_tokens:
                semaphore = asyncio.Semaphore(self.max_concurrency)

                async def enrich(token: dict):
                    async with semaphore:
                        try:
                            return token, await self._top_traders(token), None
                        except Exception as exc:
                            return token, [], str(exc)

                results = await asyncio.gather(*(
                    enrich(token) for token in analysis_tokens
                ))
                for token, traders, error in results:
                    if error:
                        errors.append({"provider": "birdeye", "mint": token["mint"],
                                       "message": error})
                        continue
                    enriched_tokens += 1
                    successfully_enriched.add(token["mint"])
                    for trader in traders:
                        observation = self._observation(token, trader)
                        if observation:
                            observations.append(observation)
                wallet_candidates = self._wallet_candidates(observations)
                wallet_cache = self._history_state.setdefault("wallets", {})
                wallets_to_audit = []
                for wallet in wallet_candidates:
                    cached = wallet_cache.get(wallet)
                    if (
                        isinstance(cached, dict)
                        and generated_at - _integer(cached.get("audited_at"))
                        < self.wallet_cache_seconds
                        and isinstance(cached.get("profile"), dict)
                    ):
                        profile = self._refresh_wallet_profile(
                            cached["profile"], observations
                        )
                        cached["profile"] = profile
                        wallet_profiles.append(profile)
                    else:
                        wallets_to_audit.append(wallet)

                async def audit_wallet(wallet: str):
                    async with semaphore:
                        try:
                            return wallet, await self._wallet_pnl_summary(wallet), None
                        except Exception as exc:
                            return wallet, {}, str(exc)

                audits = await asyncio.gather(*(
                    audit_wallet(wallet) for wallet in wallets_to_audit
                ))
                for wallet, history, error in audits:
                    if error:
                        failed_wallets.add(wallet)
                        errors.append({
                            "provider": "birdeye", "wallet": wallet, "message": error,
                        })
                        continue
                    profile = self._wallet_profile(wallet, history, observations)
                    wallet_profiles.append(profile)
                    wallet_cache[wallet] = {
                        "audited_at": generated_at,
                        "profile": profile,
                    }
                for profile in wallet_profiles:
                    if not profile.get("qualified"):
                        continue
                    # Seed the baseline only when a wallet first enters the
                    # monitored cohort. Adding later Birdeye observations here
                    # could race a Helius delivery and suppress a real alert.
                    if profile["wallet"] in self._history_state.get("wallet_mints", {}):
                        continue
                    self._remember_wallet_mints(
                        profile["wallet"],
                        {
                            item["mint"] for item in observations
                            if item["wallet"] == profile["wallet"]
                        },
                    )
                providers["birdeye"]["available"] = enriched_tokens > 0
            elif self.birdeye_api_key:
                providers["birdeye"]["available"] = True

            blocked_mints = {
                observation["mint"] for observation in observations
                if observation["wallet"] in failed_wallets
            }
            evaluated_tokens = [
                token for token in analysis_tokens
                if token["mint"] in successfully_enriched
                and token["mint"] not in blocked_mints
            ]
            batch_opportunities, _, rejected_by_mint = self._build_opportunities(
                evaluated_tokens, observations, wallet_profiles
            )
            opportunity_by_mint = {
                opportunity["mint"]: opportunity
                for opportunity in batch_opportunities
            }
            profile_by_wallet = {
                profile["wallet"]: profile for profile in wallet_profiles
            }
            token_records = self._history_state.get("tokens", {})
            for token in evaluated_tokens:
                mint = token["mint"]
                record = token_records.get(mint)
                if not isinstance(record, dict):
                    continue
                record["analyzed_at"] = generated_at
                opportunity = opportunity_by_mint.get(mint)
                if opportunity:
                    analysis_fields = {
                        key: opportunity[key] for key in (
                            "opportunity_score", "conviction", "quality_wallet_count",
                            "early_quality_wallet_count", "best_wallet_score", "reasons",
                            "wallet_evidence",
                        )
                    }
                    evidence_wallets = {
                        item["wallet"] for item in opportunity["wallet_evidence"]
                    }
                    record["analysis"] = analysis_fields
                    record["wallets"] = [
                        profile_by_wallet[wallet] for wallet in evidence_wallets
                        if wallet in profile_by_wallet
                    ]
                    record["rejection_reasons"] = []
                else:
                    record["analysis"] = None
                    record["wallets"] = []
                    record["rejection_reasons"] = rejected_by_mint.get(
                        mint, ["no_quality_wallet"]
                    )

            opportunities, wallets, rejection_reasons = self._aggregate_history()
            for profile in wallets:
                if profile["wallet"] in self._history_state.get("wallet_mints", {}):
                    continue
                self._remember_wallet_mints(
                    profile["wallet"],
                    set(profile.get("profitable_memecoin_mints", [])).union(
                        item.get("mint") for item in profile.get("observations", [])
                        if isinstance(item, dict) and item.get("mint")
                    ),
                )
            try:
                providers["helius"] = await self._sync_helius_webhook(wallets)
            except Exception as exc:
                providers["helius"] = {
                    "configured": self.webhook_configured,
                    "available": False,
                    "mode": "enhanced-webhook",
                    "wallets_monitored": 0,
                }
                errors.append({"provider": "helius", "message": str(exc)})

            history_save_error = None
            if not history_load_error:
                history_save_error = await self._save_history()
            if history_save_error:
                providers["history"]["available"] = False
                errors.append({"provider": "history", "message": history_save_error})

            purchases = self._purchase_rows()
            token_records = self._history_state.get("tokens", {})
            analyzed_tokens = sum(
                _integer(record.get("analyzed_at")) > 0
                for record in token_records.values() if isinstance(record, dict)
            )
            structurally_eligible = sum(
                not self._structural_rejections(token) for token in tokens
            )
            payload = {
                "generated_at": generated_at,
                "cache_expires_at": generated_at + self.cache_seconds,
                "read_only": True,
                "providers": providers,
                "summary": {
                    "recent_tokens": len(recent_tokens),
                    "launches_in_window": len(tokens),
                    "history_window_hours": self.history_hours,
                    "history_capacity": self.history_limit,
                    "collection_batch": self.max_tokens,
                    "analyzed_tokens": analyzed_tokens,
                    "pending_tokens": max(0, len(tokens) - analyzed_tokens),
                    "analyzed_this_cycle": len(evaluated_tokens),
                    "structurally_eligible": structurally_eligible,
                    "enriched_tokens": enriched_tokens,
                    "wallet_candidates": len(wallet_candidates),
                    "wallets_evaluated": len(wallet_profiles),
                    "quality_wallets": len(wallets),
                    "monitored_wallets": _integer(
                        providers["helius"].get("wallets_monitored")
                    ),
                    "realized_pnl_usd": round(sum(
                        _number(wallet.get("realized_pnl_usd")) for wallet in wallets
                    ), 2),
                    "purchase_alerts": len(purchases),
                    "purchase_alerts_24h": sum(
                        generated_at - _integer(row.get("purchased_at_unix")) <= 86_400
                        for row in purchases
                    ),
                    "pending_alert_delivery": sum(
                        not _integer(row.get("alert_sent_at")) for row in purchases
                    ),
                    "opportunities": len(opportunities),
                    "rejected_tokens": max(0, analyzed_tokens - len(opportunities)),
                    "early_wallets": sum(wallet["early_buys"] > 0 for wallet in wallets),
                    "robust_wallets": sum(wallet["confidence"] == "robust" for wallet in wallets),
                },
                "wallets": wallets,
                "purchases": purchases,
                "opportunities": opportunities,
                "tokens": tokens,
                "errors": errors[:20],
                "methodology": {
                    "early_window_seconds": 120,
                    "wallet_history_window": "90d",
                    "launch_history_window_hours": self.history_hours,
                    "launch_history_capacity": self.history_limit,
                    "token_batch_per_cycle": self.max_tokens,
                    "wallets_per_cycle": self.max_wallets,
                    "max_concurrency": self.max_concurrency,
                    "reanalyze_seconds": self.reanalyze_seconds,
                    "history_persistent": self.history_persistent,
                    "ranking": (
                        "PnL realizado decrescente entre carteiras com pelo menos "
                        f"{self.min_profitable_memecoins} memecoins distintas e "
                        "PnL realizado positivo"
                    ),
                    "alert_rule": (
                        "primeira compra observada de um mint por carteira ranqueada; "
                        "SWAP/BUY confirmado pela Helius e deduplicado por assinatura"
                    ),
                    "monitor_wallets": self.monitor_wallets,
                    "disqualifying_tags": ["dev", "insider", "bundler"],
                    "minimums": {
                        "liquidity_usd": self.min_liquidity_usd,
                        "token_safety": self.min_token_safety,
                        "opportunity_score": self.min_opportunity_score,
                        "profitable_memecoins": self.min_profitable_memecoins,
                    },
                    "rejection_reasons": rejection_reasons,
                    "entry_delay_is_approximate": True,
                    "history_may_be_incomplete": True,
                },
            }
            self._cache = payload
            self._cache_at = time.time()
            return payload

    async def _quote(self, input_mint: str, output_mint: str, amount: int) -> dict:
        try:
            payload = await self._get_json(
                f"{self.jupiter_base}/swap/v2/order",
                params={"inputMint": input_mint, "outputMint": output_mint,
                        "amount": str(amount)},
                headers=self._jupiter_headers(),
            )
            error_code = payload.get("errorCode") if isinstance(payload, dict) else "invalid"
            out_amount = _integer(payload.get("outAmount")) if isinstance(payload, dict) else 0
            return {
                "available": error_code in (None, 0, "0") and out_amount > 0,
                "in_amount": str(payload.get("inAmount") or amount),
                "out_amount": str(payload.get("outAmount") or "0"),
                "router": payload.get("router"),
                "mode": payload.get("mode"),
                "price_impact_pct": _number(payload.get("priceImpactPct"), default=-1),
                "error_code": error_code,
                "error": payload.get("errorMessage"),
            }
        except Exception as exc:
            return {"available": False, "error": str(exc), "error_code": "upstream"}

    async def routes(self, mint: str, *, amount_sol: float = 0.25) -> dict:
        if not BASE58_ADDRESS.fullmatch(mint):
            raise ValueError("Mint Solana inválido")
        amount_sol = max(0.01, min(5.0, float(amount_sol)))
        snapshot = await self.snapshot()
        token = next((row for row in snapshot["tokens"] if row["mint"] == mint), None)
        if token is None:
            payload = await self._get_json(
                f"{self.jupiter_base}/tokens/v2/search",
                params={"query": mint}, headers=self._jupiter_headers(),
            )
            if not isinstance(payload, list) or not payload:
                raise ValueError("Token não localizado na Jupiter")
            token = self._normalize_token(payload[0])
        buy_amount = max(1, round(amount_sol * 1_000_000_000))
        sell_amount = min(10**18, max(1, 10 ** token["decimals"]))
        buy, sell = await asyncio.gather(
            self._quote(WSOL_MINT, mint, buy_amount),
            self._quote(mint, WSOL_MINT, sell_amount),
        )
        return {
            "mint": mint,
            "symbol": token["symbol"],
            "amount_sol": amount_sol,
            "buy": buy,
            "sell": sell,
            "tradable": bool(buy["available"] and sell["available"]),
            "read_only": True,
            "note": "Cotações sem taker: nenhuma transação foi criada ou executada.",
        }
