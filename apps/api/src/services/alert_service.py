"""AstraOS — Alert Delivery Service.

Dispatches triggered alerts via Telegram, Email (SMTP), and WebSocket.
"""

import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings as app_settings
from ..models.trading import Alert, UserSettings

logger = logging.getLogger(__name__)


async def send_telegram(chat_id: str, message: str) -> bool:
    """Send a Telegram message via Bot API."""
    token = app_settings.telegram_bot_token
    if not token or not chat_id:
        logger.warning("Telegram not configured — skipping")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        })
        if resp.status_code == 200:
            logger.info("Telegram sent to %s", chat_id)
            return True
        logger.error("Telegram error: %s %s", resp.status_code, resp.text)
        return False


async def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email via SMTP (async with aiosmtplib or stdlib fallback)."""
    smtp_host = app_settings.smtp_host
    smtp_port = app_settings.smtp_port
    smtp_user = app_settings.smtp_user
    smtp_password = app_settings.smtp_password
    from_email = app_settings.alert_email_from

    if not smtp_host or not smtp_user:
        logger.warning("SMTP not configured — skipping email")
        return False

    msg = MIMEMultipart()
    msg["From"] = from_email or smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    try:
        import aiosmtplib
        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_password,
            use_tls=smtp_port == 465,
            start_tls=smtp_port == 587,
        )
        logger.info("Email sent to %s", to_email)
        return True
    except ImportError:
        # Fallback to synchronous stdlib (run in thread)
        import smtplib
        def _send():
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_port in (587,):
                    server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _send)
        logger.info("Email sent (sync fallback) to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Email send failed: %s", exc)
        return False


async def dispatch_alert(alert: Alert, db: AsyncSession) -> dict:
    """Dispatch an alert through its configured channels."""
    results: dict[str, bool] = {}

    # Get user settings for channel preferences
    us_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == alert.user_id)
    )
    user_settings = us_result.scalar_one_or_none()

    channels = alert.channels or {}
    msg = f"🔔 *Alert Triggered*\n\n*{alert.symbol}* — {alert.alert_type}\n{alert.message}"

    # Telegram
    if channels.get("telegram", True) and (not user_settings or user_settings.telegram_alerts):
        chat_id = (user_settings.telegram_chat_id if user_settings else None) or app_settings.telegram_chat_id
        if chat_id:
            results["telegram"] = await send_telegram(chat_id, msg)

    # Email
    if channels.get("email", True) and (not user_settings or user_settings.email_alerts):
        to_email = app_settings.alert_email_to
        if to_email:
            results["email"] = await send_email(
                to_email,
                f"Alert: {alert.symbol} {alert.alert_type}",
                f"<h3>Alert Triggered</h3><p><b>{alert.symbol}</b> — {alert.message}</p>",
            )

    # WebSocket broadcast (always on)
    if channels.get("websocket", True):
        try:
            from ..routers.websocket import broadcast_risk_event
            await broadcast_risk_event({
                "alert_id": alert.id,
                "symbol": alert.symbol,
                "message": alert.message,
                "type": "alert",
            })
            results["websocket"] = True
        except Exception:
            results["websocket"] = False

    return results


async def check_and_trigger_alerts(db: AsyncSession, quotes: dict[str, float]) -> list[int]:
    """Check all active alerts against current prices and trigger if met.

    Args:
        db: Database session.
        quotes: Dict mapping symbol -> current price.

    Returns:
        List of triggered alert IDs.
    """
    from datetime import datetime, timezone

    result = await db.execute(
        select(Alert).where(
            and_(Alert.is_active == True, Alert.is_triggered == False)  # noqa: E712
        )
    )
    alerts = result.scalars().all()
    triggered_ids: list[int] = []

    for alert in alerts:
        price = quotes.get(alert.symbol)
        if price is None:
            continue

        should_trigger = False
        if alert.condition == "above" and price >= alert.threshold:
            should_trigger = True
        elif alert.condition == "below" and price <= alert.threshold:
            should_trigger = True
        elif alert.condition == "crosses":
            should_trigger = True  # Simplified: triggers on any price match

        if should_trigger:
            alert.is_triggered = True
            alert.triggered_at = datetime.now(timezone.utc)
            await dispatch_alert(alert, db)
            triggered_ids.append(alert.id)

    if triggered_ids:
        await db.commit()

    return triggered_ids
