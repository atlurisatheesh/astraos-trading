# type: ignore
"""AstraOS — Email Notification Service (SMTP).

Sends trade alerts, daily P&L summaries, and weekly market digests
via SMTP (Gmail / Outlook / custom relay).
"""

import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

import structlog

from ..core.config import settings

logger = structlog.get_logger()
IST = ZoneInfo("Asia/Kolkata")


def is_configured() -> bool:
    """Check if SMTP credentials are provided."""
    return bool(settings.smtp_user and settings.smtp_password and settings.alert_email_to)


def _build_msg(subject: str, html_body: str, to: Optional[str] = None) -> MIMEMultipart:
    """Build a MIME email message."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.alert_email_from or settings.smtp_user
    msg["To"] = to or settings.alert_email_to
    msg.attach(MIMEText(html_body, "html"))
    return msg


def _send_sync(msg: MIMEMultipart) -> bool:
    """Send email synchronously (runs in thread pool)."""
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        logger.debug("Email sent successfully", to=msg["To"])
        return True
    except Exception as e:
        logger.error("Email send failed", error=str(e))
        return False


async def send_email(subject: str, html_body: str, to: Optional[str] = None) -> bool:
    """Send an HTML email asynchronously.

    Args:
        subject: Email subject line.
        html_body: HTML content of the email.
        to: Override recipient (defaults to config `alert_email_to`).

    Returns:
        True if sent successfully.
    """
    if not is_configured():
        logger.debug("Email not configured — skipping delivery.")
        return False

    msg = _build_msg(subject, html_body, to)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send_sync, msg)


# ── Pre-built Templates ──

async def send_trade_alert(
    symbol: str, side: str, quantity: int, price: float, reason: str = ""
) -> bool:
    """Send a formatted trade execution email."""
    color = "#22c55e" if side.upper() == "BUY" else "#ef4444"
    action = "BOUGHT" if side.upper() == "BUY" else "SOLD"
    now = datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")

    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width:480px; margin:auto; border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
      <div style="background:{color}; padding:16px 24px;">
        <h2 style="margin:0; color:white;">{'🟢' if side.upper()=='BUY' else '🔴'} {action}</h2>
      </div>
      <div style="padding:24px;">
        <table style="width:100%; border-collapse:collapse;">
          <tr><td style="padding:8px 0; color:#888;">Asset</td><td style="padding:8px 0; font-weight:bold;">{symbol}</td></tr>
          <tr><td style="padding:8px 0; color:#888;">Quantity</td><td style="padding:8px 0;">{quantity}</td></tr>
          <tr><td style="padding:8px 0; color:#888;">Price</td><td style="padding:8px 0;">₹{price:,.2f}</td></tr>
          <tr><td style="padding:8px 0; color:#888;">Value</td><td style="padding:8px 0;">₹{quantity * price:,.2f}</td></tr>
        </table>
        {"<p style='margin-top:12px; color:#666; font-style:italic;'>Reason: " + reason + "</p>" if reason else ""}
        <p style="margin-top:16px; font-size:12px; color:#aaa;">{now} · Quantus AI Auto-Trader</p>
      </div>
    </div>
    """
    return await send_email(f"Trade Alert: {action} {symbol}", html)


