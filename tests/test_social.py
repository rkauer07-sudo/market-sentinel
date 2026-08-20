import time

from market_sentinel.auth import create_session, new_wallet_challenge, read_session
from market_sentinel.social import SocialStore
from market_sentinel.storage import Store


ADDRESS = "0x1111111111111111111111111111111111111111"


def test_signed_session_rejects_tampering():
    token = create_session(ADDRESS, "test-secret", 60)
    assert read_session(token, "test-secret") == ADDRESS
    assert read_session(token + "x", "test-secret") is None
    assert read_session(token, "different-secret") is None


def test_wallet_challenge_is_single_use(tmp_path):
    store = Store(str(tmp_path / "social.db"))
    social = SocialStore(store)
    nonce, message, expires_at = new_wallet_challenge(ADDRESS, "localhost")
    social.save_challenge(ADDRESS, nonce, message, expires_at)
    assert social.challenge_message(ADDRESS, nonce) == message
    assert social.consume_challenge(ADDRESS, nonce) is True
    assert social.challenge_message(ADDRESS, nonce) is None
    assert social.consume_challenge(ADDRESS, nonce) is False
    store.close()


def test_chat_requires_persisted_user_and_keeps_plan_fields(tmp_path):
    store = Store(str(tmp_path / "social.db"))
    social = SocialStore(store)
    user = social.upsert_user(ADDRESS)
    assert user["plan"] == "free" and user["subscription_status"] == "inactive"
    message = social.add_message(ADDRESS, "  leitura   de mercado  ")
    assert message["body"] == "leitura de mercado"
    assert social.messages() == [message]
    assert user["last_login_at"] <= int(time.time())
    store.close()
