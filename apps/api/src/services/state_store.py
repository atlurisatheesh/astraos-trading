"""AstraOS Services — Scheduler state persistence (KV over DB).

save_state()/load_state() use a short-lived engine per call so they are
safe from any thread or event loop (scheduler jobs, worker threads,
startup). Writes are infrequent (position changes, signal batches).
"""

import asyncio
import json

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ..core.config import get_settings
from ..models.state import SchedulerState

logger = structlog.get_logger()


def _own_session_factory():
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def save_state(key: str, value) -> bool:
    """Upsert a JSON-serializable value under a key."""
    try:
        payload = json.dumps(value, default=str)
        engine, factory = _own_session_factory()
        try:
            async with factory() as session:
                row = await session.get(SchedulerState, key)
                if row:
                    row.value_json = payload
                else:
                    session.add(SchedulerState(key=key, value_json=payload))
                await session.commit()
        finally:
            await engine.dispose()
        return True
    except Exception as e:
        logger.warning("State save failed", key=key, error=str(e))
        return False


async def load_state(key: str, default=None):
    """Load a value by key, or default when missing/corrupt."""
    try:
        engine, factory = _own_session_factory()
        try:
            async with factory() as session:
                row = await session.get(SchedulerState, key)
        finally:
            await engine.dispose()
        if row is None:
            return default
        return json.loads(row.value_json)
    except Exception as e:
        logger.warning("State load failed", key=key, error=str(e))
        return default


def save_state_background(key: str, value) -> None:
    """Fire-and-forget save from sync code running inside an event loop."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(save_state(key, value))
    except RuntimeError:
        # No running loop (e.g. unit test sync context) — skip silently
        pass
