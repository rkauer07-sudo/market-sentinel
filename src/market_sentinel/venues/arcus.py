import time

from ..classify import classify
from ..models import Candle, Market
from .base import VenueAdapter


class ArcusAdapter(VenueAdapter):
    """Read-only adapter for Arcus public perpetual-market data."""

    name = "arcus"
    base_url = "https://api.arcus.xyz/v1"

    async def discover_markets(self) -> list[Market]:
        response = await self.client.get(f"{self.base_url}/markets")
        response.raise_for_status()
        result = []
        for raw in response.json().get("markets", []):
            if str(raw.get("status", "")).upper() != "ONLINE":
                continue
            base = str(raw.get("baseAsset") or "").upper()
            category = str(raw.get("category") or "").lower()
            if category == "equities":
                category = "stocks"
            enriched = {**raw, "category": category}
            asset_class = classify(base, enriched, self.core_assets)
            if asset_class is None:
                continue
            result.append(Market(
                self.name, str(raw["marketDisplayName"]), base,
                str(raw.get("quoteAsset") or "USD"), str(raw.get("type") or "PERPETUAL"),
                asset_class, float(raw.get("volume24hNotional") or 0),
                _float_or_none(raw.get("fundingRate")), _notional_open_interest(raw), enriched,
            ))
        return result

    async def candles(self, market: Market, timeframe: str, limit: int = 300) -> list[Candle]:
        response = await self.client.get(f"{self.base_url}/candles", params={
            "market": market.symbol, "timeframe": timeframe,
            "to": int(time.time() * 1_000_000), "countback": min(limit, 1500),
        })
        response.raise_for_status()
        return [Candle(
            int(row["openTime"]) // 1_000_000,
            float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]),
            float(row.get("volume") or 0), float(row.get("notionalVolume") or 0),
        ) for row in response.json().get("candles", [])]


def _float_or_none(value):
    try: return float(value)
    except (TypeError, ValueError): return None


def _notional_open_interest(raw: dict) -> float | None:
    size, mark = _float_or_none(raw.get("openInterest")), _float_or_none(raw.get("markPrice"))
    return size * mark if size is not None and mark is not None else None
