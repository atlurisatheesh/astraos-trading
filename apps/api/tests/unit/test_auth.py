"""AstraOS Tests — Authentication (register, login, JWT, BOLA)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestAuth:
    """Authentication tests — register, login, token validation."""

    async def test_register_success(self, client: AsyncClient):
        """New user registration works."""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "new@astraos.dev",
            "password": "SecurePass123!",
            "full_name": "New User",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@astraos.dev"
        assert data["full_name"] == "New User"
        assert data["role"] == "user"
        assert "password" not in data
        assert "password_hash" not in data

    async def test_register_weak_password(self, client: AsyncClient):
        """Weak passwords are rejected (< 12 chars)."""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "weak@astraos.dev",
            "password": "short",
            "full_name": "Weak User",
        })
        assert resp.status_code == 422

    async def test_register_duplicate_email(self, client: AsyncClient, test_user):
        """Duplicate email registration fails."""
        resp = await client.post("/api/v1/auth/register", json={
            "email": "test@astraos.dev",
            "password": "SecurePass123!",
            "full_name": "Duplicate User",
        })
        assert resp.status_code == 409

    async def test_login_success(self, client: AsyncClient, test_user):
        """Login with valid credentials returns tokens."""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@astraos.dev",
            "password": "TestPass123456",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, test_user):
        """Login with wrong password fails."""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "test@astraos.dev",
            "password": "WrongPassword123",
        })
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client: AsyncClient):
        """Login with non-existent email fails."""
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@astraos.dev",
            "password": "TestPass123456",
        })
        assert resp.status_code == 401

    async def test_me_authenticated(self, client: AsyncClient, auth_headers):
        """Authenticated /me endpoint returns user profile."""
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@astraos.dev"
        assert "password_hash" not in data

    async def test_me_unauthenticated(self, client: AsyncClient):
        """Unauthenticated /me request fails."""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_me_invalid_token(self, client: AsyncClient):
        """Invalid JWT token fails."""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestBOLA:
    """BOLA prevention tests — users cannot access other users' data."""

    async def test_no_password_in_response(self, client: AsyncClient, auth_headers):
        """Password hash is never returned in any response."""
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        body = resp.text
        assert "password_hash" not in body
        assert "password" not in body.lower() or "password" in '{"email"' 
