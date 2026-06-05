"""AstraOS Router — User Settings."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.dependencies import get_current_user
from ..models.trading import UserSettings
from ..models.user import User

router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


@router.get("/")
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user settings."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        # Auto-create default settings
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    return settings


@router.put("/")
async def update_settings(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user settings."""
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == current_user.id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = UserSettings(user_id=current_user.id)
        db.add(settings)

    allowed = {
        "telegram_chat_id", "email_alerts", "telegram_alerts",
        "websocket_alerts", "alert_price", "alert_volume",
        "alert_signal", "alert_news", "preferences",
    }
    for key, value in data.items():
        if key in allowed and hasattr(settings, key):
            setattr(settings, key, value)

    await db.commit()
    await db.refresh(settings)
    return settings
