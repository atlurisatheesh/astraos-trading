"""AstraOS Risk - durable kill switch controls."""

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.trading import KillSwitchState, Order, Position, RiskEvent

logger = structlog.get_logger()

OPEN_ORDER_STATUSES = (
    "DRAFT",
    "RISK_PENDING",
    "PENDING_RISK",  # legacy spelling kept so old rows are halted too
    "RISK_APPROVED",
    "HUMAN_PENDING",
    "HUMAN_APPROVED",
    "SENT",
    "ACKNOWLEDGED",
    "PARTIALLY_FILLED",
)


class KillSwitch:
    """Query and mutate persistent halt state."""

    async def is_triggered(
        self,
        db: AsyncSession,
        *,
        user_id=None,
        strategy_id: str | None = None,
    ) -> bool:
        """Return true when a platform, account, or strategy halt is active."""
        result = await db.execute(
            select(KillSwitchState).where(KillSwitchState.is_active.is_(True))
        )
        states = result.scalars().all()

        for state in states:
            if state.scope == "platform":
                return True
            if user_id is not None and state.scope == "account" and state.user_id == user_id:
                return True
            if (
                strategy_id is not None
                and state.scope == "strategy"
                and str(state.strategy_id) == str(strategy_id)
            ):
                return True
        return False

    async def trigger(
        self,
        db: AsyncSession,
        *,
        scope: str,
        user_id=None,
        strategy_id: str | None = None,
        reason: str = "",
        triggered_by=None,
    ) -> KillSwitchState:
        """Activate a halt for a scope, reusing an existing active record."""
        result = await db.execute(
            select(KillSwitchState).where(
                KillSwitchState.scope == scope,
                KillSwitchState.user_id == user_id,
                KillSwitchState.strategy_id == strategy_id,
                KillSwitchState.is_active.is_(True),
            )
        )
        state = result.scalar_one_or_none()
        if state:
            state.reason = reason or state.reason
            state.triggered_by = triggered_by or state.triggered_by
            return state

        state = KillSwitchState(
            scope=scope,
            user_id=user_id,
            strategy_id=strategy_id,
            reason=reason,
            triggered_by=triggered_by,
            is_active=True,
        )
        db.add(state)
        return state

    async def clear(
        self,
        db: AsyncSession,
        *,
        scope: str | None = None,
        user_id=None,
        strategy_id: str | None = None,
    ) -> int:
        """Clear matching active halt records and return affected row count."""
        stmt = update(KillSwitchState).where(KillSwitchState.is_active.is_(True))
        if scope:
            stmt = stmt.where(KillSwitchState.scope == scope)
        if user_id is not None:
            stmt = stmt.where(KillSwitchState.user_id == user_id)
        if strategy_id is not None:
            stmt = stmt.where(KillSwitchState.strategy_id == strategy_id)

        result = await db.execute(stmt.values(is_active=False))
        return int(result.rowcount or 0)


async def is_platform_halted(db: AsyncSession) -> bool:
    """Convenience helper for global background jobs without a user context."""
    return await KillSwitch().is_triggered(db)


async def strategy_kill(strategy_id: str, user_id, db: AsyncSession) -> dict:
    """Level 1: Disable one strategy and cancel its open orders."""
    from ..models.trading import Strategy

    await db.execute(
        update(Strategy)
        .where(Strategy.id == strategy_id, Strategy.user_id == user_id)
        .values(is_active=False)
    )

    await db.execute(
        update(Order)
        .where(
            Order.strategy_id == strategy_id,
            Order.user_id == user_id,
            Order.status.in_(OPEN_ORDER_STATUSES),
        )
        .values(status="CANCELLED", rejection_reason="Kill switch: strategy halt")
    )

    await KillSwitch().trigger(
        db,
        scope="strategy",
        user_id=user_id,
        strategy_id=strategy_id,
        reason="Strategy halt",
        triggered_by=user_id,
    )

    db.add(
        RiskEvent(
            user_id=user_id,
            strategy_id=strategy_id,
            event_type="kill_switch_strategy",
            severity="CRITICAL",
            details={"strategy_id": strategy_id},
            action_taken="strategy_disabled_orders_cancelled",
        )
    )

    logger.warning("KILL SWITCH L1: Strategy halted", strategy_id=strategy_id)
    return {"level": 1, "action": "strategy_killed", "strategy_id": strategy_id}


async def account_kill(user_id, db: AsyncSession) -> dict:
    """Level 2: halt all strategies and mark all account positions closed."""
    from ..models.trading import Strategy

    await db.execute(update(Strategy).where(Strategy.user_id == user_id).values(is_active=False))

    await db.execute(
        update(Order)
        .where(Order.user_id == user_id, Order.status.in_(OPEN_ORDER_STATUSES))
        .values(status="CANCELLED", rejection_reason="Kill switch: account halt")
    )

    await db.execute(
        update(Position)
        .where(Position.user_id == user_id, Position.is_open.is_(True))
        .values(is_open=False)
    )

    await KillSwitch().trigger(
        db,
        scope="account",
        user_id=user_id,
        reason="Account halt",
        triggered_by=user_id,
    )

    db.add(
        RiskEvent(
            user_id=user_id,
            event_type="kill_switch_account",
            severity="EMERGENCY",
            details={"user_id": str(user_id)},
            action_taken="all_positions_closed_strategies_halted",
        )
    )

    logger.critical("KILL SWITCH L2: Account halted", user_id=str(user_id))
    return {"level": 2, "action": "account_killed", "user_id": str(user_id)}


async def platform_kill(db: AsyncSession) -> dict:
    """Level 3: emergency platform-wide halt."""
    from ..models.trading import Strategy

    await db.execute(update(Strategy).values(is_active=False))

    await db.execute(
        update(Order)
        .where(Order.status.in_(OPEN_ORDER_STATUSES))
        .values(status="CANCELLED", rejection_reason="Kill switch: PLATFORM HALT")
    )

    await db.execute(update(Position).where(Position.is_open.is_(True)).values(is_open=False))

    await KillSwitch().trigger(db, scope="platform", reason="Platform halt")

    db.add(
        RiskEvent(
            event_type="kill_switch_platform",
            severity="EMERGENCY",
            details={"scope": "platform_wide"},
            action_taken="ALL_positions_closed_ALL_strategies_halted",
        )
    )

    logger.critical("KILL SWITCH L3: PLATFORM HALT - All positions closed")
    return {"level": 3, "action": "platform_killed"}
