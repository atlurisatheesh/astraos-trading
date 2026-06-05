"""AstraOS — Portfolio Service.

Aggregates positions across brokers, computes P&L,
and creates daily portfolio snapshots.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.trading import Position, Order, PortfolioSnapshot
from ..models.user import User


async def get_portfolio_summary(user: User, db: AsyncSession) -> dict:
    """Return portfolio summary: total value, invested, cash, P&L, positions."""
    result = await db.execute(
        select(Position).where(
            Position.user_id == user.id, Position.is_open == True  # noqa: E712
        )
    )
    positions = result.scalars().all()

    total_value = Decimal("0")
    invested_value = Decimal("0")
    day_pnl = Decimal("0")
    total_pnl = Decimal("0")

    position_items = []
    for p in positions:
        cost = Decimal(str(p.average_cost)) * Decimal(str(p.quantity))
        current = Decimal(str(p.current_price or p.average_cost)) * Decimal(str(p.quantity))
        unrealized = current - cost
        invested_value += cost
        total_value += current
        total_pnl += unrealized
        day_pnl += Decimal(str(p.day_pnl or 0))

        position_items.append({
            "id": str(p.id),
            "symbol": p.symbol,
            "side": p.side,
            "quantity": p.quantity,
            "average_cost": float(p.average_cost),
            "current_price": float(p.current_price or 0),
            "unrealized_pnl": float(unrealized),
            "realized_pnl": float(p.realized_pnl or 0),
            "is_open": p.is_open,
        })

    cash = Decimal("0")  # Could be fetched from broker adapter
    total_pnl_pct = (total_pnl / invested_value * 100) if invested_value else Decimal("0")

    return {
        "total_value": float(total_value + cash),
        "invested_value": float(invested_value),
        "cash": float(cash),
        "day_pnl": float(day_pnl),
        "total_pnl": float(total_pnl),
        "total_pnl_pct": float(total_pnl_pct),
        "positions": position_items,
    }


async def get_portfolio_history(user: User, db: AsyncSession, days: int = 30) -> list[dict]:
    """Return daily portfolio snapshots for the given period."""
    since = date.today() - timedelta(days=days)
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(
            and_(
                PortfolioSnapshot.user_id == user.id,
                PortfolioSnapshot.date >= since,
            )
        )
        .order_by(PortfolioSnapshot.date)
    )
    snapshots = result.scalars().all()
    return [
        {
            "date": str(s.date),
            "total_value": float(s.total_value),
            "invested_value": float(s.invested_value),
            "cash": float(s.cash),
            "day_pnl": float(s.day_pnl),
            "total_pnl": float(s.total_pnl),
            "total_pnl_pct": float(s.total_pnl_pct),
        }
        for s in snapshots
    ]


async def get_pnl_breakdown(user: User, db: AsyncSession) -> dict:
    """Return realized + unrealized P&L breakdown."""
    # Realized: sum of closed positions
    closed_result = await db.execute(
        select(
            func.sum(Position.realized_pnl),
            func.count(Position.id),
        ).where(
            Position.user_id == user.id, Position.is_open == False  # noqa: E712
        )
    )
    row = closed_result.one()
    realized_pnl = float(row[0] or 0)
    closed_count = row[1]

    # Unrealized from open positions
    open_result = await db.execute(
        select(Position).where(
            Position.user_id == user.id, Position.is_open == True  # noqa: E712
        )
    )
    open_positions = open_result.scalars().all()
    unrealized_pnl = sum(
        (float(p.current_price or p.average_cost) - float(p.average_cost)) * p.quantity
        for p in open_positions
    )

    return {
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": realized_pnl + unrealized_pnl,
        "closed_trades": closed_count,
        "open_positions": len(open_positions),
    }


async def capture_daily_snapshot(user: User, db: AsyncSession) -> PortfolioSnapshot:
    """Create a daily portfolio snapshot (called by scheduler)."""
    summary = await get_portfolio_summary(user, db)
    snapshot = PortfolioSnapshot(
        user_id=user.id,
        date=date.today(),
        total_value=summary["total_value"],
        invested_value=summary["invested_value"],
        cash=summary["cash"],
        day_pnl=summary["day_pnl"],
        total_pnl=summary["total_pnl"],
        total_pnl_pct=summary["total_pnl_pct"],
        holdings=summary["positions"],
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot
