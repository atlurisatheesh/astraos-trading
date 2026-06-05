"""AstraOS Router — Alerts (create, list, delete, trigger)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.trading import Alert
from ..models.user import User

router = APIRouter(prefix="/api/v1/alerts", tags=["Alerts"])


class AlertCreate(BaseModel):
    symbol: str
    alert_type: str = "price"  # price | volume | signal | news
    condition: str = "above"   # above | below | crosses
    threshold: float
    message: str = ""
    channels: dict = {}        # {"telegram": true, "email": true, "websocket": true}


@router.get("/")
async def list_alerts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all alerts for the current user."""
    result = await db.execute(
        select(Alert)
        .where(Alert.user_id == current_user.id)
        .order_by(Alert.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", status_code=201)
async def create_alert(
    data: AlertCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new alert rule."""
    alert = Alert(
        user_id=current_user.id,
        symbol=data.symbol,
        alert_type=data.alert_type,
        condition=data.condition,
        threshold=data.threshold,
        message=data.message or f"{data.symbol} {data.condition} {data.threshold}",
        channels=data.channels,
        is_active=True,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an alert (BOLA: scoped to user)."""
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(404, "Alert not found")
    await db.delete(alert)
    await db.commit()
    return {"ok": True}
