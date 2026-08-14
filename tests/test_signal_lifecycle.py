from market_sentinel.models import AssetClass, Candle, Market, Opportunity
from market_sentinel.storage import Store
from market_sentinel.analysis import fibonacci_targets


def opportunity(direction="LONG"):
    market = Market("test", "BTC", "BTC", "USDC", "PERP", AssetClass.CRYPTO, 1_000_000)
    if direction == "LONG":
        entry, stop = 100, 95
    else:
        entry, stop = 100, 105
    targets = fibonacci_targets(entry, stop, direction)
    return Opportunity(market, "1h", direction, "teste", entry, stop, *targets,
                       2.618, 80, ["teste"], [], 100)


def test_fibonacci_targets_for_long_and_short():
    assert fibonacci_targets(100, 95, "LONG") == (105, 106.36, 108.09, 110, 113.09)
    assert fibonacci_targets(100, 105, "SHORT") == (95, 93.64, 91.91, 90, 86.91)


def test_signal_stays_active_when_setup_disappears(tmp_path):
    store = Store(str(tmp_path / "signals.db")); op = opportunity()
    _, created = store.register_signal(op)
    assert created and store.signals("ACTIVE")[0]["status"] == "ACTIVE"
    # No reconcile call represents a subsequent scan where the setup no longer qualifies.
    assert len(store.signals("ACTIVE")) == 1
    store.close()


def test_intermediate_target_is_logged_but_signal_stays_active(tmp_path):
    store = Store(str(tmp_path / "signals.db")); op = opportunity(); store.register_signal(op)
    candles = [Candle(100, 100, 102, 99, 101, 1), Candle(200, 101, 105.5, 100, 105, 1)]
    resolved = store.reconcile(op.market, "1h", candles)
    assert resolved == []
    assert store.signals("ACTIVE")[0]["highest_target_hit"] == 1
    assert store.events()[0]["event_type"] == "TARGET_T1"
    store.close()


def test_same_candle_target_counts_as_success_even_if_stop_is_also_hit(tmp_path):
    store = Store(str(tmp_path / "signals.db")); op = opportunity(); store.register_signal(op)
    candles = [Candle(100, 100, 102, 99, 101, 1), Candle(200, 101, 111, 94, 106, 1),
               Candle(300, 106, 107, 105, 106, 1)]
    resolved = store.reconcile(op.market, "1h", candles)[0]
    assert resolved["status"] == "SUCCESS_T4"
    assert "Bateu alvo 4" in resolved["resolution_reason"]
    store.close()


def test_highest_fibonacci_target_hit_is_recorded(tmp_path):
    store = Store(str(tmp_path / "signals.db")); op = opportunity(); store.register_signal(op)
    candles = [Candle(100, 100, 121, 99, 119, 1), Candle(200, 119, 120, 118, 119, 1)]
    resolved = store.reconcile(op.market, "1h", candles)[0]
    assert resolved["status"] == "SUCCESS_T5"
    assert "lucro final" in resolved["resolution_reason"]
    assert store.signal_stats()["wins"] == 1
    store.close()


def test_forming_candle_stop_closes_signal_immediately(tmp_path):
    store = Store(str(tmp_path / "signals.db")); op = opportunity(); store.register_signal(op)
    candles = [Candle(100, 100, 102, 99, 101, 1),
               Candle(200, 101, 103, 100, 102, 1),
               Candle(300, 102, 103, 94, 96, 1)]  # current/forming candle
    resolved = store.reconcile(op.market, "1h", candles)
    assert resolved[0]["status"] == "FAILED"
    assert store.signals("ACTIVE") == []
    store.close()


def test_expired_signal_is_reactivated_on_migration(tmp_path):
    path = tmp_path / "signals.db"; store = Store(str(path)); op = opportunity(); signal_id, _ = store.register_signal(op)
    store.db.execute("UPDATE signals SET status='EXPIRED',closed_at=200,close_price=101 WHERE id=?", (signal_id,))
    store._event(signal_id, "EXPIRED", "Expirada", 101); store.db.commit(); store.close()
    reopened = Store(str(path))
    assert reopened.signal(signal_id)["status"] == "ACTIVE"
    assert reopened.events()[0]["event_type"] == "REACTIVATED"
    reopened.close()


def test_audit_reclassifies_failed_signal_that_touched_target(tmp_path):
    store = Store(str(tmp_path / "signals.db")); op = opportunity(); signal_id, _ = store.register_signal(op)
    store.db.execute("UPDATE signals SET status='FAILED',closed_at=300 WHERE id=?", (signal_id,))
    store._event(signal_id, "FAILED", "Stop antigo", op.stop); store.db.commit()
    candles = [Candle(100, 100, 102, 99, 101, 1), Candle(200, 101, 106, 94, 100, 1)]
    repaired = store.audit_failed_signal(signal_id, candles)
    assert repaired["status"] == "SUCCESS_T1"
    assert store.events()[0]["event_type"] == "SUCCESS_T1"
    store.close()
