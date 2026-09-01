import json
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from market_sentinel.solana_intel import SolanaIntelService, WSOL_MINT
from market_sentinel.web import create_app


WALLET = "4" * 44
RISKY_WALLET = "5" * 44
MINT_A = "6" * 44
MINT_B = "7" * 44


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
    monkeypatch.setenv("SOLANA_INTEL_MAX_TOKENS", "2")
    first_pool = 1767225600  # 2026-01-01T00:00:00Z
    api_calls = {"top_traders": 0, "wallet_summary": 0}

    def handler(request: httpx.Request):
        if request.url.path == "/tokens/v2/recent":
            assert request.headers["x-api-key"] == "jupiter-test"
            return httpx.Response(200, json=[
                token(MINT_A, "A", "2026-01-01T00:00:00Z"),
                token(MINT_B, "B", "2026-01-01T00:00:00Z"),
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
        pnl = 1200 if mint == MINT_A else 800
        rows = [{
            "owner": WALLET,
            "realizedPnl": pnl,
            "totalPnl": pnl,
            "firstTradeUnixTime": first_pool + (35 if mint == MINT_A else 70),
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

    assert snapshot["summary"]["enriched_tokens"] == 2
    assert snapshot["summary"]["wallets_evaluated"] == 1
    assert snapshot["summary"]["quality_wallets"] == 1
    assert snapshot["summary"]["opportunities"] == 2
    assert snapshot["providers"]["birdeye"]["available"] is True
    main = snapshot["wallets"][0]
    assert main["wallet"] == WALLET
    assert main["outcomes"] == 60
    assert main["total_buy"] == 120
    assert main["total_sell"] == 75
    assert main["win_rate_pct"] == 66.7
    assert main["early_buys"] == 2
    assert main["median_entry_seconds"] == 52.5
    assert main["qualified"] is True
    assert all(row["wallet"] != RISKY_WALLET for row in snapshot["wallets"])
    assert {row["mint"] for row in snapshot["opportunities"]} == {MINT_A, MINT_B}
    assert all(row["quality_wallet_count"] == 1 for row in snapshot["opportunities"])
    assert all(row["opportunity_score"] >= 72 for row in snapshot["opportunities"])
    assert cached_snapshot["summary"]["opportunities"] == 2
    assert api_calls == {"top_traders": 2, "wallet_summary": 1}


@pytest.mark.asyncio
async def test_weak_wallet_history_does_not_promote_token(monkeypatch):
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
    assert snapshot["summary"]["opportunities"] == 0
    assert snapshot["opportunities"] == []
    assert snapshot["methodology"]["rejection_reasons"]["no_quality_wallet"] == 1


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


def test_solana_intel_web_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "solana-web.db"))
    monkeypatch.setenv("SESSION_SECRET", "integration-test-secret")
    monkeypatch.delenv("DASHBOARD_USER", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    app = create_app("config.yaml")

    class FakeIntel:
        async def snapshot(self, *, force=False):
            return {"forced": force, "read_only": True}

        async def routes(self, mint, *, amount_sol):
            return {"mint": mint, "amount_sol": amount_sol, "read_only": True}

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
        assert client.get("/static/solana-intel.js").status_code == 200
        assert client.get("/static/solana-intel.css").status_code == 200
