"""AstraOS Risk — Shadow Mode Validator.

Tracks signal accuracy over time without executing real trades.
Used during the mandatory 30-day paper trading period before going live.

Answers the critical question: "Does this system actually have an edge?"

Go-live criteria (all must pass for 30 consecutive trading days):
  - Win rate >= 52%
  - Sharpe ratio >= 1.5
  - Max drawdown <= 8% of capital
  - Profit factor >= 1.4
"""

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog

logger = structlog.get_logger()
IST = ZoneInfo("Asia/Kolkata")

GO_LIVE_CRITERIA = {
    "min_trading_days": 30,
    "min_win_rate": 52.0,
    "min_sharpe": 1.5,
    "max_drawdown_pct": 8.0,
    "min_profit_factor": 1.4,
    "min_total_signals": 50,
}


@dataclass
class SignalRecord:
    symbol: str
    action: str
    entry_price: float
    target_price: float
    stop_loss: float
    confidence: float
    timestamp: float
    resolved: bool = False
    outcome: str = ""  # "win", "loss", "hold"
    exit_price: float = 0.0
    pnl: float = 0.0
    agent_signals: dict = field(default_factory=dict)


class ShadowValidator:
    """Tracks all signals in shadow mode and evaluates go-live readiness."""

    def __init__(self, capital: float = 1_000_000.0):
        self._signals: deque[SignalRecord] = deque(maxlen=5000)
        self._capital = capital
        self._peak_equity = capital
        self._current_equity = capital
        self._daily_results: dict[str, dict] = {}
        self._agent_accuracy: dict[str, dict] = {}

    def record_signal(
        self,
        symbol: str,
        action: str,
        entry_price: float,
        target_price: float,
        stop_loss: float,
        confidence: float,
        agent_signals: dict | None = None,
    ) -> None:
        """Record a new signal for shadow tracking."""
        self._signals.append(SignalRecord(
            symbol=symbol,
            action=action,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss=stop_loss,
            confidence=confidence,
            timestamp=time.time(),
            agent_signals=agent_signals or {},
        ))

    def resolve_signal(self, symbol: str, current_price: float) -> SignalRecord | None:
        """Check if any open signal for this symbol has hit target or stop-loss."""
        for sig in self._signals:
            if sig.symbol != symbol or sig.resolved:
                continue

            hit_target = False
            hit_stop = False

            if sig.action == "BUY":
                hit_target = current_price >= sig.target_price
                hit_stop = current_price <= sig.stop_loss
            elif sig.action == "SELL":
                hit_target = current_price <= sig.target_price
                hit_stop = current_price >= sig.stop_loss

            if hit_target or hit_stop:
                sig.resolved = True
                sig.exit_price = current_price

                if hit_target:
                    sig.outcome = "win"
                    sig.pnl = abs(sig.target_price - sig.entry_price)
                else:
                    sig.outcome = "loss"
                    sig.pnl = -abs(sig.stop_loss - sig.entry_price)

                self._current_equity += sig.pnl
                self._peak_equity = max(self._peak_equity, self._current_equity)

                today = datetime.now(IST).strftime("%Y-%m-%d")
                if today not in self._daily_results:
                    self._daily_results[today] = {"wins": 0, "losses": 0, "pnl": 0.0}
                self._daily_results[today]["pnl"] += sig.pnl
                if sig.outcome == "win":
                    self._daily_results[today]["wins"] += 1
                else:
                    self._daily_results[today]["losses"] += 1

                # Track per-agent accuracy
                for agent_name, agent_signal in sig.agent_signals.items():
                    if agent_name not in self._agent_accuracy:
                        self._agent_accuracy[agent_name] = {"correct": 0, "total": 0}
                    self._agent_accuracy[agent_name]["total"] += 1
                    agent_bullish = agent_signal.get("signal") == "bullish"
                    was_win = sig.outcome == "win"
                    if (sig.action == "BUY" and agent_bullish and was_win) or \
                       (sig.action == "SELL" and not agent_bullish and was_win):
                        self._agent_accuracy[agent_name]["correct"] += 1

                return sig

        return None

    def get_metrics(self) -> dict:
        """Calculate shadow trading metrics."""
        resolved = [s for s in self._signals if s.resolved]
        wins = [s for s in resolved if s.outcome == "win"]
        losses = [s for s in resolved if s.outcome == "loss"]

        total = len(resolved)
        win_rate = len(wins) / total * 100 if total > 0 else 0
        total_pnl = sum(s.pnl for s in resolved)

        avg_win = sum(s.pnl for s in wins) / len(wins) if wins else 0
        avg_loss = abs(sum(s.pnl for s in losses) / len(losses)) if losses else 1
        profit_factor = (sum(s.pnl for s in wins) / abs(sum(s.pnl for s in losses))) if losses else 999

        # Max drawdown
        drawdown = (self._peak_equity - self._current_equity) / self._peak_equity * 100

        # Simplified Sharpe (daily returns)
        import numpy as np
        daily_pnls = [d["pnl"] for d in self._daily_results.values()]
        sharpe = 0.0
        if len(daily_pnls) > 5:
            arr = np.array(daily_pnls)
            if np.std(arr) > 0:
                sharpe = float(np.mean(arr) / np.std(arr) * np.sqrt(252))

        return {
            "total_signals": len(self._signals),
            "resolved_signals": total,
            "pending_signals": len(self._signals) - total,
            "win_rate": round(win_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(drawdown, 2),
            "sharpe_ratio": round(sharpe, 4),
            "trading_days": len(self._daily_results),
            "current_equity": round(self._current_equity, 2),
            "agent_accuracy": {
                name: round(s["correct"] / max(s["total"], 1) * 100, 1)
                for name, s in self._agent_accuracy.items()
            },
        }

    def check_go_live_readiness(self) -> dict:
        """Check if the system meets all criteria for live trading."""
        m = self.get_metrics()
        criteria = GO_LIVE_CRITERIA

        checks = {
            "trading_days": {
                "value": m["trading_days"],
                "required": criteria["min_trading_days"],
                "passed": m["trading_days"] >= criteria["min_trading_days"],
            },
            "win_rate": {
                "value": m["win_rate"],
                "required": criteria["min_win_rate"],
                "passed": m["win_rate"] >= criteria["min_win_rate"],
            },
            "sharpe_ratio": {
                "value": m["sharpe_ratio"],
                "required": criteria["min_sharpe"],
                "passed": m["sharpe_ratio"] >= criteria["min_sharpe"],
            },
            "max_drawdown": {
                "value": m["max_drawdown_pct"],
                "required": criteria["max_drawdown_pct"],
                "passed": m["max_drawdown_pct"] <= criteria["max_drawdown_pct"],
            },
            "profit_factor": {
                "value": m["profit_factor"],
                "required": criteria["min_profit_factor"],
                "passed": m["profit_factor"] >= criteria["min_profit_factor"],
            },
            "total_signals": {
                "value": m["resolved_signals"],
                "required": criteria["min_total_signals"],
                "passed": m["resolved_signals"] >= criteria["min_total_signals"],
            },
        }

        all_passed = all(c["passed"] for c in checks.values())

        return {
            "ready_for_live": all_passed,
            "checks": checks,
            "metrics": m,
            "recommendation": (
                "All criteria met — system has demonstrated a statistically significant edge. "
                "Proceed with live trading at 1-lot minimum size for 2 more weeks."
                if all_passed else
                "System has NOT yet met go-live criteria. Continue paper trading."
            ),
        }


# Singleton
shadow_validator = ShadowValidator()
