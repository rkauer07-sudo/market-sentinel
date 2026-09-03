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


def test_retest_requires_confirmation_volume():
    rows = [Candle(i, 99, 100, 98, 99, 100) for i in range(20)]
    rows += [Candle(20, 99, 103, 99, 102, 200), Candle(21, 102, 104, 101, 103, 100),
             Candle(22, 101, 103, 99.8, 102.5, 80)]
    assert confirmed_breakout_retest(rows, [100], "LONG", 2) is None


def test_retest_requires_decisive_rejection_body():
    rows = [Candle(i, 99, 100, 98, 99, 100) for i in range(20)]
    rows += [Candle(20, 99, 103, 99, 102, 200), Candle(21, 102, 104, 101, 103, 100),
             Candle(22, 102.3, 103, 99.8, 102.5, 130)]
    assert confirmed_breakout_retest(rows, [100], "LONG", 2) is None


from market_sentinel.analysis import pullback_continuation


def _pullback_closed(direction="LONG"):
    """A long uptrend, then a 3-candle pullback into the MA20 zone, then a
    decisive reclaim candle as the last closed candle."""
    rows = [Candle(1_700_000_000 + i * 3600, 99, 100, 98, 99.5, 100) for i in range(20)]
    if direction == "LONG":
        rows += [
            Candle(1, 101, 101.2, 99.2, 99.4, 90),    # dip toward MA20
            Candle(2, 99.4, 100.0, 98.9, 99.2, 95),   # holds the zone
            Candle(3, 99.2, 100.1, 99.0, 99.6, 95),   # base
            Candle(4, 99.6, 103.4, 99.5, 103.2, 260),  # decisive reclaim (closed[-1])
        ]
    else:
        rows += [
            Candle(1, 99, 100.8, 99, 100.6, 90),      # bounce toward MA20
            Candle(2, 100.6, 101.1, 100.0, 100.8, 95),
            Candle(3, 100.8, 101.0, 100.2, 100.4, 95),
            Candle(4, 100.4, 100.5, 96.8, 96.9, 260),  # decisive rejection (closed[-1])
        ]
    return rows


def test_pullback_detects_long_continuation():
    closed = _pullback_closed("LONG")
    result = pullback_continuation(closed, ma20=100, ma50=95, current_atr=2,
                                   trend_up=True, trend_down=False, cfg={})
    assert result is not None
    direction, entry, stop = result
    assert direction == "LONG"
    assert entry == 103.2
    assert stop < 99.2  # below the pullback low and MA50, minus an ATR buffer


def test_pullback_detects_short_continuation():
    closed = _pullback_closed("SHORT")
    result = pullback_continuation(closed, ma20=100, ma50=105, current_atr=2,
                                   trend_up=False, trend_down=True, cfg={})
    assert result is not None
    direction, entry, stop = result
    assert direction == "SHORT"
    assert entry == 96.9
    assert stop > 100.8  # above the pullback high and MA50, plus an ATR buffer


def test_pullback_requires_an_aligned_trend():
    closed = _pullback_closed("LONG")
    assert pullback_continuation(closed, ma20=100, ma50=95, current_atr=2,
                                 trend_up=False, trend_down=False, cfg={}) is None


def test_pullback_ignores_a_weak_reclaim_body():
    closed = _pullback_closed("LONG")
    # Replace the reclaim with a doji-like candle that barely closes up.
    closed[-1] = Candle(closed[-1].timestamp, 99.6, 103.4, 99.5, 99.7, 260)
    assert pullback_continuation(closed, ma20=100, ma50=95, current_atr=2,
                                 trend_up=True, trend_down=False, cfg={}) is None


def test_pullback_requires_price_to_reach_the_ma20_zone():
    closed = _pullback_closed("LONG")
    # A pullback that never comes near MA20 (all lows far above the zone).
    assert pullback_continuation(closed, ma20=50, ma50=45, current_atr=2,
                                 trend_up=True, trend_down=False, cfg={}) is None


def test_pullback_can_be_disabled_by_config():
    closed = _pullback_closed("LONG")
    cfg = {"enable_pullback_continuation": True}
    assert pullback_continuation(closed, ma20=100, ma50=95, current_atr=2,
                                 trend_up=True, trend_down=False, cfg=cfg) is not None


def _uptrend_with_pullback():
    rows = []
    price = 100.0
    for i in range(232):
        price *= 1.004
        rows.append(Candle(1_700_000_000 + i * 3600, price * 0.999,
                           price * 1.002, price * 0.997, price, 100))
    base = rows[-6].close
    rows[-5] = Candle(rows[-5].timestamp, base, base * 1.001, base * 0.985, base * 0.988, 90)
    rows[-4] = Candle(rows[-4].timestamp, base * 0.988, base * 0.99, base * 0.978, base * 0.982, 95)
    rows[-3] = Candle(rows[-3].timestamp, base * 0.982, base * 0.99, base * 0.977, base * 0.985, 95)
    rc_o = base * 0.985
    rows[-2] = Candle(rows[-2].timestamp, rc_o, base * 1.02, rc_o * 0.999, base * 1.015, 260)
    rows[-1] = Candle(rows[-1].timestamp, base * 1.015, base * 1.02, base * 1.01, base * 1.016, 50)
    return rows


_ANALYZE_CFG = {
    "min_candles": 210, "min_risk_reward": 2.0, "min_score": 82, "strong_score": 90,
    "min_confirmations": 6, "min_breakout_volume_ratio": 1.3, "min_retest_volume_ratio": 1.05,
    "pivot_window": 3, "zone_tolerance_atr": 0.35, "min_daily_quote_volume": 1_000_000,
    "retest_min_bars": 2, "retest_max_bars": 3, "pullback_zone_atr": 0.6, "pullback_lookback": 3,
}


def test_analyze_reaches_pullback_path_only_when_enabled():
    market = Market("test", "SOL", "SOL", "USDC", "PERP", AssetClass.CRYPTO, 5_000_000)
    enabled, disabled = {}, {}
    analyze(market, "4h", _uptrend_with_pullback(), True,
            {**_ANALYZE_CFG, "enable_pullback_continuation": True}, enabled)
    analyze(market, "4h", _uptrend_with_pullback(), True,
            {**_ANALYZE_CFG, "enable_pullback_continuation": False}, disabled)
    # With the setup enabled the candidate flows into the shared quality gates
    # (here vibe rejects it); disabling it falls straight back to no setup.
    assert enabled["reason"] != "no_confirmed_setup"
    assert disabled["reason"] == "no_confirmed_setup"
