"""AstraOS Router — Positions."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.trading import Position
from ..models.user import User
from ..schemas import PositionResponse

router = APIRouter(prefix="/api/v1/positions", tags=["Positions"])


@router.get("/", response_model=list[PositionResponse])
async def list_positions(
    is_open: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all positions for the current user (BOLA: scoped)."""
    query = (
        select(Position)
        .where(Position.user_id == current_user.id, Position.is_open == is_open)
    )
    result = await db.execute(query)
    return result.scalars().all()
