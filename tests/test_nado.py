import httpx

from market_sentinel.models import AssetClass, Market
from market_sentinel.venues.nado import NadoAdapter


def market():
    return Market("nado", "BTC-PERP_USDT0", "BTC", "USDT0", "PERP",
                  AssetClass.CRYPTO, metadata={"product_id": 2})


async def test_nado_empty_archive_is_a_valid_empty_result():
    def handler(request):
        return httpx.Response(200, json={"candlesticks": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = NadoAdapter(client, frozenset({"BTC"}))
        adapter.request_interval = 0
        assert await adapter.candles(market(), "1h") == []


async def test_nado_retries_rate_limit_with_shared_cooldown():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"candlesticks": [{
            "timestamp": 1_700_000_000, "open_x18": 10 * 10**18,
            "high_x18": 12 * 10**18, "low_x18": 9 * 10**18,
            "close_x18": 11 * 10**18, "volume": 2 * 10**18,
        }]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = NadoAdapter(client, frozenset({"BTC"}))
        adapter.request_interval = 0
        rows = await adapter.candles(market(), "1h")

    assert calls == 2
    assert rows[0].close == 11
