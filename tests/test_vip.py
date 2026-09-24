import time

from fastapi.testclient import TestClient

from market_sentinel.analysis import fibonacci_targets
from market_sentinel.auth import create_session
from market_sentinel.models import AssetClass, Market, Opportunity
from market_sentinel.payments import USDC_MINT, b58decode, b58encode
from market_sentinel.web import create_app

ADDRESS = "2btLJAAb1S3x6hZYdVyAePjqtQYi2ZBSRGy4569RZu8h"
OTHER = "FVdnakemjhcemfWUgNR2AERbk5Pog7zJ1UF2LjbocBUj"
TREASURY = b58encode(bytes(range(1, 33)))


def make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "vip.db"))
    monkeypatch.setenv("SESSION_SECRET", "vip-test-secret")
    monkeypatch.setenv("VIP_TREASURY_WALLET", TREASURY)
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "DASHBOARD_USER",
                "DASHBOARD_PASSWORD", "TURSO_DATABASE_URL", "VIP_ADMIN_WALLETS"):
        monkeypatch.delenv(key, raising=False)
    return create_app("config.yaml")


def open_signal(app):
    market = Market("hyperliquid", "SOL", "SOL", "USDC", "PERP", AssetClass.CRYPTO, 5_000_000)
    op = Opportunity(market, "1h", "LONG", "teste", 100, 95, *fibonacci_targets(100, 95, "LONG"),
                     2.618, 90, ["teste"], [], 100)
    signal_id, _ = app.state.dashboard.sentinel.store.register_signal(op)
    return signal_id


def login(app, client, address=ADDRESS):
    app.state.dashboard.social.upsert_user(address)
    client.cookies.set("sentinel_session", create_session(address, app.state.dashboard.session_secret))


def paying_tx(reference, amount=10_000_000, owner=TREASURY, err=None, block_time=None):
    return {"blockTime": block_time or int(time.time()),
            "meta": {"err": err, "logMessages": [],
                     "preTokenBalances": [],
                     "postTokenBalances": [{"accountIndex": 2, "mint": USDC_MINT, "owner": owner,
                                            "uiTokenAmount": {"amount": str(amount)}}]},
            "transaction": {"message": {"accountKeys": [{"pubkey": "payer"}, {"pubkey": reference}],
                                        "instructions": []}}}


SIG = b58encode(bytes([7]) * 64)


def test_base58_roundtrip():
    raw = b"\0\0" + bytes(range(30))
    assert b58decode(b58encode(raw)) == raw


def test_non_vip_only_sees_open_count(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        signal_id = open_signal(app)
        state = client.get("/api/dashboard-state").json()
        assert state["opportunities"] == [] and state["opportunities_locked"] is True
        assert state["opportunity_count"] == 1
        assert all(e["symbol"] == "VIP" for e in state["events"])
        assert client.get("/api/opportunities").json() == []
        assert client.get(f"/api/signals/{signal_id}/chart").status_code == 403
        assert "hyperliquid:SOL" not in client.get("/api/live-prices").json()
        login(app, client)  # logged in but not paid: still locked
        assert client.get("/api/dashboard-state").json()["opportunities"] == []


def test_payment_unlocks_vip_for_31_days_and_signature_is_single_use(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    vip = app.state.dashboard.vip
    with TestClient(app) as client:
        open_signal(app)
        login(app, client)
        intent = client.post("/api/vip/intent").json()
        assert intent["solana_pay_url"].startswith(f"solana:{TREASURY}?amount=10&spl-token={USDC_MINT}")
        monkeypatch.setattr(vip, "find_signatures", lambda ref: [SIG])
        monkeypatch.setattr(vip, "_get_transaction", lambda sig: paying_tx(intent["reference"]))
        result = client.post("/api/vip/verify", json={"reference": intent["reference"]}).json()
        assert result["status"] == "paid" and result["user"]["vip"] is True
        end = result["user"]["current_period_end"]
        assert abs(end - (time.time() + 31 * 86400)) < 60
        state = client.get("/api/dashboard-state").json()
        assert len(state["opportunities"]) == 1 and state["opportunities"][0]["symbol"] == "SOL"

        # Another account cannot reuse the same on-chain transfer.
        login(app, client, OTHER)
        other = client.post("/api/vip/intent").json()
        monkeypatch.setattr(vip, "_get_transaction", lambda sig: paying_tx(other["reference"]))
        again = client.post("/api/vip/verify", json={"reference": other["reference"],
                                                     "signature": SIG}).json()
        assert again["status"] == "pending" and "já foi utilizada" in again["reason"]


def test_renewal_stacks_on_remaining_time(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    social = app.state.dashboard.social
    social.upsert_user(ADDRESS)
    first = social.extend_vip(ADDRESS, 31 * 86400)["current_period_end"]
    second = social.extend_vip(ADDRESS, 31 * 86400)["current_period_end"]
    assert second - first == 31 * 86400


def test_underpaid_wrong_owner_or_unbound_transfer_is_rejected(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    vip = app.state.dashboard.vip
    intent = {"reference": "REF", "memo": "MS-VIP-ABCD", "created_at": int(time.time())}
    assert "menor" in vip.validate_transaction(paying_tx("REF", amount=9_990_000), intent)
    assert "menor" in vip.validate_transaction(paying_tx("REF", owner="someone"), intent)
    assert "referência" in vip.validate_transaction(paying_tx("OTHER"), intent)
    assert "falhou" in vip.validate_transaction(paying_tx("REF", err={"x": 1}), intent)
    assert "anterior" in vip.validate_transaction(
        paying_tx("REF", block_time=int(time.time()) - 3600), intent)
    assert vip.validate_transaction(paying_tx("REF"), intent) is None


def test_admin_wallet_is_always_vip(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    monkeypatch.setattr(app.state.dashboard.vip, "admin_wallets", {ADDRESS})
    with TestClient(app) as client:
        open_signal(app)
        login(app, client)
        assert len(client.get("/api/dashboard-state").json()["opportunities"]) == 1


def test_chat_highlights_only_vip_messages(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    social = app.state.dashboard.social
    with TestClient(app) as client:
        login(app, client, OTHER)
        assert client.post("/api/chat/messages", json={"body": "sem destaque"}).json()["vip"] is False
        login(app, client, ADDRESS)
        social.extend_vip(ADDRESS, 31 * 86400)
        assert client.post("/api/chat/messages", json={"body": "sou VIP"}).json()["vip"] is True
        rows = {m["body"]: m["vip"] for m in client.get("/api/chat/messages").json()["messages"]}
        assert rows == {"sem destaque": False, "sou VIP": True}
