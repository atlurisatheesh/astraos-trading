"""AstraOS Broker — Paper Trading Adapter (zero cost, simulated fills)."""

import uuid
from decimal import Decimal
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()


class PaperBrokerAdapter:
    """Simulated broker for development and testing. Zero cost, no real money.

    Simulates immediate fills at the requested price (or a small random slippage).
    Implements the same interface as the real broker adapter.
    """

    def __init__(self):
        self.name = "paper"

    async def place_order(self, order) -> dict:
        """Simulate placing an order — instant fill at requested price."""
        order_id = f"PAPER-{uuid.uuid4().hex[:12].upper()}"
        fill_price = order.price or Decimal("100.00")  # default mock price

        logger.info(
            "Paper order placed",
            order_id=order_id,
            side=order.side,
            quantity=order.quantity,
            price=str(fill_price),
        )

        return {
            "order_id": order_id,
            "status": "FILLED",
            "filled": True,
            "fill_price": fill_price,
            "fill_quantity": order.quantity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def cancel_order(self, broker_order_id: str) -> dict:
        """Simulate cancelling an order."""
        logger.info("Paper order cancelled", order_id=broker_order_id)
        return {"status": "CANCELLED", "order_id": broker_order_id}

    async def get_positions(self) -> list[dict]:
        """Return empty positions (paper account)."""
        return []

    async def get_order_status(self, broker_order_id: str) -> dict:
        """Simulate order status check."""
        return {"status": "FILLED", "order_id": broker_order_id}
