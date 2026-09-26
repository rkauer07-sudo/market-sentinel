import time

from fastapi.testclient import TestClient

from market_sentinel.payments import USDC_MINT, b58encode

from tests.test_vip import ADDRESS, OTHER, SIG, TREASURY, login, make_app, paying_tx

OWNER = "GVMPqSU3KZTKa58cKLZreZx46rTWVLhEWXJ7DdebDKH8"
PROGRAM = b58encode(bytes(range(40, 72)))


def add_code(app, code, percent, **extra):
    db = app.state.dashboard.social.store.db
    cols = {"code": code, "percent": percent, **extra}
    db.execute(f"INSERT INTO discount_codes({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
               tuple(cols.values()))
    db.commit()


def contract_tx(reference, amount, program=PROGRAM):
    tx = paying_tx(reference, amount=amount)
    tx["transaction"]["message"]["instructions"] = [{"programId": program, "accounts": [], "data": ""}]
    return tx


def test_discount_code_lowers_price_and_is_one_use_per_wallet(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    vip = app.state.dashboard.vip
    add_code(app, "AMIGO20", 20)
    with TestClient(app) as client:
        login(app, client)
        bad = client.post("/api/vip/intent", json={"code": "nope"})
        assert bad.status_code == 400 and "inválido" in bad.json()["detail"]
        intent = client.post("/api/vip/intent", json={"code": " amigo20 "}).json()
        assert intent["amount_usdc"] == 8 and intent["discount_percent"] == 20
        assert intent["amount_units"] == 8_000_000
        monkeypatch.setattr(vip, "find_signatures", lambda ref: [SIG])
        monkeypatch.setattr(vip, "_get_transaction", lambda sig: paying_tx(intent["reference"], 8_000_000))
        paid = client.post("/api/vip/verify", json={"reference": intent["reference"]}).json()
        assert paid["status"] == "paid"
        again = client.post("/api/vip/intent", json={"code": "AMIGO20"})
        assert again.status_code == 400 and "já usou" in again.json()["detail"]
        login(app, client, OTHER)  # other wallet can still use it
        assert client.post("/api/vip/intent", json={"code": "AMIGO20"}).json()["amount_usdc"] == 8


def test_underpaying_a_discounted_intent_is_rejected(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    vip = app.state.dashboard.vip
    intent = {"reference": "REF", "memo": "M", "created_at": int(time.time()), "amount_usdc": 7.5}
    assert "menor" in vip.validate_transaction(paying_tx("REF", amount=7_000_000), intent)
    assert vip.validate_transaction(paying_tx("REF", amount=7_500_000), intent) is None


def test_full_discount_grants_vip_without_transaction(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    add_code(app, "FREE", 100, max_uses=1)
    with TestClient(app) as client:
        login(app, client)
        result = client.post("/api/vip/intent", json={"code": "free"}).json()
        assert result["status"] == "paid" and result["user"]["vip"] is True
        assert abs(result["user"]["current_period_end"] - (time.time() + 31 * 86400)) < 60
        login(app, client, OTHER)
        limit = client.post("/api/vip/intent", json={"code": "FREE"})
        assert limit.status_code == 400 and "limite" in limit.json()["detail"]


def test_expired_or_inactive_codes_fail(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    add_code(app, "OLD", 10, expires_at=int(time.time()) - 10)
    add_code(app, "OFF", 10, active=0)
    with TestClient(app) as client:
        login(app, client)
        assert "expirou" in client.post("/api/vip/intent", json={"code": "OLD"}).json()["detail"]
        assert "inválido" in client.post("/api/vip/intent", json={"code": "OFF"}).json()["detail"]


def test_contract_mode_requires_program_invocation(tmp_path, monkeypatch):
    monkeypatch.setenv("VIP_PROGRAM_ID", PROGRAM)
    app = make_app(tmp_path, monkeypatch)
    vip = app.state.dashboard.vip
    assert vip.public_config()["contract"] is True
    intent = {"reference": "REF", "memo": "M", "created_at": int(time.time()), "amount_usdc": 10}
    assert "contrato" in vip.validate_transaction(paying_tx("REF"), intent)
    assert "contrato" in vip.validate_transaction(contract_tx("REF", 10_000_000, program="X"), intent)
    assert vip.validate_transaction(contract_tx("REF", 10_000_000), intent) is None
    with TestClient(app) as client:
        login(app, client)
        created = client.post("/api/vip/intent").json()
        assert created["program_id"] == PROGRAM and created["solana_pay_url"] is None


def test_feedback_anyone_sends_only_owner_reads(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        ok = client.post("/api/feedback", json={"body": "Adorei o painel", "contact": "@fulano"})
        assert ok.status_code == 200
        assert client.post("/api/feedback", json={"body": "x"}).status_code == 400
        assert client.get("/api/feedback").status_code == 403
        login(app, client, ADDRESS)
        assert client.get("/api/feedback").status_code == 403
        assert client.get("/api/auth/me").json()["user"]["is_owner"] is False
        login(app, client, OWNER)
        assert client.get("/api/auth/me").json()["user"]["is_owner"] is True
        inbox = client.get("/api/feedback").json()
        assert inbox["unread"] == 1 and inbox["messages"][0]["contact"] == "@fulano"
        mid = inbox["messages"][0]["id"]
        assert client.post(f"/api/feedback/{mid}/read", json={}).status_code == 200
        assert client.get("/api/feedback").json()["unread"] == 0


def test_feedback_rate_limit(tmp_path, monkeypatch):
    app = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        assert client.post("/api/feedback", json={"body": "primeira"}).status_code == 200
        second = client.post("/api/feedback", json={"body": "segunda"})
        assert second.status_code == 400 and "Aguarde" in second.json()["detail"]


def test_legacy_host_redirects_to_canonical_domain(tmp_path, monkeypatch):
    monkeypatch.setenv("CANONICAL_HOST", "marketsentinel.xyz")
    monkeypatch.setenv("REDIRECT_HOSTS", "market-sentinel-sable.vercel.app,www.marketsentinel.xyz")
    app = make_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        r = client.get("/api/status?x=1", headers={"host": "market-sentinel-sable.vercel.app"},
                       follow_redirects=False)
        assert r.status_code == 308 and r.headers["location"] == "https://marketsentinel.xyz/api/status?x=1"
        assert client.get("/health", headers={"host": "marketsentinel.xyz"}).status_code == 200
