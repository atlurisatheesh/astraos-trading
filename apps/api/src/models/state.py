"""AstraOS Models — Scheduler state snapshots (KV).

Open positions, trailing stops, and generated signals live in process
memory; this table mirrors them so a Render restart doesn't silently
drop tracked positions or signal history.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class SchedulerState(Base):
    __tablename__ = "scheduler_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
