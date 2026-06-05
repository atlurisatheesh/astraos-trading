"""Initial schema — all tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Users ─────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), server_default="user"),
        sa.Column("risk_profile", postgresql.JSONB, server_default="{}"),
        sa.Column("broker_config", postgresql.JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Instruments ───────────────────────────────────
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(30), nullable=False, index=True),
        sa.Column("exchange", sa.String(10), nullable=False),
        sa.Column("instrument_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("lot_size", sa.Integer, server_default="1"),
        sa.Column("tick_size", sa.Numeric(10, 4), server_default="0.05"),
        sa.Column("sector", sa.String(100)),
        sa.Column("industry", sa.String(100)),
        sa.Column("expiry", sa.Date),
        sa.Column("strike", sa.Numeric(18, 4)),
        sa.Column("isin", sa.String(20)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("meta", postgresql.JSONB, server_default="{}"),
        sa.UniqueConstraint("symbol", "exchange", "instrument_type", "expiry", "strike", name="uq_instrument"),
    )

    # ── Watchlists ────────────────────────────────────
    op.create_table(
        "watchlists",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("instrument_ids", postgresql.ARRAY(sa.Integer), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Strategies ────────────────────────────────────
    op.create_table(
        "strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("strategy_type", sa.String(50), nullable=False),
        sa.Column("asset_class", sa.String(20), nullable=False),
        sa.Column("timeframe", sa.String(20), nullable=False),
        sa.Column("parameters", postgresql.JSONB, server_default="{}"),
        sa.Column("risk_limits", postgresql.JSONB, server_default="{}"),
        sa.Column("algo_id", sa.String(100)),
        sa.Column("is_approved", sa.Boolean, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("false")),
        sa.Column("backtest_results", postgresql.JSONB),
        sa.Column("wfe_score", sa.Numeric(5, 4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Signals ───────────────────────────────────────
    op.create_table(
        "signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id")),
        sa.Column("instrument_id", sa.Integer, sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("signal_type", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 4)),
        sa.Column("target_price", sa.Numeric(18, 4)),
        sa.Column("stop_loss", sa.Numeric(18, 4)),
        sa.Column("time_horizon", sa.String(30)),
        sa.Column("reasoning", postgresql.JSONB, nullable=False),
        sa.Column("agent_scores", postgresql.JSONB),
        sa.Column("regime", sa.String(30)),
        sa.Column("risk_reward", sa.Numeric(8, 4)),
        sa.Column("is_executed", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    # ── Orders ────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("signals.id")),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id")),
        sa.Column("instrument_id", sa.Integer, sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("broker", sa.String(30), nullable=False),
        sa.Column("broker_order_id", sa.String(100)),
        sa.Column("order_type", sa.String(20), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("product", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(18, 4)),
        sa.Column("trigger_price", sa.Numeric(18, 4)),
        sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
        sa.Column("filled_quantity", sa.Integer, server_default="0"),
        sa.Column("average_price", sa.Numeric(18, 4)),
        sa.Column("risk_checks", postgresql.JSONB, server_default="{}"),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("parent_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Positions ─────────────────────────────────────
    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("instrument_id", sa.Integer, sa.ForeignKey("instruments.id"), nullable=False),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id")),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("average_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("current_price", sa.Numeric(18, 4)),
        sa.Column("unrealized_pnl", sa.Numeric(18, 4), server_default="0"),
        sa.Column("realized_pnl", sa.Numeric(18, 4), server_default="0"),
        sa.Column("stop_loss", sa.Numeric(18, 4)),
        sa.Column("target", sa.Numeric(18, 4)),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("is_open", sa.Boolean, server_default=sa.text("true")),
    )

    # ── Audit Log ─────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", sa.String(100)),
        sa.Column("details", postgresql.JSONB, nullable=False),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Risk Events ───────────────────────────────────
    op.create_table(
        "risk_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id")),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=False),
        sa.Column("action_taken", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Portfolio Snapshots ───────────────────────────
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("invested_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("cash", sa.Numeric(18, 4), server_default="0"),
        sa.Column("day_pnl", sa.Numeric(18, 4), server_default="0"),
        sa.Column("total_pnl", sa.Numeric(18, 4), server_default="0"),
        sa.Column("total_pnl_pct", sa.Numeric(8, 4), server_default="0"),
        sa.Column("holdings", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── News Archive ──────────────────────────────────
    op.create_table(
        "news_archive",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("symbols", postgresql.ARRAY(sa.String(30))),
        sa.Column("sentiment_score", sa.Numeric(5, 4)),
        sa.Column("sentiment_label", sa.String(20)),
        sa.Column("summary", sa.Text),
        sa.Column("content_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Alerts ────────────────────────────────────────
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("alert_type", sa.String(30), nullable=False),
        sa.Column("condition", sa.String(20), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 4), nullable=False),
        sa.Column("message", sa.String(500)),
        sa.Column("channels", postgresql.JSONB, server_default='{"websocket": true}'),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("is_triggered", sa.Boolean, server_default=sa.text("false")),
        sa.Column("triggered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── User Settings ─────────────────────────────────
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("telegram_chat_id", sa.String(50)),
        sa.Column("email_alerts", sa.Boolean, server_default=sa.text("true")),
        sa.Column("telegram_alerts", sa.Boolean, server_default=sa.text("false")),
        sa.Column("websocket_alerts", sa.Boolean, server_default=sa.text("true")),
        sa.Column("alert_on_signal", sa.Boolean, server_default=sa.text("true")),
        sa.Column("alert_on_order_fill", sa.Boolean, server_default=sa.text("true")),
        sa.Column("alert_on_risk_event", sa.Boolean, server_default=sa.text("true")),
        sa.Column("preferences", postgresql.JSONB, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Trade Journal ─────────────────────────────────
    op.create_table(
        "trade_journal",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id")),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("exit_price", sa.Numeric(18, 4)),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("pnl", sa.Numeric(18, 4), server_default="0"),
        sa.Column("emotion", sa.String(30)),
        sa.Column("notes", sa.Text),
        sa.Column("tags", postgresql.JSONB, server_default="{}"),
        sa.Column("trade_date", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── Performance indexes ───────────────────────────
    op.create_index("ix_portfolio_snapshots_user_date", "portfolio_snapshots", ["user_id", "date"])
    op.create_index("ix_news_archive_published", "news_archive", ["published_at"])
    op.create_index("ix_news_archive_symbols", "news_archive", ["symbols"], postgresql_using="gin")
    op.create_index("ix_alerts_user_active", "alerts", ["user_id", "is_active"])
    op.create_index("ix_trade_journal_user_date", "trade_journal", ["user_id", "trade_date"])
    op.create_index("ix_signals_created", "signals", ["created_at"])
    op.create_index("ix_orders_user_status", "orders", ["user_id", "status"])


def downgrade() -> None:
    op.drop_table("trade_journal")
    op.drop_table("user_settings")
    op.drop_table("alerts")
    op.drop_table("news_archive")
    op.drop_table("portfolio_snapshots")
    op.drop_table("risk_events")
    op.drop_table("audit_log")
    op.drop_table("positions")
    op.drop_table("orders")
    op.drop_table("signals")
    op.drop_table("strategies")
    op.drop_table("watchlists")
    op.drop_table("instruments")
    op.drop_table("users")
