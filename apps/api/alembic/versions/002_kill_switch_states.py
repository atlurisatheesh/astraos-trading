"""Add durable kill switch state.

Revision ID: 002_kill_switch_states
Revises: 001_initial
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_kill_switch_states"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kill_switch_states",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("strategies.id")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("reason", sa.Text),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_kill_switch_states_scope", "kill_switch_states", ["scope"])
    op.create_index("ix_kill_switch_states_user_id", "kill_switch_states", ["user_id"])
    op.create_index("ix_kill_switch_states_strategy_id", "kill_switch_states", ["strategy_id"])
    op.create_index("ix_kill_switch_states_is_active", "kill_switch_states", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_kill_switch_states_is_active", table_name="kill_switch_states")
    op.drop_index("ix_kill_switch_states_strategy_id", table_name="kill_switch_states")
    op.drop_index("ix_kill_switch_states_user_id", table_name="kill_switch_states")
    op.drop_index("ix_kill_switch_states_scope", table_name="kill_switch_states")
    op.drop_table("kill_switch_states")
