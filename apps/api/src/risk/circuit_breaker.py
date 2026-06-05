"""AstraOS Risk — Level 0 Circuit Breaker (Behavioural + Market).

Pre-kill-switch automatic halts that trigger before the situation gets bad
enough to need a kill switch. These are the "experienced trader's reflexes"
encoded into the system.

Operates in-memory for speed. Persists events to DB asynchronously.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog

logger = structlog.get_logger()
IST = ZoneInfo("Asia/Kolkata")


@dataclass
class CircuitState:
    consecutive_losses: int = 0
    total_losses_today: int = 0
    total_wins_today: int = 0
    day_pnl: float = 0.0
    week_pnl: float = 0.0
    month_pnl: float = 0.0
    capital: float = 1_000_000.0
    paused_until: float = 0.0
    pause_reason: str = ""
    trade_history: deque = field(default_factory=lambda: deque(maxlen=100))
    vix_history: deque = field(default_factory=lambda: deque(maxlen=60))
    last_reset_date: str = ""


class CircuitBreaker:
    """Level 0 protection — automatic behavioural circuit breakers."""

    MAX_CONSECUTIVE_LOSSES = 2
    CONSECUTIVE_LOSS_PAUSE_SECONDS = 1800  # 30 minutes

    MAX_DAILY_LOSS_PCT = 1.0    # 1% of capital → paper-only
    MAX_WEEKLY_LOSS_PCT = 3.0   # 3% → review mode
    MAX_MONTHLY_LOSS_PCT = 5.0  # 5% → full halt + retrain

    VIX_SPIKE_THRESHOLD = 30.0  # VIX % change in 5 minutes

    def __init__(self) -> None:
        self._state = CircuitState()

    @property
    def state(self) -> CircuitState:
        self._maybe_reset_daily()
        return self._state

    def _maybe_reset_daily(self) -> None:
        today = datetime.now(IST).strftime("%Y-%m-%d")
        if today != self._state.last_reset_date:
            self._state.consecutive_losses = 0
            self._state.total_losses_today = 0
            self._state.total_wins_today = 0
            self._state.day_pnl = 0.0
            self._state.last_reset_date = today

    def record_trade_result(self, pnl: float, symbol: str = "") -> dict:
        """Record a completed trade result and check circuit conditions."""
        self._maybe_reset_daily()
        s = self._state

        s.trade_history.append({
            "pnl": pnl,
            "symbol": symbol,
            "timestamp": time.time(),
        })

        s.day_pnl += pnl
        s.week_pnl += pnl
        s.month_pnl += pnl

        if pnl < 0:
            s.consecutive_losses += 1
            s.total_losses_today += 1
        else:
            s.consecutive_losses = 0
            s.total_wins_today += 1

        return self.check_all()

    def record_vix(self, vix_value: float) -> dict | None:
        """Record a VIX reading and check for spikes."""
        self._state.vix_history.append({
            "vix": vix_value,
            "timestamp": time.time(),
        })

        if len(self._state.vix_history) < 2:
            return None

        readings = list(self._state.vix_history)
        five_min_ago = time.time() - 300
        recent = [r for r in readings if r["timestamp"] >= five_min_ago]

        if len(recent) < 2:
            return None

        oldest = recent[0]["vix"]
        newest = recent[-1]["vix"]
        if oldest > 0:
            change_pct = ((newest - oldest) / oldest) * 100
            if change_pct > self.VIX_SPIKE_THRESHOLD:
                self._pause(3600, f"VIX spiked {change_pct:.1f}% in 5 minutes — halting all new entries")
                return {
                    "triggered": True,
                    "type": "vix_spike",
                    "vix_change_pct": round(change_pct, 2),
                    "action": "halt_new_entries_60min",
                }

        return None

    def check_all(self) -> dict:
        """Run all circuit breaker checks. Returns status dict."""
        s = self._state
        result = {
            "trading_allowed": True,
            "mode": "live",
            "triggers": [],
            "consecutive_losses": s.consecutive_losses,
            "day_pnl": round(s.day_pnl, 2),
            "day_pnl_pct": round(s.day_pnl / s.capital * 100, 4) if s.capital else 0,
        }

        # Check if we're currently paused
        if s.paused_until > time.time():
            remaining = int(s.paused_until - time.time())
            result["trading_allowed"] = False
            result["mode"] = "paused"
            result["pause_remaining_seconds"] = remaining
            result["pause_reason"] = s.pause_reason
            return result

        # Consecutive losses → 30-minute cooldown
        if s.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES:
            self._pause(
                self.CONSECUTIVE_LOSS_PAUSE_SECONDS,
                f"{s.consecutive_losses} consecutive losses — cooling off for 30 minutes",
            )
            result["trading_allowed"] = False
            result["mode"] = "cooldown"
            result["triggers"].append("consecutive_losses")

        # Daily loss → paper-only mode
        day_loss_pct = abs(s.day_pnl / s.capital * 100) if s.capital and s.day_pnl < 0 else 0
        if day_loss_pct >= self.MAX_DAILY_LOSS_PCT:
            result["trading_allowed"] = False
            result["mode"] = "paper_only"
            result["triggers"].append("daily_loss_limit")
            logger.warning("Circuit breaker: daily loss limit", pnl=s.day_pnl, pct=day_loss_pct)

        # Weekly loss → review mode (no auto-trading)
        week_loss_pct = abs(s.week_pnl / s.capital * 100) if s.capital and s.week_pnl < 0 else 0
        if week_loss_pct >= self.MAX_WEEKLY_LOSS_PCT:
            result["trading_allowed"] = False
            result["mode"] = "review_only"
            result["triggers"].append("weekly_loss_limit")

        # Monthly loss → full halt + recommend retrain
        month_loss_pct = abs(s.month_pnl / s.capital * 100) if s.capital and s.month_pnl < 0 else 0
        if month_loss_pct >= self.MAX_MONTHLY_LOSS_PCT:
            result["trading_allowed"] = False
            result["mode"] = "full_halt"
            result["triggers"].append("monthly_loss_limit")
            result["recommend_retrain"] = True

        return result

    def is_trading_allowed(self) -> bool:
        return self.check_all()["trading_allowed"]

    def force_resume(self, reason: str = "manual override") -> None:
        """Manually resume trading after a circuit breaker pause."""
        self._state.paused_until = 0
        self._state.pause_reason = ""
        self._state.consecutive_losses = 0
        logger.warning("Circuit breaker manually resumed", reason=reason)

    def set_capital(self, capital: float) -> None:
        self._state.capital = capital

    def reset_weekly(self) -> None:
        self._state.week_pnl = 0.0

    def reset_monthly(self) -> None:
        self._state.month_pnl = 0.0

    def _pause(self, seconds: int, reason: str) -> None:
        self._state.paused_until = time.time() + seconds
        self._state.pause_reason = reason
        logger.warning("Circuit breaker activated", reason=reason, pause_seconds=seconds)

    def get_status(self) -> dict:
        """Full status report."""
        s = self._state
        checks = self.check_all()
        return {
            **checks,
            "total_wins_today": s.total_wins_today,
            "total_losses_today": s.total_losses_today,
            "win_rate_today": round(
                s.total_wins_today / max(1, s.total_wins_today + s.total_losses_today) * 100, 1
            ),
            "week_pnl": round(s.week_pnl, 2),
            "month_pnl": round(s.month_pnl, 2),
        }


# Singleton
circuit_breaker = CircuitBreaker()