async def send_daily_summary(
    total_pnl: float, win_rate: float, trade_count: int, positions: list[dict]
) -> bool:
    """Send end-of-day portfolio summary email."""
    pnl_color = "#22c55e" if total_pnl >= 0 else "#ef4444"
    date_str = datetime.now(IST).strftime("%d %b %Y")

    rows = ""
    for p in positions[:20]:
        sym = p.get("symbol", "?")
        pnl = p.get("pnl", 0)
        rc = "#22c55e" if pnl >= 0 else "#ef4444"
        rows += f"<tr><td style='padding:6px 8px;'>{sym}</td><td style='padding:6px 8px; color:{rc};'>₹{pnl:,.2f}</td></tr>"

    html = f"""
    <div style="font-family:'Segoe UI',sans-serif; max-width:520px; margin:auto; border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
      <div style="background:linear-gradient(135deg,#1e1b4b,#312e81); padding:20px 24px;">
        <h2 style="margin:0; color:white;">📊 Daily Report — {date_str}</h2>
      </div>
      <div style="padding:24px;">
        <div style="display:flex; gap:16px; margin-bottom:20px;">
          <div style="flex:1; text-align:center; padding:12px; background:#f8f8f8; border-radius:8px;">
            <div style="font-size:24px; font-weight:bold; color:{pnl_color};">₹{total_pnl:,.2f}</div>
            <div style="font-size:12px; color:#888; margin-top:4px;">Total P&L</div>
          </div>
          <div style="flex:1; text-align:center; padding:12px; background:#f8f8f8; border-radius:8px;">
            <div style="font-size:24px; font-weight:bold;">{trade_count}</div>
            <div style="font-size:12px; color:#888; margin-top:4px;">Trades</div>
          </div>
          <div style="flex:1; text-align:center; padding:12px; background:#f8f8f8; border-radius:8px;">
            <div style="font-size:24px; font-weight:bold;">{win_rate:.0f}%</div>
            <div style="font-size:12px; color:#888; margin-top:4px;">Win Rate</div>
          </div>
        </div>
        {"<table style='width:100%; border-collapse:collapse;'><thead><tr><th style='text-align:left; padding:6px 8px; border-bottom:1px solid #eee;'>Symbol</th><th style='text-align:left; padding:6px 8px; border-bottom:1px solid #eee;'>P&L</th></tr></thead><tbody>" + rows + "</tbody></table>" if rows else ""}
        <p style="margin-top:16px; font-size:12px; color:#aaa;">Quantus AI · Auto-generated report</p>
      </div>
    </div>
    """
    return await send_email(f"Quantus Daily Report — {date_str}", html)


async def send_weekly_digest(
    weekly_pnl: float, best_trade: dict, worst_trade: dict, total_trades: int
) -> bool:
    """Send weekly market digest email."""
    date_str = datetime.now(IST).strftime("%d %b %Y")
    pnl_color = "#22c55e" if weekly_pnl >= 0 else "#ef4444"

    html = f"""
    <div style="font-family:'Segoe UI',sans-serif; max-width:520px; margin:auto; border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
      <div style="background:linear-gradient(135deg,#064e3b,#065f46); padding:20px 24px;">
        <h2 style="margin:0; color:white;">📈 Weekly Digest — Week ending {date_str}</h2>
      </div>
      <div style="padding:24px;">
        <div style="text-align:center; margin-bottom:20px;">
          <div style="font-size:32px; font-weight:bold; color:{pnl_color};">₹{weekly_pnl:,.2f}</div>
          <div style="font-size:14px; color:#888;">Weekly P&L</div>
        </div>
        <table style="width:100%; border-collapse:collapse;">
          <tr><td style="padding:8px 0; color:#888;">Total Trades</td><td style="padding:8px 0; font-weight:bold;">{total_trades}</td></tr>
          <tr><td style="padding:8px 0; color:#888;">Best Trade</td><td style="padding:8px 0; color:#22c55e;">{best_trade.get('symbol','—')} (₹{best_trade.get('pnl',0):,.2f})</td></tr>
          <tr><td style="padding:8px 0; color:#888;">Worst Trade</td><td style="padding:8px 0; color:#ef4444;">{worst_trade.get('symbol','—')} (₹{worst_trade.get('pnl',0):,.2f})</td></tr>
        </table>
        <p style="margin-top:16px; font-size:12px; color:#aaa;">Quantus AI · Auto-generated digest</p>
      </div>
    </div>
    """
    return await send_email(f"Quantus Weekly Digest — {date_str}", html)
