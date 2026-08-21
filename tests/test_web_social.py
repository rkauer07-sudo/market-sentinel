from fastapi.testclient import TestClient

from market_sentinel.auth import create_session
from market_sentinel.web import create_app


ADDRESS = "0x2222222222222222222222222222222222222222"


def test_web3_session_unlocks_chat(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "web.db"))
    monkeypatch.setenv("SESSION_SECRET", "integration-test-secret")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("DASHBOARD_USER", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    app = create_app("config.yaml")
    with TestClient(app) as client:
        assert client.get("/health").json()["version"] == "0.3.0"
        assert client.get("/api/learning").json() == {"latest": None, "profiles": []}
        assert client.get("/api/chat/messages").status_code == 401
        app.state.dashboard.social.upsert_user(ADDRESS)
        token = create_session(ADDRESS, app.state.dashboard.session_secret)
        client.cookies.set("sentinel_session", token)
        sent = client.post("/api/chat/messages", json={"body": "BTC segurando suporte"})
        assert sent.status_code == 200
        rows = client.get("/api/chat/messages").json()["messages"]
        assert rows[0]["body"] == "BTC segurando suporte"
        assert rows[0]["mine"] is True


def test_nonce_endpoint_does_not_request_a_transaction(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "nonce.db"))
    monkeypatch.setenv("SESSION_SECRET", "integration-test-secret")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    app = create_app("config.yaml")
    with TestClient(app) as client:
        response = client.post("/api/auth/nonce", json={"address": ADDRESS})
        assert response.status_code == 200
        challenge = response.json()
        assert ADDRESS in challenge["message"]
        assert "não envia transações" in challenge["message"]
