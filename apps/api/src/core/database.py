"""AstraOS API — Async Database Engine & Session."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

# SQLite doesn't support pool_size/max_overflow
_is_sqlite = settings.database_url.startswith("sqlite")

_engine_kwargs = dict(
    echo=settings.app_debug,
    pool_pre_ping=True,
)
if not _is_sqlite:
    _engine_kwargs.update(pool_size=10, max_overflow=20)

engine = create_async_engine(
    settings.database_url,
    **_engine_kwargs,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: yields an async DB session, auto-closes."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
