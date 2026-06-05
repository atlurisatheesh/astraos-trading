"""AstraOS Broker — Paper Trading (Unified Interface).

Simulated broker for development and testing.
Implements the unified BrokerAdapter interface.
"""

import uuid
from datetime import datetime, timezone

import structlog  # type: ignore

from . import BrokerAdapter, BrokerCredentials, OrderParams, OrderResult, Position, Holding  # type: ignore

logger = structlog.get_logger()


class PaperBrokerUnified(BrokerAdapter):
    """Zero-risk simulated broker — instant fills, no real money."""

    name = "paper"

    def __init__(self):
        self._logged_in = True  # Always logged in
        self._orders: list[dict] = []
        self._positions: list[Position] = []
        self._holdings: list[Holding] = []
        self._balance = 1_000_000.0  # ₹10 lakh starting capital

    async def login(self, credentials: BrokerCredentials) -> dict:
        self._logged_in = True
        return {
            "status": "success",
            "broker": "paper",
            "message": "Paper trading mode — no real money at risk",
            "balance": self._balance,
        }

    async def place_order(self, params: OrderParams) -> OrderResult:
        order_id = f"PAPER-{uuid.uuid4().hex[:12].upper()}"
        fill_price = params.price if params.price > 0 else 100.0

        order = {
            "order_id": order_id,
            "symbol": params.symbol,
            "exchange": params.exchange,
            "side": params.side,
            "quantity": params.quantity,
            "price": fill_price,
            "status": "FILLED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._orders.append(order)

        # Update positions
        self._positions.append(Position(
            symbol=params.symbol, exchange=params.exchange,
            side=params.side, quantity=params.quantity,
            avg_price=fill_price, ltp=fill_price, pnl=0,
            product=params.product, broker="paper",
        ))

        logger.info("Paper order filled", order_id=order_id, symbol=params.symbol,
                     side=params.side, qty=params.quantity, price=fill_price)

        return OrderResult(
            success=True, order_id=order_id, broker="paper",
            status="FILLED", message=f"Paper {params.side} {params.quantity} {params.symbol} @ ₹{fill_price}",
        )

    async def modify_order(self, order_id: str, params: OrderParams) -> OrderResult:
        return OrderResult(success=True, order_id=order_id, broker="paper",
                          status="MODIFIED", message="Paper order modified")

    async def cancel_order(self, order_id: str) -> OrderResult:
        return OrderResult(success=True, order_id=order_id, broker="paper",
                          status="CANCELLED", message="Paper order cancelled")

    async def get_order_book(self) -> list[dict]:
        return self._orders

    async def get_positions(self) -> list[Position]:
        return self._positions

    async def get_holdings(self) -> list[Holding]:
        return self._holdings

    async def get_funds(self) -> dict:
        return {
            "available": self._balance,
            "used": sum(p.quantity * p.avg_price for p in self._positions),
            "total": self._balance,
            "broker": "paper",
        }

    async def get_ltp(self, exchange: str, symbol: str) -> float:
        return 0.0  # Paper doesn't track real prices

    async def get_quote(self, exchange: str, symbol: str) -> dict:
        return {"symbol": symbol, "exchange": exchange, "broker": "paper"}

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
