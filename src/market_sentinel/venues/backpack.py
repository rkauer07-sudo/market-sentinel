import asyncio
import time
from datetime import datetime
from ..classify import classify
from ..models import Candle, Market
from .base import VenueAdapter


class BackpackAdapter(VenueAdapter):
    name = "backpack"
    base_url = "https://api.backpack.exchange/api/v1"

    async def discover_markets(self) -> list[Market]:
        market_r, ticker_r, mark_r = await asyncio.gather(
            self.client.get(f"{self.base_url}/markets"),
            self.client.get(f"{self.base_url}/tickers", params={"interval": "1d"}),
            self.client.get(f"{self.base_url}/markPrices"))
        for response in (market_r, ticker_r, mark_r): response.raise_for_status()
        tickers = {x["symbol"]: x for x in ticker_r.json()}
        marks = {x["symbol"]: x for x in mark_r.json()}
        result = []
        for raw in market_r.json():
            market_type = str(raw.get("marketType", "")).upper()
            if market_type not in {"SPOT", "PERP", "IPERP"}: continue
            base = str(raw.get("baseSymbol") or raw.get("symbol", "").split("_")[0])
            asset_class = classify(base, raw, self.core_assets)
            if asset_class is None: continue
            symbol, ticker, mark = raw["symbol"], tickers.get(raw["symbol"], {}), marks.get(raw["symbol"], {})
            result.append(Market(self.name, symbol, base, str(raw.get("quoteSymbol", "USDC")), market_type,
                asset_class, float(ticker.get("quoteVolume") or 0), maybe_float(mark.get("fundingRate")), None, raw))
        return result

    async def candles(self, market: Market, timeframe: str, limit: int = 300) -> list[Candle]:
        seconds = {"1h": 3600, "4h": 14400, "1d": 86400}[timeframe]
        end = int(time.time())
        response = await self.client.get(f"{self.base_url}/klines", params={
            "symbol": market.symbol, "interval": timeframe, "startTime": end - seconds * limit, "endTime": end})
        response.raise_for_status()
        return [Candle(timestamp(x["start"]), float(x["open"]), float(x["high"]), float(x["low"]),
            float(x["close"]), float(x.get("volume") or 0), float(x.get("quoteVolume") or 0)) for x in response.json()]


def maybe_float(value):
    try: return float(value)
    except (TypeError, ValueError): return None


def timestamp(value):
    if isinstance(value, (int, float)): return int(value / 1000 if value > 10_000_000_000 else value)
    return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp())

