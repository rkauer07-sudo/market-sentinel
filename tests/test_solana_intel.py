import json
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from market_sentinel.solana_intel import SolanaIntelService, USDC_MINT, WSOL_MINT
from market_sentinel.web import create_app


WALLET = "4" * 44
RISKY_WALLET = "5" * 44
MINT_A = "6" * 44
MINT_B = "7" * 44
MINT_C = "9" * 44


@pytest.fixture(autouse=True)
def isolated_solana_history(monkeypatch):
    for name in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SOLANA_INTEL_HISTORY_PATH",
    ):
        monkeypatch.delenv(name, raising=False)


def token(mint: str, symbol: str, created_at: str) -> dict:
    return {
        "id": mint,
        "name": f"{symbol} token",
        "symbol": symbol,
        "decimals": 6,
        "firstPool": {"id": "8" * 44, "createdAt": created_at},
        "holderCount": 250,
        "liquidity": 45_000,
        "mcap": 200_000,
        "usdPrice": 0.002,
        "organicScore": 72,
        "organicScoreLabel": "high",
        "audit": {
            "mintAuthorityDisabled": True,
            "freezeAuthorityDisabled": True,
            "topHoldersPercentage": 12.5,
        },
        "stats5m": {"numBuys": 31, "numSells": 12, "numTraders": 25},
    }


def qualified_wallet(address: str, *, pnl: float, score: int = 80) -> dict:
    return {
        "wallet": address,
        "qualified": True,
        "score": score,
        "realized_pnl_usd": pnl,
        "profitable_memecoins": 3,
        "profitable_memecoin_mints": [MINT_A, MINT_B, MINT_C],
        "win_rate_pct": 66.7,
        "outcomes": 60,
        "total_buy": 120,
        "total_sell": 75,
        "solscan_url": f"https://solscan.io/account/{address}",
    }


@pytest.mark.asyncio
async def test_snapshot_uses_jupiter_without_birdeye(monkeypatch):
    monkeypatch.delenv("JUPITER_API_KEY", raising=False)
    monkeypatch.delenv("BIRDEYE_API_KEY", raising=False)
    monkeypatch.setenv("SOLANA_INTEL_MAX_TOKENS", "1")

    def handler(request: httpx.Request):
        assert request.url.path == "/tokens/v2/recent"
        assert "x-api-key" not in request.headers
        return httpx.Response(200, json=[token(MINT_A, "MEME", "2026-01-01T00:00:00Z")])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        snapshot = await SolanaIntelService(client).snapshot()

    assert snapshot["read_only"] is True
    assert snapshot["summary"]["recent_tokens"] == 1
    assert snapshot["wallets"] == []
    assert snapshot["opportunities"] == []
    assert snapshot["providers"]["jupiter"]["available"] is True
    assert snapshot["providers"]["birdeye"]["configured"] is False
    assert snapshot["tokens"][0]["safety_score"] == 100


@pytest.mark.asyncio
async def test_defaults_use_max_collection_and_accumulate_launches(monkeypatch):
    monkeypatch.delenv("SOLANA_INTEL_MAX_TOKENS", raising=False)
    monkeypatch.delenv("SOLANA_INTEL_MAX_WALLETS", raising=False)
    batches = [
        [token(MINT_A, "A", "2026-01-01T00:00:00Z")],
        [token(MINT_B, "B", "2026-01-01T00:01:00Z")],
    ]

    def handler(request: httpx.Request):
        assert request.url.path == "/tokens/v2/recent"
        return httpx.Response(200, json=batches.pop(0))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = SolanaIntelService(client)
        first = await service.snapshot()
        second = await service.snapshot(force=True)

    assert service.max_tokens == 30
    assert service.max_wallets == 50
    assert service.history_limit == 500
    assert first["summary"]["launches_in_window"] == 1
    assert second["summary"]["launches_in_window"] == 2
    assert second["summary"]["pending_tokens"] == 2
    assert {row["mint"] for row in second["tokens"]} == {MINT_A, MINT_B}


