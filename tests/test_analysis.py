from market_sentinel.analysis import analyze, btc_regime
from market_sentinel.models import AssetClass, Candle, Market


def candles(count=230, breakout=True):
    rows = []
    for i in range(count):
        close = 100 + i * 0.1
        rows.append(Candle(1_700_000_000 + i * 3600, close - .2, close + .5, close - .5, close, 100))
    if breakout:
        rows[-2] = Candle(rows[-2].timestamp, 122, 130, 121.8, 129, 300)
    return rows


def test_btc_regime_is_bullish():
    assert btc_regime(candles()) is True


def test_analysis_never_uses_open_candle():
    rows = candles(breakout=False)
    rows[-1] = Candle(rows[-1].timestamp, 1, 1000, 0.1, 999, 999999)
    market = Market("test", "BTC", "BTC", "USDC", "PERP", AssetClass.CRYPTO, 1_000_000)
    cfg = {"min_candles": 210, "min_risk_reward": 2, "min_score": 70,
           "min_daily_quote_volume": 500000, "pivot_window": 3, "zone_tolerance_atr": .35}
    assert analyze(market, "1h", rows, True, cfg) is None

