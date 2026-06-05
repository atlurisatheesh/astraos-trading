"""AstraOS Router — Signals (AI-generated buy/sell/hold signals)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.trading import Signal
from ..models.user import User
from ..schemas import SignalResponse

router = APIRouter(prefix="/api/v1/signals", tags=["Signals"])


@router.get("/", response_model=list[SignalResponse])
async def list_signals(
    instrument_id: int | None = None,
    signal_type: str | None = None,
    min_confidence: float = Query(default=0, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List AI signals, optionally filtered by instrument, type, confidence."""
    query = select(Signal).order_by(desc(Signal.created_at)).limit(limit)

    if instrument_id:
        query = query.where(Signal.instrument_id == instrument_id)
    if signal_type:
        query = query.where(Signal.signal_type == signal_type)
    if min_confidence > 0:
        query = query.where(Signal.confidence >= min_confidence)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single signal with full reasoning trace."""
    from fastapi import HTTPException
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal
