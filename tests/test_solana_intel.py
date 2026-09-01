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
    assert snapshot["providers"]["jupiter"]["available"] is True
    assert snapshot["providers"]["birdeye"]["configured"] is False
    assert snapshot["tokens"][0]["safety_score"] == 100


@pytest.mark.asyncio
async def test_birdeye_wallets_are_aggregated_and_risky_tags_are_penalized(monkeypatch):
    monkeypatch.setenv("BIRDEYE_API_KEY", "birdeye-test")
    monkeypatch.setenv("JUPITER_API_KEY", "jupiter-test")
    monkeypatch.setenv("SOLANA_INTEL_MAX_TOKENS", "2")
    first_pool = 1767225600  # 2026-01-01T00:00:00Z

    def handler(request: httpx.Request):
        if request.url.path == "/tokens/v2/recent":
            assert request.headers["x-api-key"] == "jupiter-test"
            return httpx.Response(200, json=[
                token(MINT_A, "A", "2026-01-01T00:00:00Z"),
                token(MINT_B, "B", "2026-01-01T00:00:00Z"),
            ])
        assert request.url.path == "/defi/v2/tokens/top_traders"
        assert request.headers["x-api-key"] == "birdeye-test"
        query = parse_qs(request.url.query.decode())
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
        snapshot = await SolanaIntelService(client).snapshot()

    assert snapshot["summary"]["enriched_tokens"] == 2
    assert snapshot["providers"]["birdeye"]["available"] is True
    main = next(row for row in snapshot["wallets"] if row["wallet"] == WALLET)
    risky = next(row for row in snapshot["wallets"] if row["wallet"] == RISKY_WALLET)
    assert main["tokens_traded"] == 2
    assert main["wins"] == 2
    assert main["early_buys"] == 2
    assert main["median_entry_seconds"] == 52.5
    assert risky["risk_penalty"] == 28
    assert main["score"] > risky["score"]


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