@pytest.mark.asyncio
async def test_launch_history_survives_a_new_service_instance(tmp_path, monkeypatch):
    history_path = tmp_path / "solana-launches.json"
    monkeypatch.setenv("SOLANA_INTEL_HISTORY_PATH", str(history_path))

    def first_handler(request: httpx.Request):
        return httpx.Response(200, json=[
            token(MINT_A, "A", "2026-01-01T00:00:00Z"),
        ])

    async with httpx.AsyncClient(transport=httpx.MockTransport(first_handler)) as client:
        first = await SolanaIntelService(client).snapshot()

    def second_handler(request: httpx.Request):
        return httpx.Response(200, json=[
            token(MINT_B, "B", "2026-01-01T00:01:00Z"),
        ])

    async with httpx.AsyncClient(transport=httpx.MockTransport(second_handler)) as client:
        second = await SolanaIntelService(client).snapshot()

    assert first["providers"]["history"]["persistent"] is True
    assert history_path.exists()
    assert second["summary"]["launches_in_window"] == 2
    assert {row["mint"] for row in second["tokens"]} == {MINT_A, MINT_B}


@pytest.mark.asyncio
async def test_launch_history_is_saved_to_supabase_storage(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "sb_secret_test")
    monkeypatch.setenv("SUPABASE_STORAGE_BUCKET", "sentinel")
    saved = {}

    def handler(request: httpx.Request):
        if request.url.host == "supabase.test":
            assert request.headers["apikey"] == "sb_secret_test"
            assert "authorization" not in request.headers
            if request.method == "GET":
                return httpx.Response(404, json={"message": "not found"})
            saved.update(json.loads(request.content))
            return httpx.Response(200, json={"Key": "solana-intel-history.json"})
        assert request.url.path == "/tokens/v2/recent"
        return httpx.Response(200, json=[
            token(MINT_A, "A", "2026-01-01T00:00:00Z"),
        ])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        snapshot = await SolanaIntelService(client).snapshot()

    assert snapshot["providers"]["history"]["persistent"] is True
    assert snapshot["providers"]["history"]["mode"] == "supabase-storage"
    assert MINT_A in saved["tokens"]


