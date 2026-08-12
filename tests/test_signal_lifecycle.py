from market_sentinel.models import AssetClass, Candle, Market, Opportunity
from market_sentinel.storage import Store


def opportunity(direction="LONG"):
    market = Market("test", "BTC", "BTC", "USDC", "PERP", AssetClass.CRYPTO, 1_000_000)
    if direction == "LONG":
        entry, stop, target1, target2 = 100, 95, 110, 120
    else:
        entry, stop, target1, target2 = 100, 105, 90, 80
    return Opportunity(market, "1h", direction, "teste", entry, stop, target1, target2,
                       2, 80, ["teste"], [], 100)


def test_signal_stays_active_when_setup_disappears(tmp_path):
    store = Store(str(tmp_path / "signals.db")); op = opportunity()
    _, created = store.register_signal(op)
    assert created and store.signals("ACTIVE")[0]["status"] == "ACTIVE"
    # No reconcile call represents a subsequent scan where the setup no longer qualifies.
    assert len(store.signals("ACTIVE")) == 1
    store.close()


def test_target_resolves_signal_and_creates_visual_event(tmp_path):
    store = Store(str(tmp_path / "signals.db")); op = opportunity(); store.register_signal(op)
    candles = [Candle(100, 100, 102, 99, 101, 1), Candle(200, 101, 111, 100, 109, 1),
               Candle(300, 109, 112, 108, 111, 1)]
    resolved = store.reconcile(op.market, "1h", candles, 24)
    assert resolved[0]["status"] == "SUCCESS_T1"
    assert store.events()[0]["event_type"] == "SUCCESS_T1"
    store.close()


def test_same_candle_stop_and_target_is_conservative(tmp_path):
    store = Store(str(tmp_path / "signals.db")); op = opportunity(); store.register_signal(op)
    candles = [Candle(100, 100, 102, 99, 101, 1), Candle(200, 101, 112, 94, 106, 1),
               Candle(300, 106, 107, 105, 106, 1)]
    assert store.reconcile(op.market, "1h", candles, 24)[0]["status"] == "FAILED"
    store.close()


def test_forming_candle_stop_closes_signal_immediately(tmp_path):
    store = Store(str(tmp_path / "signals.db")); op = opportunity(); store.register_signal(op)
    candles = [Candle(100, 100, 102, 99, 101, 1),
               Candle(200, 101, 103, 100, 102, 1),
               Candle(300, 102, 103, 94, 96, 1)]  # current/forming candle
    resolved = store.reconcile(op.market, "1h", candles, 24)
    assert resolved[0]["status"] == "FAILED"
    assert store.signals("ACTIVE") == []
    store.close()
