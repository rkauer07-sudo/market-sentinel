import asyncio
import time
from ..classify import classify
from ..models import Candle, Market
from .base import VenueAdapter


class HyperliquidAdapter(VenueAdapter):
    name = "hyperliquid"
    url = "https://api.hyperliquid.xyz/info"

    async def _post(self, body):
        response = await self.client.post(self.url, json=body)
        response.raise_for_status()
        return response.json()

    async def discover_markets(self) -> list[Market]:
        dex_rows, category_rows = await asyncio.gather(
            self._post({"type": "perpDexs"}), self._post({"type": "perpCategories"}))
        categories = {name: category for name, category in category_rows}
        dexes = [""] + [x["name"] for x in dex_rows if x and x.get("name")]
        payloads = await asyncio.gather(*(self._post({"type": "metaAndAssetCtxs", "dex": d}) for d in dexes), return_exceptions=True)
        result = []
        for dex, payload in zip(dexes, payloads):
            if isinstance(payload, Exception) or not isinstance(payload, list) or len(payload) < 2: continue
            meta, contexts = payload
            for raw, ctx in zip(meta.get("universe", []), contexts):
                coin = str(raw.get("name", ""))
                symbol = coin if not dex or coin.startswith(f"{dex}:") else f"{dex}:{coin}"
                combined = {**raw, **ctx, "dex": dex, "category": categories.get(symbol, "")}
                asset_class = classify(symbol, combined, self.core_assets)
                if asset_class is None: continue
                mark = float(ctx.get("markPx") or 0)
                result.append(Market(self.name, symbol, coin, "USDC", "PERP", asset_class,
                    float(ctx.get("dayNtlVlm") or 0), maybe_float(ctx.get("funding")),
                    float(ctx.get("openInterest") or 0) * mark, combined))
        return result

    async def candles(self, market: Market, timeframe: str, limit: int = 300) -> list[Candle]:
        duration = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}[timeframe]
        end = int(time.time() * 1000)
        rows = await self._post({"type": "candleSnapshot", "req": {
            "coin": market.symbol, "interval": timeframe, "startTime": end - duration * limit, "endTime": end}})
        return [Candle(int(x["t"] / 1000), float(x["o"]), float(x["h"]), float(x["l"]),
            float(x["c"]), float(x.get("v") or 0), float(x.get("v") or 0) * float(x["c"])) for x in rows]


def maybe_float(value):
    try: return float(value)
    except (TypeError, ValueError): return None
