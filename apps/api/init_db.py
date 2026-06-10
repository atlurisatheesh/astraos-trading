"""Initialize database by creating all tables. Run before starting the server."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use env var if set, otherwise default to local dev SQLite
DB_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./data/astraos.db")
os.environ.setdefault("DATABASE_URL", DB_URL)
os.environ.setdefault("DATABASE_URL_SYNC", os.environ.get("DATABASE_URL_SYNC", "sqlite:///./data/astraos.db"))


async def main():
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.orm import DeclarativeBase

        class _Base(DeclarativeBase):
            pass

        # Import models against a fresh Base so we don't conflict
        # with the app's Base. We'll use the app's Base directly.
        from src.core.database import Base
        from src.models.user import User  # noqa: F401
        from src.models.instrument import Instrument  # noqa: F401
        from src.models.trading import (  # noqa: F401
            Order, Position, Strategy, Signal, Watchlist, AuditLog, RiskEvent,
            KillSwitchState, PortfolioSnapshot, NewsArchive, Alert, UserSettings, TradeJournal,
        )

        print(f"[init_db] DB URL: {DB_URL}")
        print(f"[init_db] Tables in metadata: {sorted(Base.metadata.tables.keys())}")

        engine = create_async_engine(DB_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

        print(f"[init_db] ✅ Tables created successfully")

    except Exception as e:
        import traceback
        print(f"[init_db] ERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        # Don't exit with error — let the server start and handle it
        sys.exit(0)


asyncio.run(main())
