import httpx

from market_sentinel.models import AssetClass
from market_sentinel.venues.arcus import ArcusAdapter


async def test_arcus_discovers_supported_classes():
    payload = {"markets": [
        {"marketDisplayName": "BTC-USD", "baseAsset": "BTC", "quoteAsset": "USD",
         "status": "ONLINE", "type": "PERPETUAL", "category": "CRYPTO",
         "volume24hNotional": "100", "markPrice": "10", "openInterest": "2"},
        {"marketDisplayName": "AAPL-USD", "baseAsset": "AAPL", "quoteAsset": "USD",
         "status": "ONLINE", "type": "PERPETUAL", "category": "EQUITIES",
         "volume24hNotional": "200", "markPrice": "20", "openInterest": "3"},
        {"marketDisplayName": "XAU-USD", "baseAsset": "XAU", "quoteAsset": "USD",
         "status": "ONLINE", "type": "PERPETUAL", "category": "COMMODITIES",
         "volume24hNotional": "300", "markPrice": "30", "openInterest": "4"},
        {"marketDisplayName": "SPY-USD", "baseAsset": "SPY", "quoteAsset": "USD",
         "status": "ONLINE", "type": "PERPETUAL", "category": "INDICES"},
    ]}

    def handler(request):
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rows = await ArcusAdapter(client, frozenset({"BTC"})).discover_markets()

    assert [(row.base, row.asset_class) for row in rows] == [
        ("BTC", AssetClass.CRYPTO), ("AAPL", AssetClass.STOCK),
        ("XAU", AssetClass.COMMODITY), ("SPY", AssetClass.INDEX)]
    assert rows[1].open_interest == 60


async def test_arcus_candles_convert_microseconds():
    payload = {"candles": [{"openTime": 1_700_000_000_000_000, "open": "10", "high": "12",
                            "low": "9", "close": "11", "volume": "2", "notionalVolume": "22"}]}

    def handler(request):
        assert request.url.params["timeframe"] == "4h"
        assert request.url.params["countback"] == "300"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = ArcusAdapter(client, frozenset({"BTC"}))
        from market_sentinel.models import Market
        market = Market("arcus", "BTC-USD", "BTC", "USD", "PERPETUAL", AssetClass.CRYPTO)
        rows = await adapter.candles(market, "4h")

    assert rows[0].timestamp == 1_700_000_000
    assert rows[0].quote_volume == 22
