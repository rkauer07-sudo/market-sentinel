from ..classify import classify
from ..models import Candle, Market
from .base import VenueAdapter


class NadoAdapter(VenueAdapter):
    name = "nado"
    gateway = "https://gateway.prod.nado.xyz/v2"
    archive = "https://archive.prod.nado.xyz/v1"

    async def discover_markets(self) -> list[Market]:
        pairs_response, assets_response = await __import__("asyncio").gather(
            self.client.get(f"{self.gateway}/pairs"), self.client.get(f"{self.gateway}/assets"))
        pairs_response.raise_for_status(); assets_response.raise_for_status()
        rows = pairs_response.json(); assets = {x["product_id"]: x for x in assets_response.json()}
        result = []
        for raw in rows:
            asset = assets.get(raw.get("product_id"), {})
            combined = {**raw, **asset}
            symbol = str(raw.get("ticker_id") or asset.get("ticker_id") or "")
            base = str(raw.get("base") or asset.get("symbol") or "").replace("-PERP", "")
            asset_class = classify(base, combined, self.core_assets)
            status = str(raw.get("trading_status", "live"))
            if asset_class is None or status not in {"live", "trading", "active"}: continue
            result.append(Market(self.name, symbol, base,
                str(raw.get("quote") or raw.get("quote_symbol") or "USDT0"),
                str(raw.get("type") or raw.get("product_type") or "PERP").upper(), asset_class,
                float(raw.get("quote_volume_24h") or raw.get("volume_24h") or 0),
                maybe_float(raw.get("funding_rate")), None, {**combined, "product_id": raw.get("product_id")}))
        return result

    async def candles(self, market: Market, timeframe: str, limit: int = 300) -> list[Candle]:
        granularity = {"1h": 3600, "4h": 14400, "1d": 86400}[timeframe]
        response = await self.client.post(self.archive, json={"candlesticks": {
            "product_id": market.metadata["product_id"], "granularity": granularity, "limit": min(limit, 500)}})
        response.raise_for_status()
        rows = response.json().get("candlesticks", [])
        result = [Candle(integer(x, "timestamp"), scaled(x, "open_x18"), scaled(x, "high_x18"),
            scaled(x, "low_x18"), scaled(x, "close_x18"), scaled(x, "volume")) for x in rows]
        return sorted(result, key=lambda x: x.timestamp)


def maybe_float(value):
    try: return float(value)
    except (TypeError, ValueError): return None


def number(row, *keys, default=None):
    for key in keys:
        if key in row: return float(row[key])
    if default is not None: return float(default)
    raise KeyError(keys[0])


def integer(row, *keys):
    value = int(next(row[k] for k in keys if k in row))
    return int(value / 1000 if value > 10_000_000_000 else value)


def scaled(row, key): return float(row[key]) / 1e18
