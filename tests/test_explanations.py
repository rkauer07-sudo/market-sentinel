from market_sentinel.explanations import explain_candidate


def test_breakout_explanation_is_simple_and_cautious():
    explanation = explain_candidate({
        "scenario": "Possível rompimento de resistência",
        "direction": "LONG",
        "timeframe": "4h",
        "trigger_price": 105,
        "invalidation_price": 101,
        "target": 113,
        "readiness": 82,
    })
    assert "Ainda não houve rompimento" in explanation["summary"]
    assert "fechamento acima" in explanation["watch_for"]
    assert "não confirmado" in explanation["stage"]


def test_short_explanation_states_invalidation_side():
    explanation = explain_candidate({
        "scenario": "Possível perda de suporte",
        "direction": "SHORT",
        "timeframe": "1h",
        "trigger_price": 95,
        "invalidation_price": 99,
        "target": 87,
        "readiness": 74,
    })
    assert "acima de 99" in explanation["avoid_if"]
    assert "não recuperar" in explanation["summary"]
