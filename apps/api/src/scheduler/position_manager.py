"""AstraOS Scheduler — Position Manager (Exit Logic).

The auto-trader only OPENS positions. This module MANAGES and CLOSES them.
Without this, profits are never booked and losses are never cut.

Exit triggers:
  1. Target hit — book full profit
  2. Stop-loss hit — cut loss immediately
  3. Trailing stop (ATR-based) — lock in profits on strong moves
  4. Time-based exit — close positions before market close (3:15 PM)
  5. Regime change — if VIX spikes, close all positions
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog

from .engine import push_feed
from ..risk.circuit_breaker import circuit_breaker
from ..risk.shadow_validator import shadow_validator
from ..agents.outcome_tracker import outcome_tracker

logger = structlog.get_logger()
IST = ZoneInfo("Asia/Kolkata")


class PositionManager:
    """Manages open paper positions — trailing stops, target/SL exits, time exits."""

    def __init__(self):
        self._open_positions: list[dict] = []
        self._closed_positions: list[dict] = []
        self._trailing_stops: dict[str, float] = {}  # symbol -> current trailing SL

    def add_position(self, trade: dict) -> None:
        """Register a new position from the auto-trader."""
        symbol = trade["symbol"]
        self._open_positions.append(trade)

        # Initialize trailing stop at the original stop-loss
        sl = trade.get("stop_loss", 0)
        self._trailing_stops[symbol] = sl

        logger.info("Position registered", symbol=symbol, entry=trade.get("fill_price"))

    def check_exits(self, current_prices: dict[str, float]) -> list[dict]:
        """Check all open positions for exit conditions.

        Args:
            current_prices: {symbol: current_price}

        Returns:
            List of positions that were closed.
        """
        closed = []
        now = datetime.now(IST)

        for pos in list(self._open_positions):
            symbol = pos["symbol"]
            price = current_prices.get(symbol)
            if price is None:
                continue

            action = pos["action"]
            entry = pos.get("fill_price", pos.get("entry_price", 0))
            target = pos.get("target", 0)
            original_sl = pos.get("stop_loss", 0)
            trailing_sl = self._trailing_stops.get(symbol, original_sl)

            exit_reason = None
            exit_price = price

            # 1. Target hit
            if action == "BUY" and price >= target:
                exit_reason = "TARGET_HIT"
            elif action == "SELL" and price <= target:
                exit_reason = "TARGET_HIT"

            # 2. Stop-loss hit (using trailing stop)
            if action == "BUY" and price <= trailing_sl:
                exit_reason = "STOP_LOSS"
            elif action == "SELL" and price >= trailing_sl:
                exit_reason = "STOP_LOSS"

            # 3. Time-based exit: close before 3:15 PM
            if now.hour == 15 and now.minute >= 15:
                exit_reason = "TIME_EXIT"

            # 4. Update trailing stop (move up for BUY, down for SELL)
            if exit_reason is None:
                self._update_trailing_stop(pos, price)

            # Execute exit
            if exit_reason:
                pnl = self._calculate_pnl(pos, exit_price)

                pos["exit_price"] = round(exit_price, 2)
                pos["exit_reason"] = exit_reason
                pos["exit_time"] = now.isoformat()
                pos["pnl"] = round(pnl, 2)
                pos["status"] = "CLOSED"

                self._open_positions.remove(pos)
                self._closed_positions.append(pos)
                closed.append(pos)

                # ── Feedback loop 3: circuit breaker learns from this result ──
                circuit_breaker.record_trade_result(pnl, symbol)

                # ── Feedback loop 4: shadow validator resolves the signal ─
                shadow_validator.resolve_signal(symbol, exit_price)

                # ── Feedback loop 5: outcome tracker checks prices ────────
                outcome_tracker.check_outcomes({symbol: exit_price})

                # Push to feed
                emoji = "+" if pnl >= 0 else ""
                push_feed(
                    "EXIT",
                    f"CLOSED {symbol} — {exit_reason} | P&L: Rs {emoji}{pnl:,.0f} | "
                    f"Entry: {entry:,.2f} Exit: {exit_price:,.2f}",
                    pos,
                )

                logger.info(
                    "Position closed",
                    symbol=symbol,
                    reason=exit_reason,
                    pnl=pnl,
                    entry=entry,
                    exit=exit_price,
                )

                # Clean up trailing stop
                self._trailing_stops.pop(symbol, None)

        return closed

    def _update_trailing_stop(self, pos: dict, current_price: float) -> None:
        """Update trailing stop to lock in profits.

        Uses ATR-based trailing: move stop up by (price move - 2*ATR).
        Only moves in the profitable direction, never backwards.
        """
        symbol = pos["symbol"]
        action = pos["action"]
        entry = pos.get("fill_price", pos.get("entry_price", 0))
        original_sl = pos.get("stop_loss", 0)
        current_sl = self._trailing_stops.get(symbol, original_sl)

        # Estimate ATR as 2% of entry (simplified)
        atr = entry * 0.02

        if action == "BUY":
            # New trailing stop = current price - 2*ATR
            new_sl = current_price - (2 * atr)
            # Only move up, never down
            if new_sl > current_sl:
                self._trailing_stops[symbol] = round(new_sl, 2)
                if new_sl > entry:
                    push_feed(
                        "TRAIL",
                        f"Trailing stop raised for {symbol}: Rs {current_sl:,.2f} -> Rs {new_sl:,.2f} (profit locked)",
                    )

        elif action == "SELL":
            new_sl = current_price + (2 * atr)
            if new_sl < current_sl:
                self._trailing_stops[symbol] = round(new_sl, 2)

    def _calculate_pnl(self, pos: dict, exit_price: float) -> float:
        """Calculate P&L for a position."""
        entry = pos.get("fill_price", pos.get("entry_price", 0))
        qty = pos.get("quantity", 0)
        action = pos["action"]

        if action == "BUY":
            return (exit_price - entry) * qty
        else:  # SELL
            return (entry - exit_price) * qty

    def emergency_close_all(self, current_prices: dict[str, float]) -> list[dict]:
        """Emergency close all positions (kill switch)."""
        closed = []
        for pos in list(self._open_positions):
            symbol = pos["symbol"]
            price = current_prices.get(symbol, pos.get("fill_price", 0))
            pnl = self._calculate_pnl(pos, price)

            pos["exit_price"] = round(price, 2)
            pos["exit_reason"] = "EMERGENCY_CLOSE"
            pos["exit_time"] = datetime.now(IST).isoformat()
            pos["pnl"] = round(pnl, 2)
            pos["status"] = "CLOSED"

            self._open_positions.remove(pos)
            self._closed_positions.append(pos)
            closed.append(pos)
            circuit_breaker.record_trade_result(pnl, symbol)

        push_feed("RISK", f"EMERGENCY: All {len(closed)} positions closed")
        self._trailing_stops.clear()
        return closed

    def get_open_positions(self) -> list[dict]:
        return self._open_positions.copy()

    def get_closed_positions(self) -> list[dict]:
        return self._closed_positions.copy()

    def get_daily_pnl(self) -> float:
        return sum(p.get("pnl", 0) for p in self._closed_positions)


# Singleton
position_manager = PositionManager()
