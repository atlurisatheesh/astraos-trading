"""AstraOS Tests — E2E Integration Tests.

Full end-to-end flows: register → login → portfolio → alerts → journal → settings.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestE2EPortfolioFlow:
    """E2E: Login → Get portfolio → Check history → Check P&L."""

    async def test_portfolio_summary(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/portfolio/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_value" in data
        assert "invested_value" in data
        assert "positions" in data

    async def test_portfolio_history(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/portfolio/history?days=7", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_portfolio_pnl(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/portfolio/pnl", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "realized_pnl" in data
        assert "unrealized_pnl" in data


@pytest.mark.asyncio
class TestE2EAlertFlow:
    """E2E: Create alert → List → Delete."""

    async def test_create_and_list_alerts(self, client: AsyncClient, auth_headers):
        # Create
        resp = await client.post("/api/v1/alerts/", headers=auth_headers, json={
            "symbol": "RELIANCE",
            "alert_type": "price",
            "condition": "above",
            "threshold": 3000.0,
            "channels": {"telegram": True, "email": False},
        })
        assert resp.status_code == 201
        alert_id = resp.json()["id"]

        # List
        resp = await client.get("/api/v1/alerts/", headers=auth_headers)
        assert resp.status_code == 200
        alerts = resp.json()
        assert len(alerts) >= 1
        assert any(a["id"] == alert_id for a in alerts)

        # Delete
        resp = await client.delete(f"/api/v1/alerts/{alert_id}", headers=auth_headers)
        assert resp.status_code == 200

        # Verify deleted
        resp = await client.get("/api/v1/alerts/", headers=auth_headers)
        assert all(a["id"] != alert_id for a in resp.json())

    async def test_delete_nonexistent_alert(self, client: AsyncClient, auth_headers):
        resp = await client.delete("/api/v1/alerts/99999", headers=auth_headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestE2EJournalFlow:
    """E2E: Create journal entry → List."""

    async def test_create_and_list_journal(self, client: AsyncClient, auth_headers):
        resp = await client.post("/api/v1/journal/", headers=auth_headers, json={
            "symbol": "RELIANCE",
            "side": "BUY",
            "entry_price": 2840.0,
            "quantity": 50,
            "pnl": 1825.0,
            "emotion": "Calm",
            "notes": "Strong OI buildup + momentum.",
            "trade_date": "2026-03-24",
        })
        assert resp.status_code == 201
        entry = resp.json()
        assert entry["symbol"] == "RELIANCE"
        assert entry["pnl"] == 1825.0

        # List
        resp = await client.get("/api/v1/journal/", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


@pytest.mark.asyncio
class TestE2ESettingsFlow:
    """E2E: Get settings → Update → Verify."""

    async def test_get_and_update_settings(self, client: AsyncClient, auth_headers):
        # Get (auto-creates defaults)
        resp = await client.get("/api/v1/settings/", headers=auth_headers)
        assert resp.status_code == 200

        # Update
        resp = await client.put("/api/v1/settings/", headers=auth_headers, json={
            "telegram_alerts": True,
            "email_alerts": False,
            "alert_price": True,
        })
        assert resp.status_code == 200

        # Verify
        resp = await client.get("/api/v1/settings/", headers=auth_headers)
        data = resp.json()
        assert data["telegram_alerts"] is True
        assert data["email_alerts"] is False


@pytest.mark.asyncio
class TestE2ERiskFlow:
    """E2E: Risk metrics and events."""

    async def test_risk_metrics(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/risk/metrics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "metrics" in data

    async def test_risk_events(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/risk/events", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
class TestE2EFullTradeFlow:
    """E2E: Register → Login → Place Order → Check Positions → View Portfolio."""

    async def test_full_trade_flow(self, client: AsyncClient):
        # 1. Register
        resp = await client.post("/api/v1/auth/register", json={
            "email": "trader@astraos.dev",
            "password": "SuperSecure12345!",
            "full_name": "E2E Trader",
        })
        assert resp.status_code == 201

        # 2. Login
        resp = await client.post("/api/v1/auth/login", json={
            "email": "trader@astraos.dev",
            "password": "SuperSecure12345!",
        })
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Check portfolio (empty)
        resp = await client.get("/api/v1/portfolio/summary", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total_value"] == 0

        # 4. Check positions (empty)
        resp = await client.get("/api/v1/positions/", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

        # 5. Create an alert
        resp = await client.post("/api/v1/alerts/", headers=headers, json={
            "symbol": "NIFTY",
            "alert_type": "price",
            "condition": "above",
            "threshold": 24000.0,
        })
        assert resp.status_code == 201

        # 6. Check settings
        resp = await client.get("/api/v1/settings/", headers=headers)
        assert resp.status_code == 200

        # 7. Add journal entry
        resp = await client.post("/api/v1/journal/", headers=headers, json={
            "symbol": "NIFTY",
            "side": "BUY",
            "entry_price": 23500.0,
            "quantity": 1,
        })
        assert resp.status_code == 201


@pytest.mark.asyncio
class TestE2EHealthAndPublicEndpoints:
    """E2E: Health check and public endpoints."""

    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    async def test_unauthenticated_portfolio(self, client: AsyncClient):
        """Protected endpoints return 401 without token."""
        resp = await client.get("/api/v1/portfolio/summary")
        assert resp.status_code in (401, 403)

    async def test_unauthenticated_alerts(self, client: AsyncClient):
        resp = await client.get("/api/v1/alerts/")
        assert resp.status_code in (401, 403)
