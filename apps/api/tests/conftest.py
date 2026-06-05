"""AstraOS Tests — Shared fixtures and test configuration."""

import os
import uuid
from decimal import Decimal
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event, String, Text, Integer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID, ARRAY

from src.core.database import Base, get_db
from src.core.security import hash_password, create_access_token
from src.main import app
from src.models.user import User
from src.models.instrument import Instrument


# -- SQLite Compatibility Layer --
# Override PostgreSQL types with SQLite-compatible equivalents for tests
# This keeps production code using native PG types while tests use SQLite (free, no Docker)

from sqlalchemy import TypeDecorator, types
import json


class JSONBForSQLite(TypeDecorator):
    """Store JSONB as TEXT in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None


class UUIDForSQLite(TypeDecorator):
    """Store UUID as VARCHAR(36) in SQLite."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value)
        return None


class ARRAYForSQLite(TypeDecorator):
    """Store ARRAY as JSON TEXT in SQLite."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return "[]"

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return []


# Monkey-patch the column types for SQLite
# This runs before any table creation so SQLite gets compatible types
@event.listens_for(Base.metadata, "before_create")
def patch_types_for_sqlite(target, connection, **kw):
    """Replace PG-specific types with SQLite equivalents for testing."""
    if "sqlite" in str(connection.engine.url):
        for table in target.tables.values():
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSONBForSQLite()
                elif isinstance(column.type, PG_UUID):
                    column.type = UUIDForSQLite()
                elif isinstance(column.type, ARRAY):
                    column.type = ARRAYForSQLite()


# Use SQLite for tests (zero cost, no Docker needed)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    # Clean up test.db
    if os.path.exists("./test.db"):
        try:
            os.remove("./test.db")
        except PermissionError:
            pass


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session."""
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async test client with overridden DB dependency."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        email="test@astraos.dev",
        password_hash=hash_password("TestPass123456"),
        full_name="Test User",
        role="user",
        risk_profile={"capital": 1000000},
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict:
    """Provide auth headers with valid JWT for test user."""
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def test_instrument(db_session: AsyncSession) -> Instrument:
    """Create a test instrument."""
    instrument = Instrument(
        symbol="RELIANCE",
        exchange="NSE",
        instrument_type="EQ",
        name="Reliance Industries Ltd",
        lot_size=1,
        tick_size=Decimal("0.05"),
        sector="Energy",
        industry="Oil & Gas",
        is_active=True,
    )
    db_session.add(instrument)
    await db_session.commit()
    await db_session.refresh(instrument)
    return instrument
