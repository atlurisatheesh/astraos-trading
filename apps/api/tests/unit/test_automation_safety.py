"""Automation safety regressions for broker sessions, scheduler controls, and kill switch."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import create_access_token, hash_password
from src.models.trading import KillSwitchState
from src.models.user import User


@pytest.mark.asyncio
async def test_broker_routes_require_auth(client: AsyncClient):
    resp = await client.post("/api/v1/broker/order", json={"symbol": "RELIANCE"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_broker_sessions_are_scoped_per_user(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    login = await client.post("/api/v1/broker/login", headers=auth_headers, json={"broker": "paper"})
    assert login.status_code == 200
    assert login.json()["status"] == "success"

    active = await client.get("/api/v1/broker/active", headers=auth_headers)
    assert active.status_code == 200
    assert active.json()["sessions"] == [{"broker": "paper", "logged_in": True}]

    other = User(
        id=uuid.uuid4(),
        email="other@astraos.dev",
        password_hash=hash_password("OtherPass123456"),
        full_name="Other User",
        role="user",
        risk_profile={"capital": 1000000},
    )
    db_session.add(other)
    await db_session.commit()

    other_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(other.id)})}"}
    active_other = await client.get("/api/v1/broker/active", headers=other_headers)
    assert active_other.status_code == 200
    assert active_other.json()["sessions"] == []


@pytest.mark.asyncio
async def test_scheduler_controls_require_auth_and_admin(client: AsyncClient, auth_headers: dict):
    status = await client.get("/api/v1/scheduler/status")
    assert status.status_code == 401

    toggle = await client.post("/api/v1/scheduler/auto-trade/toggle?enabled=true", headers=auth_headers)
    assert toggle.status_code == 403


@pytest.mark.asyncio
async def test_account_kill_switch_is_durable(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_user: User,
):
    resp = await client.post("/api/v1/risk/kill-switch/account", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["action"] == "account_killed"

    result = await db_session.execute(
        select(KillSwitchState).where(
            KillSwitchState.scope == "account",
            KillSwitchState.user_id == test_user.id,
            KillSwitchState.is_active.is_(True),
        )
    )
    assert result.scalar_one_or_none() is not None

    status = await client.get("/api/v1/risk/kill-switch/status", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["active"] is True
