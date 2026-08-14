from market_sentinel.vibe_indicators import bollinger, ema, macd, technical_snapshot, wilder_rsi


def test_vibe_indicators_are_computed_without_external_dependencies():
    values = [100 + index * .2 + (index % 4) * .05 for index in range(80)]
    assert ema(values, 20) is not None
    assert wilder_rsi(values) is not None
    assert macd(values) is not None
    assert bollinger(values) is not None
    assert technical_snapshot(values) is not None


def test_vibe_gate_rejects_exhausted_long_move():
    values = [100 + index * .1 for index in range(70)] + [120, 130, 145]
    snapshot = technical_snapshot(values)
    assert snapshot is not None
    assert snapshot.confirms("LONG", values[-1]) is False


def test_vibe_gate_requires_directional_macd_alignment():
    rising = [100 + index * .08 + ((index % 6) - 3) * .03 for index in range(100)]
    snapshot = technical_snapshot(rising)
    assert snapshot is not None
    wrong_direction = "SHORT" if snapshot.macd_histogram > 0 else "LONG"
    assert snapshot.confirms(wrong_direction, rising[-1]) is False
