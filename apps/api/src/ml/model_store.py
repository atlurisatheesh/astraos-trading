# type: ignore
"""AstraOS ML — Model persistence to database.

backup_active_model(): mirror the active model file + metrics into Postgres.
restore_active_model(): rebuild data/models/ from the DB after a restart.

Keeps only the latest active artifact (single row) to cap DB size.
"""

import json

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ..core.config import get_settings
from ..models.ml_artifact import MLModelArtifact
from .model_registry import CURRENT_MODEL, CURRENT_METRICS, ACTIVE_POINTER, MODEL_DIR

logger = structlog.get_logger()


def _own_session_factory():
    """Short-lived engine per call — safe from any thread/event loop.

    Training runs in a worker thread with its own loop; reusing the app's
    pooled engine there raises 'attached to a different loop'.
    """
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def backup_active_model() -> bool:
    """Copy the active model file into the DB (replaces previous backup)."""
    if not CURRENT_MODEL.exists():
        logger.warning("No active model file to back up")
        return False
    try:
        payload = CURRENT_MODEL.read_bytes()
        metrics = {}
        if CURRENT_METRICS.exists():
            metrics = json.loads(CURRENT_METRICS.read_text())
        version = int(metrics.get("version", 0) or 0)

        engine, factory = _own_session_factory()
        try:
            async with factory() as session:
                await session.execute(delete(MLModelArtifact))
                session.add(MLModelArtifact(
                    version=version,
                    metrics_json=json.dumps(metrics),
                    payload=payload,
                    is_active=True,
                ))
                await session.commit()
        finally:
            await engine.dispose()

        logger.info("Model backed up to DB", version=version, size_kb=len(payload) // 1024)
        return True
    except Exception as e:
        logger.error("Model backup failed", error=str(e))
        return False


async def restore_active_model() -> bool:
    """Restore the active model from DB if the local file is missing."""
    if CURRENT_MODEL.exists():
        return True  # disk copy survived, nothing to do
    try:
        engine, factory = _own_session_factory()
        try:
            async with factory() as session:
                result = await session.execute(
                    select(MLModelArtifact).where(MLModelArtifact.is_active == True)  # noqa: E712
                    .order_by(MLModelArtifact.created_at.desc()).limit(1)
                )
                row = result.scalar_one_or_none()
        finally:
            await engine.dispose()

        if not row:
            logger.info("No model backup in DB — predictions unavailable until next training")
            return False

        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        CURRENT_MODEL.write_bytes(row.payload)
        metrics = json.loads(row.metrics_json or "{}")
        CURRENT_METRICS.write_text(json.dumps(metrics, indent=2))
        ACTIVE_POINTER.write_text(json.dumps({
            "active_version": row.version,
            "accuracy": metrics.get("accuracy", 0),
            "promoted_at": metrics.get("registered_at", ""),
            "model_path": str(CURRENT_MODEL),
            "restored_from_db": True,
        }, indent=2))

        logger.info("Model restored from DB", version=row.version,
                    size_kb=len(row.payload) // 1024)
        return True
    except Exception as e:
        logger.error("Model restore failed", error=str(e))
        return False
