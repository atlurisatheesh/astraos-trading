# type: ignore
"""AstraOS — Live Portfolio Monitor.

Hooks into the fast `live_scanner.py` loop to evaluate user positions
against Stop-Loss (SL), Take-Profit (TP), and Trailing Stop-Loss (T-SL) targets
every single second.
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from ..core.database import async_session_maker
from ..models.position import Position
from ..models.user import User
from ..scheduler.engine import push_feed
from ..services.broker_factory import execute_order
from ..services.telegram_service import notify_trigger_hit

logger = structlog.get_logger()
IST = ZoneInfo("Asia/Kolkata")

# In-memory cache of active positions to avoid DB queries every second
_active_positions: list[Position] = []
_last_db_sync: float = 0


async def _sync_positions() -> None:
    """Sync active open positions from the DB into memory."""
    global _active_positions, _last_db_sync

    now = datetime.now(IST).timestamp()
    if now - _last_db_sync < 15:  # Sync max once every 15 seconds
        return

    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(Position).where(Position.status == "OPEN").join(User)
            )
            _active_positions = result.scalars().all()
            _last_db_sync = now
    except Exception as e:
        logger.error("Failed to sync portfolio positions", error=str(e))


async def _handle_trigger(
    position: Position, current_price: float, trigger_type: str, message: str
) -> None:
    """Execute sequence when a SL/TP trigger is hit."""
    logger.warning("Portfolio Trigger Hit", symbol=position.symbol, trigger=trigger_type)

    push_feed(
        "TRADE_EXIT",
        f"🚨 {trigger_type} HIT: Exiting {position.quantity}x {position.symbol} @ ₹{current_price:,.2f}",
        {"symbol": position.symbol, "price": current_price, "reason": message},
    )

    try:
        # Load user to get broker config
        async with async_session_maker() as db:
            user = await db.get(User, position.user_id)
            if not user or not user.broker_config:
                logger.error("Cannot auto-execute exit: No broker configured for user.")
                return

            broker_id = user.broker_config.get("broker")
            broker_env = user.broker_config.get("environment", "PAPER")

            if not broker_id:
                logger.error("No valid broker ID in config.")
                return

            # Submit market order to close position
            side = "SELL" if position.side == "BUY" else "BUY"
            await execute_order(
                user_id=user.id,
                broker_id=broker_id,
                broker_env=broker_env,
                symbol=position.symbol,
                side=side,
                quantity=position.quantity,
                order_type="MARKET",
            )
            
            # Close position in DB
            position.status = "CLOSED"
            position.exit_price = current_price
            position.exit_date = datetime.now(IST)
            pnl = (
                (current_price - position.entry_price) * position.quantity
                if position.side == "BUY"
                else (position.entry_price - current_price) * position.quantity
            )
            position.pnl = pnl
            db.add(position)
            await db.commit()
            
            push_feed("TRADE_EXECUTED", f"✅ Successfully closed {position.symbol} position.")
            
            # Send instant Telegram alert to the user's phone
            asyncio.create_task(
                notify_trigger_hit(
                    symbol=position.symbol,
                    trigger_type=trigger_type,
                    price=current_price,
                    pnl=pnl
                )
            )

    except Exception as e:
        logger.error("Trigger execution failed", error=str(e))
        push_feed("ERROR", f"Failed to execute {trigger_type} for {position.symbol}")


async def monitor_tick(symbol: str, price_data: dict[str, Any]) -> None:
    """Evaluate all active positions for this symbol on every single tick.
    
    Called directly by the 1-second `live_scanner.py` loop.
    """
    await _sync_positions()

    current_price = float(price_data.get("price", 0))
    if current_price <= 0:
        return

    # Find all open positions for this arriving symbol
    positions = [p for p in _active_positions if p.symbol == symbol]
    
    for pos in positions:
        # 1. Check Take-Profit (TP)
        if pos.take_profit:
            if pos.side == "BUY" and current_price >= pos.take_profit:
                await _handle_trigger(pos, current_price, "TAKE_PROFIT", "Target Reached")
                continue
            elif pos.side == "SELL" and current_price <= pos.take_profit:
                await _handle_trigger(pos, current_price, "TAKE_PROFIT", "Target Reached")
                continue

        # 2. Check Stop-Loss (SL)
        if pos.stop_loss:
            if pos.side == "BUY" and current_price <= pos.stop_loss:
                await _handle_trigger(pos, current_price, "STOP_LOSS", "Stop Loss Hit")
                continue
            elif pos.side == "SELL" and current_price >= pos.stop_loss:
                await _handle_trigger(pos, current_price, "STOP_LOSS", "Stop Loss Hit")
                continue

        # 3. Handle Trailing Stop-Loss (T-SL)
        # If the price moves by `trailing_step` in our favor, move the SL up.
        trailing_step = getattr(pos, "trailing_step", None)
        if trailing_step and trailing_step > 0 and pos.stop_loss:
            if pos.side == "BUY":
                # Find the distance from SL to current price
                dist = current_price - pos.stop_loss
                if dist > trailing_step * 2:
                    # Move SL up by trailing_step
                    new_sl = pos.stop_loss + trailing_step
                    try:
                        async with async_session_maker() as db:
                            db_pos = await db.get(Position, pos.id)
                            db_pos.stop_loss = new_sl
                            await db.commit()
                            pos.stop_loss = new_sl  # update in-memory cache
                            push_feed("INFO", f"📈 T-SL Moved: {pos.symbol} stop-loss trailed up to ₹{new_sl:.2f}")
                    except Exception:
                        pass
