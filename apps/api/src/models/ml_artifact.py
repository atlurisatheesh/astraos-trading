"""AstraOS Models — Persisted ML model artifacts.

Render free tier has an ephemeral disk: every deploy/restart wipes
data/models/. The active model is mirrored into this table so it can be
restored on startup instead of waiting for the next weekly retrain.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db_types import UUID
from ..core.database import Base


class MLModelArtifact(Base):
    __tablename__ = "ml_model_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
