"""AstraOS Agents — Trade Outcome Tracker.

Tracks the accuracy of each agent's signals after trades resolve.
Feeds accuracy data back into the orchestrator for Bayesian weight
rebalancing — agents that are right more often get more influence.

Also feeds into the shadow validator for go-live readiness assessment.
"""

import time
from collections import deque
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()


@dataclass
class PendingSignal:
    symbol: str
    action: str            # BUY or SELL
    entry_price: float
    target_price: float
    stop_loss: float
    agent_signals: dict    # agent_name -> {"signal": "bullish/bearish", "confidence": 70}
    created_at: float = field(default_factory=time.time)
    resolved: bool = False
    outcome: str = ""      # "win" or "loss"
    exit_price: float = 0.0


class OutcomeTracker:
    """Track signal outcomes and feed accuracy back to orchestrator."""

    def __init__(self, max_pending: int = 500):
        self._pending: deque[PendingSignal] = deque(maxlen=max_pending)
        self._resolved: deque[PendingSignal] = deque(maxlen=2000)

    def record_signal(
        self,
        symbol: str,
        action: str,
        entry_price: float,
        target_price: float,
        stop_loss: float,
        agent_signals: dict,
    ) -> None:
        """Record a new signal with per-agent predictions."""
        self._pending.append(PendingSignal(
            symbol=symbol,
            action=action,
            entry_price=entry_price,
            target_price=target_price,
            stop_loss=stop_loss,
            agent_signals=agent_signals,
        ))
        logger.info("Signal recorded for tracking", symbol=symbol, action=action)

    def check_outcomes(self, current_prices: dict[str, float]) -> list[PendingSignal]:
        """Check all pending signals against current prices.

        Args:
            current_prices: {symbol: current_price}

        Returns:
            List of newly resolved signals.
        """
        newly_resolved = []

        for sig in self._pending:
            if sig.resolved:
                continue

            price = current_prices.get(sig.symbol)
            if price is None:
                continue

            hit_target = False
            hit_stop = False

            if sig.action == "BUY":
                hit_target = price >= sig.target_price
                hit_stop = price <= sig.stop_loss
            elif sig.action == "SELL":
                hit_target = price <= sig.target_price
                hit_stop = price >= sig.stop_loss

            # Timeout: if signal is older than 10 trading days (~14 calendar days)
            age_days = (time.time() - sig.created_at) / 86400
            timed_out = age_days > 14

            if hit_target or hit_stop or timed_out:
                sig.resolved = True
                sig.exit_price = price

                if hit_target:
                    sig.outcome = "win"
                elif hit_stop:
                    sig.outcome = "loss"
                else:
                    # Timed out — check if it moved in the right direction
                    if sig.action == "BUY":
                        sig.outcome = "win" if price > sig.entry_price else "loss"
                    else:
                        sig.outcome = "win" if price < sig.entry_price else "loss"

                self._resolved.append(sig)
                newly_resolved.append(sig)

                # Update agent accuracy in orchestrator
                self._update_agent_accuracy(sig)

                logger.info(
                    "Signal resolved",
                    symbol=sig.symbol,
                    action=sig.action,
                    outcome=sig.outcome,
                    entry=sig.entry_price,
                    exit=sig.exit_price,
                )

        return newly_resolved

    def _update_agent_accuracy(self, sig: PendingSignal) -> None:
        """Feed outcome back to orchestrator's Bayesian weight system."""
        try:
            from .orchestrator import update_agent_accuracy

            for agent_name, agent_data in sig.agent_signals.items():
                agent_signal = agent_data.get("signal", "neutral")

                # Determine if this agent was correct
                if sig.action == "BUY":
                    agent_correct = (agent_signal == "bullish" and sig.outcome == "win") or \
                                    (agent_signal == "bearish" and sig.outcome == "loss")
                elif sig.action == "SELL":
                    agent_correct = (agent_signal == "bearish" and sig.outcome == "win") or \
                                    (agent_signal == "bullish" and sig.outcome == "loss")
                else:
                    continue

                update_agent_accuracy(agent_name, agent_correct)

        except Exception as e:
            logger.error("Failed to update agent accuracy", error=str(e))

    def get_stats(self) -> dict:
        """Get tracking statistics."""
        resolved = list(self._resolved)
        wins = [s for s in resolved if s.outcome == "win"]
        losses = [s for s in resolved if s.outcome == "loss"]

        return {
            "pending": len([s for s in self._pending if not s.resolved]),
            "total_resolved": len(resolved),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / max(len(resolved), 1) * 100, 1),
        }


# Singleton
outcome_tracker = OutcomeTracker()
