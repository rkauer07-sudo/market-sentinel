from datetime import date, datetime, timedelta

from market_sentinel.learning import DailyLearner, LOCAL_ZONE
from market_sentinel.models import AssetClass, Market, Opportunity
from market_sentinel.storage import Store


MARKET = Market("test", "BTC-PERP", "BTC", "USD", "perp", AssetClass.CRYPTO)


def opportunity(index: int, setup: str) -> Opportunity:
    return Opportunity(
        MARKET, "1h", "LONG", setup, 100, 98, 104, None, None, None, None,
        2.0, 90, ["estrutura"], ["risco"], 1_700_000_000 + index,
    )


def resolve(store: Store, index: int, setup: str, won: bool, closed_at: int):
    signal_id, created = store.register_signal(opportunity(index, setup))
    assert created
    status = "SUCCESS_T1" if won else "FAILED"
    store.db.execute("UPDATE signals SET status=?,closed_at=? WHERE id=?",
                     (status, closed_at, signal_id))
    store.db.commit()


def test_daily_learning_uses_chronological_holdout_and_ignores_future(tmp_path):
    store = Store(str(tmp_path / "learning.db"))
    target_day = date(2026, 8, 19)
    cutoff = int(datetime(2026, 8, 20, tzinfo=LOCAL_ZONE).timestamp())
    index = 0
    # Repeating order keeps strong and weak setups in both train and holdout.
    for _ in range(20):
        resolve(store, index, "strong", True, cutoff - 20_000 + index); index += 1
        resolve(store, index, "strong", True, cutoff - 20_000 + index); index += 1
        resolve(store, index, "weak", False, cutoff - 20_000 + index); index += 1
    for _ in range(10):
        resolve(store, index, "weak", True, cutoff + 100 + index); index += 1

    learner = DailyLearner(store, min_total=30, min_segment=12)
    report = learner.run_for_day(target_day)

    assert report["sample_size"] == 60
    assert report["status"] == "validated"
    weak = store.learning_profiles()["setup:weak"]
    assert weak["modifier"] < 0
    adjustment, evidence = learner.adjustment(opportunity(999, "weak"))
    assert adjustment < 0
    assert evidence


def test_daily_learning_fails_closed_with_small_sample(tmp_path):
    store = Store(str(tmp_path / "small.db"))
    target_day = date(2026, 8, 19)
    cutoff = int(datetime(2026, 8, 20, tzinfo=LOCAL_ZONE).timestamp())
    for index in range(8):
        resolve(store, index, "small", index % 2 == 0, cutoff - 100 + index)

    report = DailyLearner(store, min_total=30).run_for_day(target_day)

    assert report["status"] == "insufficient"
    assert report["promoted_profiles"] == 0
    assert store.learning_profiles() == {}


def test_run_if_due_is_idempotent(tmp_path):
    store = Store(str(tmp_path / "daily.db"))
    learner = DailyLearner(store)
    now = datetime(2026, 8, 20, 8, tzinfo=LOCAL_ZONE)
    first = learner.run_if_due(now)
    second = learner.run_if_due(now + timedelta(hours=1))
    assert first is not None
    assert second is None
