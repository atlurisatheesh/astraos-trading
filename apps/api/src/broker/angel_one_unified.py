"""AstraOS Broker — Angel One Unified Adapter.

Wraps the existing AngelOneAdapter to implement the unified BrokerAdapter interface.
"""

import structlog  # type: ignore

from . import BrokerAdapter, BrokerCredentials, OrderParams, OrderResult, Position, Holding  # type: ignore
from .angel_one_adapter import AngelOneAdapter, AngelOneConfig  # type: ignore

logger = structlog.get_logger()


class AngelOneUnified(BrokerAdapter):
    """Angel One adapter implementing the unified interface."""

    name = "angel"

    def __init__(self):
        self._adapter: AngelOneAdapter | None = None
        self._logged_in = False

    async def login(self, credentials: BrokerCredentials) -> dict:
        config = AngelOneConfig(
            api_key=credentials.api_key,
            client_id=credentials.client_id,
            password=credentials.password,
            totp_secret=credentials.totp_secret,
        )
        self._adapter = AngelOneAdapter(config)
        result = await self._adapter.login()
        self._logged_in = result.get("status") == "success"
        result["broker"] = "angel"
        return result

    async def place_order(self, params: OrderParams) -> OrderResult:
        if not self._adapter or not self._adapter.is_logged_in:
            return OrderResult(success=False, broker="angel", message="Not logged in")

        result = await self._adapter.place_order(
            symbol=params.symbol,
            token=params.symbol_token or "",
            exchange=params.exchange,
            side=params.side,
            order_type=params.order_type,
            product=params.product,
            quantity=params.quantity,
            price=params.price,
            trigger_price=params.trigger_price,
            variety=params.variety,
        )

        if result.get("status") == "success":
            return OrderResult(success=True, order_id=result.get("order_id", ""),
                             broker="angel", status="PLACED",
                             message=f"{params.side} {params.quantity} {params.symbol}")
        else:
            return OrderResult(success=False, broker="angel", message=result.get("error", "Failed"))

    async def modify_order(self, order_id: str, params: OrderParams) -> OrderResult:
        if not self._adapter:
            return OrderResult(success=False, broker="angel", message="Not logged in")
        result = await self._adapter.modify_order(order_id, quantity=params.quantity, price=params.price)
        return OrderResult(success="error" not in result, order_id=order_id, broker="angel", status="MODIFIED")

    async def cancel_order(self, order_id: str) -> OrderResult:
        if not self._adapter:
            return OrderResult(success=False, broker="angel", message="Not logged in")
        result = await self._adapter.cancel_order(order_id)
        return OrderResult(success=result.get("status") == "cancelled",
                          order_id=order_id, broker="angel", status="CANCELLED")

    async def get_order_book(self) -> list[dict]:
        if not self._adapter:
            return []
        return await self._adapter.get_order_book()

    async def get_positions(self) -> list[Position]:
        if not self._adapter:
            return []
        data = await self._adapter.get_positions()
        return [Position(
            symbol=p.get("tradingsymbol", ""), exchange=p.get("exchange", ""),
            side="BUY" if p.get("netqty", 0) > 0 else "SELL",
            quantity=abs(p.get("netqty", 0)),
            avg_price=float(p.get("avgnetprice", 0)),
            ltp=float(p.get("ltp", 0)),
            pnl=float(p.get("pnl", 0)), broker="angel",
        ) for p in data]

    async def get_holdings(self) -> list[Holding]:
        if not self._adapter:
            return []
        data = await self._adapter.get_holdings()
        return [Holding(
            symbol=h.get("tradingsymbol", ""), exchange=h.get("exchange", ""),
            quantity=int(h.get("quantity", 0)),
            avg_price=float(h.get("averageprice", 0)),
            ltp=float(h.get("ltp", 0)),
            pnl=float(h.get("profitandloss", 0)),
            pnl_pct=float(h.get("pnlpercentage", 0)),
            broker="angel",
        ) for h in data]

    async def get_funds(self) -> dict:
        if not self._adapter:
            return {}
        data = await self._adapter.get_funds()
        return {
            "available": float(data.get("availablecash", 0)),
            "used": float(data.get("utiliseddebits", 0)),
            "total": float(data.get("net", 0)),
            "broker": "angel",
        }

    async def get_ltp(self, exchange: str, symbol: str) -> float:
        if not self._adapter:
            return 0.0
        data = await self._adapter.get_ltp(exchange, symbol)
        return float(data.get("ltp", 0)) if isinstance(data, dict) else 0.0

    async def get_quote(self, exchange: str, symbol: str) -> dict:
        if not self._adapter:
            return {}
        return await self._adapter.get_quote(exchange, symbol)

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
