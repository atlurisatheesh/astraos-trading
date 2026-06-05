# type: ignore
"""AstraOS — Telegram Notification Service.

Sends instant trade execution alerts, SL/TP hits, and daily summaries
to the user's phone via the Telegram Bot API.
"""

import aiohttp
import structlog
from typing import Any

from ..core.config import settings

logger = structlog.get_logger()

# Telegram API constants
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

def is_configured() -> bool:
    """Check if Telegram bot credentials are provided."""
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


async def send_telegram_message(text: str, parse_mode: str = "HTML") -> bool:
    """Send a message to the configured Telegram chat.
    
    Args:
        text (str): The message text to send.
        parse_mode (str): Formatting mode ("HTML" or "MarkdownV2").
        
    Returns:
        bool: True if successful, False otherwise.
    """
    if not is_configured():
        logger.debug("Telegram not configured. Skipping message delivery.")
        return False

    url = TELEGRAM_API_URL.format(token=settings.telegram_bot_token)
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as response:
                if response.status == 200:
                    logger.debug("Telegram message sent successfully")
                    return True
                else:
                    err_data = await response.text()
                    logger.error("Telegram API error", status=response.status, error=err_data)
                    return False
        return False
    except Exception as e:
        logger.error("Failed to send Telegram message", error=str(e))
        return False


async def notify_trade_execution(symbol: str, side: str, quantity: int, price: float, reason: str = "") -> None:
    """Send a formatted trade execution alert."""
    emoji = "🟢" if side.upper() == "BUY" else "🔴"
    action = "BOUGHT" if side.upper() == "BUY" else "SOLD"
    
    msg = (
        f"<b>{emoji} TRADE EXECUTED</b>\n\n"
        f"<b>Action:</b> {action}\n"
        f"<b>Asset:</b> {symbol}\n"
        f"<b>Qty:</b> {quantity}\n"
        f"<b>Price:</b> ₹{price:,.2f}\n"
    )
    if reason:
        msg += f"\n<i>Reason: {reason}</i>"
        
    await send_telegram_message(msg)


async def notify_trigger_hit(symbol: str, trigger_type: str, price: float, pnl: float) -> None:
    """Send an alert when Stop-Loss or Take-Profit is hit."""
    emoji = "🎯" if trigger_type == "TAKE_PROFIT" else "🛡️"
    pnl_emoji = "🟩" if pnl >= 0 else "🟥"
    
    msg = (
        f"<b>{emoji} {trigger_type.replace('_', ' ')} HIT</b>\n\n"
        f"<b>Asset:</b> {symbol}\n"
        f"<b>Exit Price:</b> ₹{price:,.2f}\n\n"
        f"<b>{pnl_emoji} Realized P&L:</b> ₹{pnl:,.2f}"
    )
    
    await send_telegram_message(msg)


async def notify_daily_summary(total_pnl: float, win_rate: float, trade_count: int) -> None:
    """Send end-of-day portfolio summary."""
    emoji = "📈" if total_pnl >= 0 else "📉"
    
    msg = (
        f"<b>📊 DAILY SUMMARY</b>\n\n"
        f"{emoji} <b>Total P&L:</b> ₹{total_pnl:,.2f}\n"
        f"<b>Trades Today:</b> {trade_count}\n"
        f"<b>Win Rate:</b> {win_rate:.1f}%\n\n"
        f"<i>AstraOS Auto-Trader</i>"
    )
    
    await send_telegram_message(msg)
