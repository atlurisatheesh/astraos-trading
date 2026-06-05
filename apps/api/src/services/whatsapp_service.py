# type: ignore
"""AstraOS — WhatsApp Notification Service (via Twilio API).

Sends instant trade alerts and portfolio summaries to the user's phone via WhatsApp.
Uses the Twilio WhatsApp Business API for reliable delivery.
"""

import aiohttp
import base64
import structlog
from typing import Optional

from ..core.config import settings

logger = structlog.get_logger()

TWILIO_API_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def is_configured() -> bool:
    """Check if WhatsApp / Twilio credentials are provided."""
    return bool(
        settings.whatsapp_account_sid
        and settings.whatsapp_auth_token
        and settings.whatsapp_from_number
    )


async def send_whatsapp_message(to_number: str, text: str) -> bool:
    """Send a WhatsApp message via Twilio API.
    
    Args:
        to_number: Recipient phone in E.164 format (e.g. "+919876543210")
        text: Message body (plain text, max 1600 chars)
        
    Returns:
        True if sent successfully.
    """
    if not is_configured():
        logger.debug("WhatsApp not configured — skipping delivery.")
        return False

    url = TWILIO_API_URL.format(sid=settings.whatsapp_account_sid)
    
    # Twilio uses Basic Auth
    auth_str = f"{settings.whatsapp_account_sid}:{settings.whatsapp_auth_token}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()

    payload = {
        "From": settings.whatsapp_from_number,
        "To": f"whatsapp:{to_number}" if not to_number.startswith("whatsapp:") else to_number,
        "Body": text[:1600],  # Twilio limit
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=payload,
                headers={"Authorization": f"Basic {auth_b64}"},
                timeout=15,
            ) as response:
                if response.status in (200, 201):
                    logger.debug("WhatsApp message sent", to=to_number)
                    return True
                else:
                    err = await response.text()
                    logger.error("WhatsApp API error", status=response.status, error=err)
                    return False
    except Exception as e:
        logger.error("Failed to send WhatsApp message", error=str(e))
        return False


# ── Pre-built Alert Templates ──

async def notify_trade_whatsapp(
    to_number: str, symbol: str, side: str, quantity: int, price: float, reason: str = ""
) -> None:
    """Send a trade execution alert via WhatsApp."""
    emoji = "🟢" if side.upper() == "BUY" else "🔴"
    action = "BOUGHT" if side.upper() == "BUY" else "SOLD"

    msg = (
        f"{emoji} *TRADE EXECUTED*\n\n"
        f"*Action:* {action}\n"
        f"*Asset:* {symbol}\n"
        f"*Qty:* {quantity}\n"
        f"*Price:* ₹{price:,.2f}\n"
        f"*Value:* ₹{quantity * price:,.2f}\n"
    )
    if reason:
        msg += f"\n_{reason}_"
    msg += "\n\n— Quantus AI"

    await send_whatsapp_message(to_number, msg)


async def notify_trigger_whatsapp(
    to_number: str, symbol: str, trigger_type: str, price: float, pnl: float
) -> None:
    """Send a SL/TP trigger hit alert via WhatsApp."""
    emoji = "🎯" if trigger_type == "TAKE_PROFIT" else "🛡️"
    pnl_emoji = "✅" if pnl >= 0 else "❌"

    msg = (
        f"{emoji} *{trigger_type.replace('_', ' ')} HIT*\n\n"
        f"*Asset:* {symbol}\n"
        f"*Exit Price:* ₹{price:,.2f}\n\n"
        f"{pnl_emoji} *Realized P&L:* ₹{pnl:,.2f}\n\n"
        f"— Quantus AI"
    )

    await send_whatsapp_message(to_number, msg)


async def notify_daily_whatsapp(
    to_number: str, total_pnl: float, win_rate: float, trade_count: int
) -> None:
    """Send end-of-day portfolio summary via WhatsApp."""
    emoji = "📈" if total_pnl >= 0 else "📉"

    msg = (
        f"📊 *DAILY SUMMARY*\n\n"
        f"{emoji} *Total P&L:* ₹{total_pnl:,.2f}\n"
        f"*Trades Today:* {trade_count}\n"
        f"*Win Rate:* {win_rate:.1f}%\n\n"
        f"— Quantus AI"
    )

    await send_whatsapp_message(to_number, msg)
