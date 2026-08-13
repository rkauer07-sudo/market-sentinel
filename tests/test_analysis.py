from market_sentinel.analysis import analyze, btc_regime, confirmed_breakout_retest
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


def test_breakout_close_is_not_an_entry_before_retest():
    rows = [Candle(i, 99, 100, 98, 99, 100) for i in range(20)]
    rows += [Candle(20, 99, 103, 99, 102, 200)]
    assert confirmed_breakout_retest(rows, [100], "LONG", 2) is None


def test_long_entry_requires_later_closed_retest_rejection():
    rows = [Candle(i, 99, 100, 98, 99, 100) for i in range(20)]
    rows += [Candle(20, 99, 103, 99, 102, 200), Candle(21, 102, 104, 101, 103, 100),
             Candle(22, 101, 103, 99.8, 102.5, 120)]
    assert confirmed_breakout_retest(rows, [100], "LONG", 2) == 100


def test_retest_without_rejection_is_not_confirmed():
    rows = [Candle(i, 99, 100, 98, 99, 100) for i in range(20)]
    rows += [Candle(20, 99, 103, 99, 102, 200), Candle(21, 102, 104, 101, 103, 100),
             Candle(22, 102, 102.2, 99.8, 100.1, 120)]
    assert confirmed_breakout_retest(rows, [100], "LONG", 2) is None


def test_retest_on_first_candle_is_too_early():
    rows = [Candle(i, 99, 100, 98, 99, 100) for i in range(20)]
    rows += [Candle(20, 99, 103, 99, 102, 200), Candle(21, 101, 103, 99.8, 102.5, 120)]
    assert confirmed_breakout_retest(rows, [100], "LONG", 2) is None


def test_retest_after_third_candle_is_too_late():
    rows = [Candle(i, 99, 100, 98, 99, 100) for i in range(20)]
    rows += [Candle(20, 99, 103, 99, 102, 200)]
    rows += [Candle(i, 102, 104, 101, 103, 100) for i in range(21, 24)]
    rows += [Candle(24, 101, 103, 99.8, 102.5, 120)]
    assert confirmed_breakout_retest(rows, [100], "LONG", 2) is None
