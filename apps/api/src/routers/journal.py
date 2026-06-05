"""AstraOS Router — Trade Journal."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.trading import TradeJournal
from ..models.user import User

router = APIRouter(prefix="/api/v1/journal", tags=["Journal"])


class JournalCreate(BaseModel):
    symbol: str
    side: str = "BUY"
    entry_price: float
    exit_price: float | None = None
    quantity: int = 1
    pnl: float = 0.0
    emotion: str = ""
    notes: str = ""
    tags: list[str] = []
    trade_date: str | None = None


@router.get("/")
async def list_journal(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all journal entries for the current user."""
    result = await db.execute(
        select(TradeJournal)
        .where(TradeJournal.user_id == current_user.id)
        .order_by(desc(TradeJournal.trade_date))
    )
    return result.scalars().all()


@router.post("/", status_code=201)
async def create_journal_entry(
    data: JournalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new journal entry."""
    from datetime import date as date_type

    entry = TradeJournal(
        user_id=current_user.id,
        symbol=data.symbol,
        side=data.side,
        entry_price=data.entry_price,
        exit_price=data.exit_price,
        quantity=data.quantity,
        pnl=data.pnl,
        emotion=data.emotion,
        notes=data.notes,
        tags=data.tags,
        trade_date=date_type.fromisoformat(data.trade_date) if data.trade_date else date_type.today(),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry
