"""AstraOS Tests — API Health Check."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Health endpoint returns healthy status."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "AstraOS API"
    # Providers are env-dependent (yfinance/angel_one, paper/angel) —
    # assert presence, not specific values
    assert "market_data" in data["providers"]
    assert "broker" in data["providers"]


@pytest.mark.asyncio
async def test_openapi_docs(client: AsyncClient):
    """OpenAPI docs are available in debug mode."""
    resp = await client.get("/docs")
    assert resp.status_code == 200
