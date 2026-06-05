"""AstraOS Services — Order State Machine (deterministic, no LLM)."""

from datetime import datetime, timezone
from enum import Enum

import structlog

logger = structlog.get_logger()


class OrderState(str, Enum):
    """Order lifecycle states (deterministic FSM)."""
    DRAFT = "DRAFT"
    RISK_PENDING = "RISK_PENDING"
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"
    HUMAN_PENDING = "HUMAN_PENDING"       # Semi-auto: awaiting user approval
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    SENT = "SENT"                          # Sent to broker
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


# Valid state transitions
TRANSITIONS = {
    OrderState.DRAFT: {OrderState.RISK_PENDING},
    OrderState.RISK_PENDING: {OrderState.RISK_APPROVED, OrderState.RISK_REJECTED},
    OrderState.RISK_APPROVED: {OrderState.HUMAN_PENDING, OrderState.SENT},  # SENT for auto-mode
    OrderState.RISK_REJECTED: set(),  # Terminal
    OrderState.HUMAN_PENDING: {OrderState.HUMAN_APPROVED, OrderState.HUMAN_REJECTED, OrderState.CANCELLED},
    OrderState.HUMAN_APPROVED: {OrderState.SENT},
    OrderState.HUMAN_REJECTED: set(),  # Terminal
    OrderState.SENT: {OrderState.PARTIALLY_FILLED, OrderState.FILLED, OrderState.CANCELLED, OrderState.FAILED},
    OrderState.PARTIALLY_FILLED: {OrderState.FILLED, OrderState.CANCELLED},
    OrderState.FILLED: set(),  # Terminal
    OrderState.CANCELLED: set(),  # Terminal
    OrderState.FAILED: set(),  # Terminal
}


class OrderStateMachine:
    """Manages order state transitions with audit trail."""

    def __init__(self, order_id: str, current_state: str = "DRAFT"):
        self.order_id = order_id
        self.state = OrderState(current_state)
        self.history: list[dict] = []

    def can_transition(self, target: OrderState) -> bool:
        """Check if transition is valid."""
        return target in TRANSITIONS.get(self.state, set())

    def transition(self, target: OrderState, reason: str = "") -> dict:
        """Execute state transition with audit record."""
        if not self.can_transition(target):
            raise ValueError(
                f"Invalid transition: {self.state.value} → {target.value}. "
                f"Allowed: {[s.value for s in TRANSITIONS.get(self.state, set())]}"
            )

        old_state = self.state
        self.state = target

        event = {
            "order_id": self.order_id,
            "from": old_state.value,
            "to": target.value,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append(event)

        logger.info("Order state transition", **event)
        return event

    def submit(self) -> dict:
        """DRAFT → RISK_PENDING."""
        return self.transition(OrderState.RISK_PENDING, "Submitted for risk check")

    def risk_approve(self) -> dict:
        """RISK_PENDING → RISK_APPROVED."""
        return self.transition(OrderState.RISK_APPROVED, "All 12 risk checks passed")

    def risk_reject(self, reason: str) -> dict:
        """RISK_PENDING → RISK_REJECTED."""
        return self.transition(OrderState.RISK_REJECTED, reason)

    def request_human_approval(self) -> dict:
        """RISK_APPROVED → HUMAN_PENDING (semi-auto mode)."""
        return self.transition(OrderState.HUMAN_PENDING, "Awaiting user approval")

    def human_approve(self) -> dict:
        """HUMAN_PENDING → HUMAN_APPROVED."""
        return self.transition(OrderState.HUMAN_APPROVED, "User approved")

    def human_reject(self) -> dict:
        """HUMAN_PENDING → HUMAN_REJECTED."""
        return self.transition(OrderState.HUMAN_REJECTED, "User rejected")

    def send_to_broker(self) -> dict:
        """RISK_APPROVED/HUMAN_APPROVED → SENT."""
        return self.transition(OrderState.SENT, "Sent to broker")

    def fill(self) -> dict:
        """SENT/PARTIALLY_FILLED → FILLED."""
        return self.transition(OrderState.FILLED, "Order filled")

    def cancel(self, reason: str = "User cancelled") -> dict:
        """Cancel order from any cancellable state."""
        return self.transition(OrderState.CANCELLED, reason)

    @property
    def is_terminal(self) -> bool:
        return self.state in {
            OrderState.RISK_REJECTED, OrderState.HUMAN_REJECTED,
            OrderState.FILLED, OrderState.CANCELLED, OrderState.FAILED,
        }
