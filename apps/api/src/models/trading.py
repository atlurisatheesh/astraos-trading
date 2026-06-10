"""AstraOS Models — Signal, Strategy, Order, Position, Watchlist, AuditLog, RiskEvent, Portfolio, Alert, TradeJournal, NewsArchive."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from ..core.db_types import JSONB, UUID, ARRAY_JSON as ARRAY

from ..core.database import Base


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    instrument_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(20), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict)
    risk_limits: Mapped[dict] = mapped_column(JSONB, default=dict)
    algo_id: Mapped[str | None] = mapped_column(String(100))
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    backtest_results: Mapped[dict | None] = mapped_column(JSONB)
    wfe_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id")
    )
    instrument_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("instruments.id"), nullable=False
    )
    signal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    entry_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    target_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    time_horizon: Mapped[str | None] = mapped_column(String(30))
    reasoning: Mapped[dict] = mapped_column(JSONB, nullable=False)
    agent_scores: Mapped[dict | None] = mapped_column(JSONB)
    regime: Mapped[str | None] = mapped_column(String(30))
    risk_reward: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    is_executed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    signal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("signals.id")
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id")
    )
    instrument_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("instruments.id"), nullable=False
    )
    broker: Mapped[str] = mapped_column(String(30), nullable=False)
    broker_order_id: Mapped[str | None] = mapped_column(String(100))
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    product: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    trigger_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    average_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    risk_checks: Mapped[dict] = mapped_column(JSONB, default=dict)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    parent_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    instrument_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("instruments.id"), nullable=False
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id")
    )
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    target: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id")
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)
    action_taken: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class KillSwitchState(Base):
    """Durable trading halt state for platform, account, and strategy scopes."""

    __tablename__ = "kill_switch_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PortfolioSnapshot(Base):
    """Daily portfolio value snapshot for P&L tracking."""
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    invested_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    day_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    total_pnl_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("0"))
    holdings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class NewsArchive(Base):
    """Persisted news articles for historical analysis."""
    __tablename__ = "news_archive"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    symbols: Mapped[list[str] | None] = mapped_column(ARRAY(String(30)))
    sentiment_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    sentiment_label: Mapped[str | None] = mapped_column(String(20))
    summary: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Alert(Base):
    """User-configurable price/indicator alerts with delivery tracking."""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    message: Mapped[str | None] = mapped_column(String(500))
    channels: Mapped[dict] = mapped_column(JSONB, default=lambda: {"websocket": True})
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class UserSettings(Base):
    """User preferences and notification configuration."""
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    telegram_chat_id: Mapped[str | None] = mapped_column(String(50))
    email_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    websocket_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_signal: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_order_fill: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_risk_event: Mapped[bool] = mapped_column(Boolean, default=True)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TradeJournal(Base):
    """Trade journal entries for performance review."""
    __tablename__ = "trade_journal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id")
    )
    symbol: Mapped[str] = mapped_column(String(30), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    pnl: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    emotion: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[dict] = mapped_column(JSONB, default=dict)
    trade_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