@pytest.mark.asyncio
async def test_only_tokens_backed_by_quality_wallet_history_become_opportunities(monkeypatch):
    monkeypatch.setenv("BIRDEYE_API_KEY", "birdeye-test")
    monkeypatch.setenv("JUPITER_API_KEY", "jupiter-test")
    monkeypatch.setenv("SOLANA_INTEL_MAX_TOKENS", "3")
    first_pool = 1767225600  # 2026-01-01T00:00:00Z
    api_calls = {"top_traders": 0, "wallet_summary": 0}

    def handler(request: httpx.Request):
        if request.url.path == "/tokens/v2/recent":
            assert request.headers["x-api-key"] == "jupiter-test"
            return httpx.Response(200, json=[
                token(MINT_A, "A", "2026-01-01T00:00:00Z"),
                token(MINT_B, "B", "2026-01-01T00:00:00Z"),
                token(MINT_C, "C", "2026-01-01T00:00:00Z"),
            ])
        assert request.headers["x-api-key"] == "birdeye-test"
        query = parse_qs(request.url.query.decode())
        if request.url.path == "/wallet/v2/pnl/summary":
            api_calls["wallet_summary"] += 1
            assert query["wallet"] == [WALLET]
            assert query["duration"] == ["90d"]
            assert query["position_scope"] == ["cumulative"]
            assert query["pnl_method"] == ["wac"]
            return httpx.Response(200, json={"data": {
                "counts": {
                    "total_buy": 120,
                    "total_sell": 75,
                    "total_trade": 195,
                    "total_win": 40,
                    "total_loss": 20,
                    "win_rate": 40 / 60,
                },
                "pnl": {
                    "realized_profit_usd": 42_000,
                    "unrealized_usd": 3_000,
                    "total_usd": 45_000,
                    "avg_profit_per_trade_usd": 700,
                },
            }})
        assert request.url.path == "/defi/v2/tokens/top_traders"
        api_calls["top_traders"] += 1
        assert query["wallet_tags"] == ["sniper,smart_trader"]
        mint = query["address"][0]
        pnl = {MINT_A: 1200, MINT_B: 800, MINT_C: 600}[mint]
        delay = {MINT_A: 35, MINT_B: 70, MINT_C: 105}[mint]
        rows = [{
            "owner": WALLET,
            "realizedPnl": pnl,
            "totalPnl": pnl,
            "firstTradeUnixTime": first_pool + delay,
            "walletTags": ["sniper", "smart_trader"],
            "tradeBuy": 2,
            "tradeSell": 1,
        }]
        if mint == MINT_A:
            rows.append({
                "owner": RISKY_WALLET,
                "realizedPnl": 20_000,
                "totalPnl": 20_000,
                "firstTradeUnixTime": first_pool + 2,
                "walletTags": ["sniper", "bundler"],
            })
        return httpx.Response(200, json={"data": {"items": rows}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = SolanaIntelService(client)
        snapshot = await service.snapshot()
        cached_snapshot = await service.snapshot(force=True)

    assert snapshot["summary"]["enriched_tokens"] == 3
    assert snapshot["summary"]["wallets_evaluated"] == 1
    assert snapshot["summary"]["quality_wallets"] == 1
    assert snapshot["summary"]["opportunities"] == 3
    assert snapshot["providers"]["birdeye"]["available"] is True
    main = snapshot["wallets"][0]
    assert main["wallet"] == WALLET
    assert main["outcomes"] == 60
    assert main["total_buy"] == 120
    assert main["total_sell"] == 75
    assert main["win_rate_pct"] == 66.7
    assert main["profitable_memecoins"] == 3
    assert main["early_buys"] == 3
    assert main["median_entry_seconds"] == 70
    assert main["qualified"] is True
    assert all(row["wallet"] != RISKY_WALLET for row in snapshot["wallets"])
    assert {row["mint"] for row in snapshot["opportunities"]} == {
        MINT_A, MINT_B, MINT_C,
    }
    assert all(row["quality_wallet_count"] == 1 for row in snapshot["opportunities"])
    assert all(row["opportunity_score"] >= 72 for row in snapshot["opportunities"])
    assert cached_snapshot["summary"]["opportunities"] == 3
    assert api_calls == {"top_traders": 3, "wallet_summary": 1}


@pytest.mark.asyncio
async def test_fewer_than_three_profitable_memecoins_do_not_promote_token(monkeypatch):
    monkeypatch.setenv("BIRDEYE_API_KEY", "birdeye-test")
    monkeypatch.setenv("SOLANA_INTEL_MAX_TOKENS", "1")
    first_pool = 1767225600

    def handler(request: httpx.Request):
        if request.url.path == "/tokens/v2/recent":
            return httpx.Response(200, json=[
                token(MINT_A, "A", "2026-01-01T00:00:00Z"),
            ])
        if request.url.path == "/defi/v2/tokens/top_traders":
            return httpx.Response(200, json={"data": {"items": [{
                "owner": WALLET,
                "realizedPnl": 5_000,
                "firstTradeUnixTime": first_pool + 20,
                "walletTags": ["sniper", "smart_trader"],
            }]}})
        assert request.url.path == "/wallet/v2/pnl/summary"
        return httpx.Response(200, json={"data": {
            "total_buy": 6,
            "total_sell": 2,
            "total_win": 3,
            "total_loss": 3,
            "win_rate": 0.5,
            "realized_profit_usd": 400,
            "avg_profit_per_trade": 66,
        }})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        snapshot = await SolanaIntelService(client).snapshot()

    assert snapshot["summary"]["wallets_evaluated"] == 1
    assert snapshot["summary"]["quality_wallets"] == 0
    assert snapshot["methodology"]["minimums"]["profitable_memecoins"] == 3
    assert snapshot["opportunities"] == []
    assert snapshot["methodology"]["rejection_reasons"]["no_quality_wallet"] == 1


@pytest.mark.asyncio
async def test_only_distinct_realized_profit_mints_count_for_monitoring():
    def observation(mint: str, realized: float, *, unrealized: float = 0) -> dict:
        return {
            "wallet": WALLET,
            "mint": mint,
            "symbol": "MEME",
            "entry_delay_seconds": 60,
            "realized_pnl_usd": realized,
            "unrealized_pnl_usd": unrealized,
            "total_pnl_usd": realized + unrealized,
            "tags": ["smart_trader"],
        }

    async with httpx.AsyncClient() as client:
        service = SolanaIntelService(client)
        profile = service._wallet_profile(WALLET, {}, [
            observation(MINT_A, 100),
            observation(MINT_A, 200),
            observation(MINT_B, 0, unrealized=5_000),
            observation(MINT_C, 300),
        ])

        assert profile["profitable_memecoins"] == 2
        assert profile["qualified"] is False

        profile = service._refresh_wallet_profile(profile, [
            observation(MINT_B, 50),
        ])
        assert profile["profitable_memecoins"] == 3
        assert profile["qualified"] is True

        profile = service._refresh_wallet_profile(profile, [
            observation(MINT_B, 0, unrealized=5_000),
        ])
        assert profile["profitable_memecoins"] == 2
        assert profile["qualified"] is False


@pytest.mark.asyncio
async def test_route_validation_is_quote_only(monkeypatch):
    monkeypatch.setenv("JUPITER_API_KEY", "jupiter-test")
    monkeypatch.delenv("BIRDEYE_API_KEY", raising=False)

    def handler(request: httpx.Request):
        if request.url.path == "/tokens/v2/recent":
            return httpx.Response(200, json=[token(MINT_A, "MEME", "2026-01-01T00:00:00Z")])
        assert request.method == "GET"
        assert request.url.path == "/swap/v2/order"
        query = parse_qs(request.url.query.decode())
        assert "taker" not in query
        assert "userPublicKey" not in query
        output = query["outputMint"][0]
        return httpx.Response(200, json={
            "inAmount": query["amount"][0],
            "outAmount": "2500000" if output == MINT_A else "1000000",
            "router": "metis",
            "mode": "ultra",
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        routes = await SolanaIntelService(client).routes(MINT_A, amount_sol=0.25)

    assert routes["tradable"] is True
    assert routes["buy"]["router"] == "metis"
    assert routes["sell"]["available"] is True
    assert routes["read_only"] is True
    assert WSOL_MINT != MINT_A


@pytest.mark.asyncio
async def test_wallet_ranking_is_led_by_realized_profit():
    lower_profit = "3" * 44
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(500)
    )) as client:
        service = SolanaIntelService(client)
        service._history_loaded = True
        service._history_state = service._empty_history_state()
        service._history_state["wallets"] = {
            WALLET: {"audited_at": 1, "profile": qualified_wallet(
                WALLET, pnl=50_000, score=70
            )},
            lower_profit: {"audited_at": 1, "profile": qualified_wallet(
                lower_profit, pnl=10_000, score=95
            )},
        }

        _, wallets, _ = service._aggregate_history()

    assert [wallet["wallet"] for wallet in wallets] == [WALLET, lower_profit]
    assert wallets[0]["score"] < wallets[1]["score"]


@pytest.mark.asyncio
async def test_helius_swap_creates_one_alert_for_first_wallet_buy(monkeypatch):
    monkeypatch.setenv("HELIUS_WEBHOOK_SECRET", "webhook-secret")
    sent = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(500)
    )) as client:
        service = SolanaIntelService(client)
        service._history_loaded = True
        service._history_state = service._empty_history_state()
        service._history_state["wallets"] = {
            WALLET: {"audited_at": 1, "profile": qualified_wallet(WALLET, pnl=42_000)},
        }
        service._history_state["tokens"] = {
            MINT_B: {"token": service._normalize_token(
                token(MINT_B, "FRESH", "2026-01-01T00:00:00Z")
            )},
        }
        service._history_state["wallet_mints"] = {WALLET: [MINT_A]}
        event = {
            "type": "SWAP",
            "source": "JUPITER",
            "signature": "sig-first-buy",
            "timestamp": 1_767_225_700,
            "feePayer": WALLET,
            "tokenTransfers": [
                {
                    "fromUserAccount": WALLET,
                    "toUserAccount": "8" * 44,
                    "mint": USDC_MINT,
                    "tokenAmount": 250,
                },
                {
                    "fromUserAccount": "8" * 44,
                    "toUserAccount": WALLET,
                    "mint": MINT_B,
                    "tokenAmount": 1_250_000,
                    "tokenStandard": "Fungible",
                },
            ],
            "nativeTransfers": [],
        }

        async def capture(purchase):
            sent.append(purchase)

        created = await service.process_helius_webhook(event, send_alert=capture)
        duplicate = await service.process_helius_webhook(event, send_alert=capture)

    assert service.webhook_authorized("Bearer webhook-secret") is True
    assert len(created) == 1
    assert duplicate == []
    assert len(sent) == 1
    assert created[0]["wallet_rank"] == 1
    assert created[0]["mint"] == MINT_B
    assert created[0]["payment_symbol"] == "USDC"
    assert created[0]["payment_amount"] == 250
    assert created[0]["first_wallet_buy"] is True
    assert service._purchase_rows()[0]["alert_sent_at"] > 0


