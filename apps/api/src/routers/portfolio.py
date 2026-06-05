"""AstraOS Router — Portfolio (summary, history, P&L)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.user import User
from ..services.portfolio_service import (
    get_portfolio_summary,
    get_portfolio_history,
    get_pnl_breakdown,
)

router = APIRouter(prefix="/api/v1/portfolio", tags=["Portfolio"])


@router.get("/summary")
async def portfolio_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full portfolio summary with positions."""
    return await get_portfolio_summary(current_user, db)


@router.get("/history")
async def portfolio_history(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Daily portfolio value history for charts."""
    return await get_portfolio_history(current_user, db, days)


@router.get("/pnl")
async def portfolio_pnl(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Realized + unrealized P&L breakdown."""
    return await get_pnl_breakdown(current_user, db)
