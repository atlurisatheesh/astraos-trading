"""AstraOS Broker — 5Paisa API Adapter.

Full integration with 5Paisa via their Python SDK.
Supports: login (TOTP/OAuth), orders, positions, holdings, funds, market data.

Requirements:
    pip install py5paisa
    API Key: https://www.5paisa.com/developerapi (Free)
"""

from datetime import datetime, timezone

import structlog  # type: ignore

from . import BrokerAdapter, BrokerCredentials, OrderParams, OrderResult, Position, Holding  # type: ignore

logger = structlog.get_logger()


class FivePaisaAdapter(BrokerAdapter):
    """5Paisa broker adapter.

    Free API access. Supports NSE, BSE, MCX.
    """

    name = "5paisa"

    EXCHANGE_MAP = {
        "NSE": "N",
        "BSE": "B",
        "MCX": "M",
        "NFO": "N",
    }

    EXCHANGE_TYPE_MAP = {
        "NSE": "C",  # Cash
        "BSE": "C",
        "NFO": "D",  # Derivatives
        "MCX": "D",
    }

    ORDER_TYPE_MAP = {
        "BUY": "B",
        "SELL": "S",
    }

    def __init__(self):
        self._client = None
        self._logged_in = False
        self._profile: dict = {}

    async def login(self, credentials: BrokerCredentials) -> dict:
        try:
            from py5paisa import FivePaisaClient

            cred = {
                "APP_NAME": credentials.extras.get("app_name", ""),
                "APP_SOURCE": credentials.extras.get("app_source", ""),
                "USER_ID": credentials.client_id,
                "PASSWORD": credentials.password,
                "USER_KEY": credentials.api_key,
                "ENCRYPTION_KEY": credentials.api_secret,
            }

            self._client = FivePaisaClient(cred=cred)

            if credentials.totp_secret:
                # TOTP login
                self._client.get_totp_session(
                    credentials.client_id,
                    credentials.totp_secret,
                    credentials.extras.get("pin", ""),
                )
            elif credentials.access_token:
                # OAuth token
                self._client.get_oauth_session(
                    credentials.request_token or credentials.access_token
                )
            else:
                # Email/password login
                self._client.login(
                    credentials.extras.get("email", ""),
                    credentials.password,
                    credentials.extras.get("dob", ""),
                )

            self._logged_in = self._client.client_code is not None and self._client.client_code != ""

            if self._logged_in:
                logger.info("5Paisa login successful", client=self._client.client_code)
                return {
                    "status": "success",
                    "broker": "5paisa",
                    "client_code": self._client.client_code,
                }
            else:
                return {"status": "error", "broker": "5paisa", "message": "Login failed"}

        except ImportError:
            return {"status": "error", "broker": "5paisa",
                    "message": "py5paisa not installed. Run: pip install py5paisa"}
        except Exception as e:
            logger.error("5Paisa login failed", error=str(e))
            return {"status": "error", "broker": "5paisa", "message": str(e)}

    async def place_order(self, params: OrderParams) -> OrderResult:
        if not self._client:
            return OrderResult(success=False, broker="5paisa", message="Not logged in")

        try:
            exchange = self.EXCHANGE_MAP.get(params.exchange, "N")
            exch_type = self.EXCHANGE_TYPE_MAP.get(params.exchange, "C")

            order_list = [{
                "Exchange": exchange,
                "ExchangeType": exch_type,
                "ScripCode": int(params.symbol_token) if params.symbol_token else 0,
                "Qty": params.quantity,
                "Price": params.price if params.price > 0 else 0,
                "StopLossPrice": params.trigger_price if params.trigger_price > 0 else 0,
                "IsIntraday": params.product in ("INTRADAY", "MIS"),
                "IsStopLossOrder": params.order_type in ("SL", "SL-M"),
                "RemoteOrderID": params.tag or "quantus",
            }]

            if params.side == "BUY":
                result = self._client.place_order(
                    OrderType=self.ORDER_TYPE_MAP.get(params.side, "B"),
                    Exchange=exchange,
                    ExchangeType=exch_type,
                    ScripCode=int(params.symbol_token) if params.symbol_token else 0,
                    Qty=params.quantity,
                    Price=params.price,
                    IsIntraday=params.product in ("INTRADAY", "MIS"),
                )
            else:
                result = self._client.place_order(
                    OrderType="S",
                    Exchange=exchange,
                    ExchangeType=exch_type,
                    ScripCode=int(params.symbol_token) if params.symbol_token else 0,
                    Qty=params.quantity,
                    Price=params.price,
                    IsIntraday=params.product in ("INTRADAY", "MIS"),
                )

            order_id = str(result.get("BrokerOrderID", "")) if isinstance(result, dict) else str(result)

            logger.info("5Paisa order placed", order_id=order_id, symbol=params.symbol)

            return OrderResult(
                success=True, order_id=order_id, broker="5paisa",
                status="PLACED", message=f"Order: {params.side} {params.quantity} {params.symbol}",
            )

        except Exception as e:
            logger.error("5Paisa order failed", error=str(e))
            return OrderResult(success=False, broker="5paisa", message=str(e))

    async def modify_order(self, order_id: str, params: OrderParams) -> OrderResult:
        if not self._client:
            return OrderResult(success=False, broker="5paisa", message="Not logged in")
        try:
            self._client.modify_order(
                ExchOrderID=order_id,
                Qty=params.quantity,
                Price=params.price,
            )
            return OrderResult(success=True, order_id=order_id, broker="5paisa", status="MODIFIED")
        except Exception as e:
            return OrderResult(success=False, broker="5paisa", message=str(e))

    async def cancel_order(self, order_id: str) -> OrderResult:
        if not self._client:
            return OrderResult(success=False, broker="5paisa", message="Not logged in")
        try:
            self._client.cancel_order(ExchOrderID=order_id)
            return OrderResult(success=True, order_id=order_id, broker="5paisa", status="CANCELLED")
        except Exception as e:
            return OrderResult(success=False, broker="5paisa", message=str(e))

    async def get_order_book(self) -> list[dict]:
        if not self._client:
            return []
        try:
            return self._client.order_book() or []
        except Exception:
            return []

    async def get_positions(self) -> list[Position]:
        if not self._client:
            return []
        try:
            data = self._client.positions() or []
            positions = []
            for item in data:
                positions.append(Position(
                    symbol=item.get("ScripName", ""),
                    exchange=item.get("Exchange", ""),
                    side="BUY" if item.get("NetQty", 0) > 0 else "SELL",
                    quantity=abs(item.get("NetQty", 0)),
                    avg_price=float(item.get("BuyAvgRate", 0)),
                    ltp=float(item.get("LTP", 0)),
                    pnl=float(item.get("MTOM", 0)),
                    broker="5paisa",
                ))
            return positions
        except Exception:
            return []

    async def get_holdings(self) -> list[Holding]:
        if not self._client:
            return []
        try:
            data = self._client.holdings() or []
            holdings = []
            for item in data:
                avg = float(item.get("AvgRate", 0))
                ltp = float(item.get("CurrentPrice", 0))
                qty = int(item.get("Quantity", 0))
                holdings.append(Holding(
                    symbol=item.get("ScripName", ""),
                    exchange="NSE",
                    quantity=qty, avg_price=avg, ltp=ltp,
                    pnl=round((ltp - avg) * qty, 2),
                    pnl_pct=round((ltp - avg) / avg * 100, 2) if avg else 0,
                    broker="5paisa",
                ))
            return holdings
        except Exception:
            return []

    async def get_funds(self) -> dict:
        if not self._client:
            return {}
        try:
            data = self._client.margin() or []
            if data:
                row = data[0] if isinstance(data, list) else data
                return {
                    "available": float(row.get("NetAvailableMargin", 0)),
                    "used": float(row.get("NetUsedMargin", 0)),
                    "broker": "5paisa",
                }
            return {}
        except Exception:
            return {}

    async def get_ltp(self, exchange: str, symbol: str) -> float:
        if not self._client:
            return 0.0
        try:
            exch = self.EXCHANGE_MAP.get(exchange, "N")
            exch_type = self.EXCHANGE_TYPE_MAP.get(exchange, "C")
            data = self._client.fetch_market_depth_by_symbol(
                Exchange=exch, ExchangeType=exch_type, Symbol=symbol,
            )
            return float(data.get("LastTradedPrice", 0))
        except Exception:
            return 0.0

    async def get_quote(self, exchange: str, symbol: str) -> dict:
        if not self._client:
            return {}
        try:
            exch = self.EXCHANGE_MAP.get(exchange, "N")
            exch_type = self.EXCHANGE_TYPE_MAP.get(exchange, "C")
            return self._client.fetch_market_depth_by_symbol(
                Exchange=exch, ExchangeType=exch_type, Symbol=symbol,
            ) or {}
        except Exception:
            return {}

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
