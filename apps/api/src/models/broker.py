"""AstraOS Models — Persisted broker credentials (encrypted at rest)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db_types import UUID
from ..core.database import Base


class BrokerCredential(Base):
    """Encrypted broker credentials so sessions survive server restarts.

    The credential payload is Fernet-encrypted with a key derived from
    JWT_SECRET_KEY — never stored in plaintext.
    """

    __tablename__ = "broker_credentials"
    __table_args__ = (UniqueConstraint("user_id", "broker", name="uq_user_broker"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    broker: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
