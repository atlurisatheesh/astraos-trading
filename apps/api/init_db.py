"""Initialize database by creating all tables. Run before starting the server."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# Use env var if set, otherwise default to local dev SQLite
DB_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data/astraos.db")
DB_URL_SYNC = os.environ.get("DATABASE_URL_SYNC", "sqlite:///./data/astraos.db")

# Override so models/config pick up the right URL
os.environ["DATABASE_URL"] = DB_URL
os.environ["DATABASE_URL_SYNC"] = DB_URL_SYNC

from sqlalchemy.ext.asyncio import create_async_engine
from src.core.database import Base
from src.models.user import User
from src.models.instrument import Instrument
from src.models.trading import (
    Order, Position, Strategy, Signal, Watchlist, AuditLog, RiskEvent,
    KillSwitchState, PortfolioSnapshot, NewsArchive, Alert, UserSettings, TradeJournal,
)


async def main():
    print(f"[init_db] Connecting to: {DB_URL}")
    engine = create_async_engine(DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    tables = sorted(Base.metadata.tables.keys())
    print(f"[init_db] ✅ {len(tables)} tables ensured: {', '.join(tables)}")
    await engine.dispose()


asyncio.run(main())
