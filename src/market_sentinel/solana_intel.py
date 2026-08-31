from __future__ import annotations

import asyncio
import math
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from statistics import median
from typing import Any

import httpx


WSOL_MINT = "So11111111111111111111111111111111111111112"
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
        self.max_tokens = max(1, min(30, _integer(os.getenv("SOLANA_INTEL_MAX_TOKENS"), 12)))
        self.cache_seconds = max(
            30, min(3600, _integer(os.getenv("SOLANA_INTEL_CACHE_SECONDS"), 300))
        )
        self._cache: dict | None = None
        self._cache_at = 0.0
        self._lock = asyncio.Lock()

    def _jupiter_headers(self) -> dict[str, str]:
        return {"x-api-key": self.jupiter_api_key} if self.jupiter_api_key else {}

    @property
    def configured(self) -> dict[str, bool]:
        return {
            "jupiter": bool(self.jupiter_api_key),
            "birdeye": bool(self.birdeye_api_key),
            "helius": bool(self.helius_api_key),
        }

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

    def _rank_wallets(self, observations: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for observation in observations:
            grouped[observation["wallet"]].append(observation)
        ranked = []
        for address, rows in grouped.items():
            samples = len({row["mint"] for row in rows})
            wins = sum(row["total_pnl_usd"] > 0 for row in rows)
            delays = [row["entry_delay_seconds"] for row in rows
                      if row["entry_delay_seconds"] is not None]
            early_count = sum(delay <= 120 for delay in delays)
            all_tags = sorted({tag for row in rows for tag in row["tags"]})
            realized = sum(row["realized_pnl_usd"] for row in rows)
            total = sum(row["total_pnl_usd"] for row in rows)
            confidence = _wilson_lower_bound(wins, samples)
            early_ratio = early_count / len(delays) if delays else 0
            accuracy_points = confidence * 45
            early_points = early_ratio * 20
            profit_points = min(20, math.log1p(max(0, realized)) / math.log(10_001) * 20)
            sample_points = min(15, samples / 12 * 15)
            penalty = 0
            if "bundler" in all_tags:
                penalty += 28
            if "dev" in all_tags or "insider" in all_tags:
                penalty += 45
            score = round(max(0, min(100,
                accuracy_points + early_points + profit_points + sample_points - penalty)))
            ranked.append({
                "wallet": address,
                "score": score,
                "tokens_traded": samples,
                "wins": wins,
                "win_rate_pct": round(wins / samples * 100, 1) if samples else 0,
                "confidence_win_rate_pct": round(confidence * 100, 1),
                "realized_pnl_usd": round(realized, 2),
                "total_pnl_usd": round(total, 2),
                "early_buys": early_count,
                "median_entry_seconds": round(median(delays), 1) if delays else None,
                "earliest_entry_seconds": min(delays) if delays else None,
                "tags": all_tags,
                "risk_penalty": penalty,
                "confidence": "robust" if samples >= 8 else "building" if samples >= 3 else "insufficient",
                "observations": sorted(rows, key=lambda item: (
                    item["entry_delay_seconds"] is None,
                    item["entry_delay_seconds"] or 10**9,
                ))[:12],
                "solscan_url": f"https://solscan.io/account/{address}",
            })
        return sorted(ranked, key=lambda row: (
            row["risk_penalty"] > 0, -row["score"], -row["tokens_traded"],
        ))[:50]

    async def snapshot(self, *, force: bool = False) -> dict:
        now = time.time()
        if not force and self._cache and now - self._cache_at < self.cache_seconds:
            return self._cache
        async with self._lock:
            now = time.time()
            if not force and self._cache and now - self._cache_at < self.cache_seconds:
                return self._cache
            errors: list[dict] = []
            providers = {
                "jupiter": {"configured": bool(self.jupiter_api_key), "available": False,
                            "mode": "api-key" if self.jupiter_api_key else "keyless"},
                "birdeye": {"configured": bool(self.birdeye_api_key), "available": False,
                            "mode": "api-key-required"},
                "helius": {"configured": bool(self.helius_api_key), "available": None,
                           "mode": "reserved-for-wallet-audit"},
            }
            try:
                tokens = await self._recent_tokens()
                providers["jupiter"]["available"] = True
            except Exception as exc:
                tokens = []
                errors.append({"provider": "jupiter", "message": str(exc)})

            observations: list[dict] = []
            enriched_tokens = 0
            if self.birdeye_api_key and tokens:
                semaphore = asyncio.Semaphore(2)

                async def enrich(token: dict):
                    async with semaphore:
                        try:
                            return token, await self._top_traders(token), None
                        except Exception as exc:
                            return token, [], str(exc)

                results = await asyncio.gather(*(enrich(token) for token in tokens))
                for token, traders, error in results:
                    if error:
                        errors.append({"provider": "birdeye", "mint": token["mint"],
                                       "message": error})
                        continue
                    enriched_tokens += 1
                    for trader in traders:
                        observation = self._observation(token, trader)
                        if observation:
                            observations.append(observation)
                providers["birdeye"]["available"] = enriched_tokens > 0

            wallets = self._rank_wallets(observations)
            generated_at = int(time.time())
            payload = {
                "generated_at": generated_at,
                "cache_expires_at": generated_at + self.cache_seconds,
                "read_only": True,
                "providers": providers,
                "summary": {
                    "recent_tokens": len(tokens),
                    "enriched_tokens": enriched_tokens,
                    "wallet_candidates": len(wallets),
                    "early_wallets": sum(wallet["early_buys"] > 0 for wallet in wallets),
                    "robust_wallets": sum(wallet["confidence"] == "robust" for wallet in wallets),
                },
                "wallets": wallets,
                "tokens": tokens,
                "errors": errors[:20],
                "methodology": {
                    "early_window_seconds": 120,
                    "ranking": "Wilson ajustado + PnL realizado + recorrência + entrada precoce",
                    "disqualifying_tags": ["dev", "insider", "bundler"],
                    "entry_delay_is_approximate": True,
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
