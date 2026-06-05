"""AstraOS Router — Risk metrics and events."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.dependencies import get_current_user, require_admin
from ..models.trading import KillSwitchState, RiskEvent, Position
from ..models.user import User

router = APIRouter(prefix="/api/v1/risk", tags=["Risk"])


@router.get("/metrics")
async def get_risk_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compute current risk metrics from open positions."""
    result = await db.execute(
        select(Position).where(
            Position.user_id == current_user.id, Position.is_open == True  # noqa: E712
        )
    )
    positions = result.scalars().all()

    total_invested = sum(float(p.average_cost) * p.quantity for p in positions)
    total_current = sum(float(p.current_price or p.average_cost) * p.quantity for p in positions)
    total_pnl = total_current - total_invested
    capital = max(total_invested, 1)

    daily_loss_pct = abs(min(total_pnl, 0)) / capital * 100
    capital_at_risk = total_invested / capital * 100 if capital > 0 else 0

    metrics = [
        {"label": "Capital at Risk", "value": f"{min(capital_at_risk, 100):.1f}%", "max": "5%", "pct": min(int(capital_at_risk / 5 * 100), 100), "status": "safe" if capital_at_risk < 4 else "warning" if capital_at_risk < 5 else "danger"},
        {"label": "Daily Loss", "value": f"{daily_loss_pct:.1f}%", "max": "2%", "pct": min(int(daily_loss_pct / 2 * 100), 100), "status": "safe" if daily_loss_pct < 1.5 else "warning" if daily_loss_pct < 2 else "danger"},
        {"label": "Open Positions", "value": str(len(positions)), "max": "20", "pct": min(int(len(positions) / 20 * 100), 100), "status": "safe" if len(positions) < 15 else "warning"},
    ]

    return {"metrics": metrics, "position_count": len(positions), "total_invested": total_invested}


@router.get("/events")
async def get_risk_events(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List recent risk events for the current user."""
    result = await db.execute(
        select(RiskEvent)
        .where(RiskEvent.user_id == current_user.id)
        .order_by(desc(RiskEvent.created_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/kill-switch/status")
async def kill_switch_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Show active platform/account/strategy halt states relevant to the user."""
    result = await db.execute(
        select(KillSwitchState)
        .where(KillSwitchState.is_active.is_(True))
        .order_by(desc(KillSwitchState.created_at))
    )
    states = result.scalars().all()
    visible = [
        state
        for state in states
        if state.scope == "platform" or state.user_id == current_user.id or current_user.role == "admin"
    ]
    return {
        "active": bool(visible),
        "states": [
            {
                "id": state.id,
                "scope": state.scope,
                "user_id": str(state.user_id) if state.user_id else None,
                "strategy_id": str(state.strategy_id) if state.strategy_id else None,
                "reason": state.reason,
                "created_at": state.created_at,
            }
            for state in visible
        ],
    }


@router.post("/kill-switch/account")
async def trigger_account_kill(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Halt the current user's strategies and open positions."""
    from ..risk.kill_switch import account_kill

    return await account_kill(current_user.id, db)


@router.post("/kill-switch/platform")
async def trigger_platform_kill(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only platform-wide emergency halt."""
    from ..risk.kill_switch import platform_kill

    return await platform_kill(db)


@router.post("/kill-switch/clear")
async def clear_kill_switch(
    scope: str | None = Query(default=None, pattern="^(platform|account|strategy)$"),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin-only clear for active halt states."""
    from ..risk.kill_switch import KillSwitch

    cleared = await KillSwitch().clear(db, scope=scope)
    return {"cleared": cleared}


# ── Circuit Breaker (Level 0) ──────────────────────────────────────────────

@router.get("/circuit-breaker/status")
async def get_circuit_breaker_status(
    current_user: User = Depends(get_current_user),
):
    """Get Level 0 circuit breaker status — consecutive losses, daily P&L, mode."""
    from ..risk.circuit_breaker import circuit_breaker
    return circuit_breaker.get_status()


@router.post("/circuit-breaker/resume")
async def resume_circuit_breaker(
    admin: User = Depends(require_admin),
):
    """Admin-only: manually resume trading after circuit breaker pause."""
    from ..risk.circuit_breaker import circuit_breaker
    circuit_breaker.force_resume(reason=f"Manual resume by admin {admin.email}")
    return {"status": "resumed"}


# ── Position Sizing ────────────────────────────────────────────────────────

@router.post("/position-size")
async def calculate_position(
    symbol: str,
    entry_price: float,
    stop_loss: float,
    confidence: float = 70.0,
    current_user: User = Depends(get_current_user),
):
    """Calculate optimal position size using Half-Kelly criterion."""
    from ..risk.position_sizer import calculate_position_size

    capital = float(current_user.risk_profile.get("capital", 1_000_000)) if current_user.risk_profile else 1_000_000

    result = calculate_position_size(
        capital=capital,
        entry_price=entry_price,
        stop_loss=stop_loss,
        confidence=confidence,
    )
    return result.to_dict()


# ── Transaction Cost Estimator ─────────────────────────────────────────────

@router.post("/transaction-costs")
async def estimate_costs(
    turnover: float,
    segment: str = "equity_intraday",
    broker: str = "zerodha",
    lots: int = 1,
    current_user: User = Depends(get_current_user),
):
    """Estimate all-in transaction costs for a trade."""
    from ..quant.transaction_costs import (
        calculate_roundtrip_costs, Segment, Broker, estimate_breakeven_move,
    )

    seg = Segment(segment)
    brk = Broker(broker)
    costs = calculate_roundtrip_costs(turnover, turnover, seg, brk, lots)
    breakeven = estimate_breakeven_move(turnover / max(lots, 1), lots, seg, brk, lots)

    return {
        "costs": costs.to_dict(),
        "breakeven_move_per_unit": round(breakeven, 2),
    }