@pytest.mark.asyncio
async def test_helius_webhook_sync_only_updates_when_wallet_set_changes(monkeypatch):
    monkeypatch.setenv("HELIUS_API_KEY", "helius-test")
    monkeypatch.setenv(
        "HELIUS_WEBHOOK_URL", "https://sentinel.test/api/solana-intel/helius"
    )
    monkeypatch.setenv("HELIUS_WEBHOOK_SECRET", "webhook-secret")
    calls = []

    def handler(request: httpx.Request):
        calls.append((request.method, request.url.path))
        assert request.url.params["api-key"] == "helius-test"
        if request.method == "GET":
            return httpx.Response(200, json=[])
        body = json.loads(request.content)
        assert body["transactionTypes"] == ["SWAP", "BUY"]
        assert body["accountAddresses"] == [WALLET]
        assert body["authHeader"] == "webhook-secret"
        return httpx.Response(200, json={"webhookID": "webhook-1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        service = SolanaIntelService(client)
        wallets = [qualified_wallet(WALLET, pnl=42_000)]
        first = await service._sync_helius_webhook(wallets)
        second = await service._sync_helius_webhook(wallets)

    assert first["wallets_monitored"] == 1
    assert second["available"] is True
    assert calls == [("GET", "/v0/webhooks"), ("POST", "/v0/webhooks")]


def test_solana_intel_web_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "solana-web.db"))
    monkeypatch.setenv("SESSION_SECRET", "integration-test-secret")
    monkeypatch.delenv("DASHBOARD_USER", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    app = create_app("config.yaml")
    received_webhooks = []

    class FakeIntel:
        async def snapshot(self, *, force=False):
            return {"forced": force, "read_only": True}

        async def routes(self, mint, *, amount_sol):
            return {"mint": mint, "amount_sol": amount_sol, "read_only": True}

        def webhook_authorized(self, supplied):
            return supplied == "hook-secret"

        async def process_helius_webhook(self, payload, *, send_alert=None):
            received_webhooks.extend(payload)
            return []

    app.state.dashboard.solana_intel = FakeIntel()
    with TestClient(app) as client:
        assert client.get("/api/solana-intel").json() == {"forced": False, "read_only": True}
        assert client.post("/api/solana-intel/refresh").json()["forced"] is True
        route = client.get(f"/api/solana-intel/routes/{MINT_A}?amount_sol=0.5").json()
        assert route == {"mint": MINT_A, "amount_sol": 0.5, "read_only": True}
        dashboard = client.get("/")
        assert dashboard.status_code == 200
        assert 'href="/memecoins-analyser"' in dashboard.text
        assert 'id="solana-intel"' not in dashboard.text
        analyser = client.get("/memecoins-analyser")
        assert analyser.status_code == 200
        assert "Memecoins Analyser" in analyser.text
        assert 'id="solana-intel"' in analyser.text
        assert "Smart wallets" not in analyser.text
        assert client.post(
            "/api/solana-intel/helius", json=[{"type": "SWAP"}]
        ).status_code == 401
        accepted = client.post(
            "/api/solana-intel/helius",
            headers={"Authorization": "hook-secret"},
            json=[{"type": "SWAP"}],
        )
        assert accepted.json() == {"accepted": 1}
        assert received_webhooks == [{"type": "SWAP"}]
        assert client.get("/static/solana-intel.js").status_code == 200
        assert client.get("/static/solana-intel.css").status_code == 200
