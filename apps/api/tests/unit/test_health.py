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
    assert data["providers"]["market_data"] == "yfinance"
    assert data["providers"]["broker"] == "paper"


@pytest.mark.asyncio
async def test_openapi_docs(client: AsyncClient):
    """OpenAPI docs are available in debug mode."""
    resp = await client.get("/docs")
    assert resp.status_code == 200
