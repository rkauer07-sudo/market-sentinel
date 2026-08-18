from market_sentinel.web import live_resolution


def signal(direction="LONG"):
    return {
        "id": 7, "symbol": "BTC", "direction": direction,
        "stop": 95 if direction == "LONG" else 105,
        "target1": 102 if direction == "LONG" else 98,
        "target2": 104 if direction == "LONG" else 96,
        "target3": None, "target4": None, "target5": None,
        "highest_target_hit": 0,
    }


def test_live_resolution_waits_through_intermediate_target():
    assert live_resolution(signal(), 103) is None


def test_live_resolution_closes_at_final_target():
    assert live_resolution(signal(), 104)["status"] == "SUCCESS_T2"
    assert live_resolution(signal("SHORT"), 96)["status"] == "SUCCESS_T2"


def test_live_resolution_classifies_stop_from_persisted_progress():
    item = signal(); item["highest_target_hit"] = 1
    assert live_resolution(item, 95)["status"] == "SUCCESS_T1"
    item["highest_target_hit"] = 0
    assert live_resolution(item, 95)["status"] == "FAILED"
