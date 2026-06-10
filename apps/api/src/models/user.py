"""AstraOS Models — User."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db_types import JSONB, UUID

from ..core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user")
    risk_profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    broker_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    notification_preferences: Mapped[dict] = mapped_column(
        JSONB,
        default=lambda: {
            "email": True,
            "telegram": False,
            "whatsapp": False,
            "telegram_chat_id": "",
            "whatsapp_number": "",
        },
    )
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
