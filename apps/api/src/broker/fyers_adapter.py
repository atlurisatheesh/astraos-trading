"""AstraOS Broker — Fyers v3 API Adapter.

Full integration with Fyers via their v3 Python SDK.
Supports: login, orders, positions, holdings, funds, market data.

Requirements:
    pip install fyers-apiv3
    API Key: https://myapi.fyers.in/ (Free)

Auth Flow:
    1. Generate auth_code via Fyers login redirect
    2. Exchange auth_code for access_token via login()
"""

from datetime import datetime, timezone

import structlog  # type: ignore

from . import BrokerAdapter, BrokerCredentials, OrderParams, OrderResult, Position, Holding  # type: ignore

logger = structlog.get_logger()


class FyersAdapter(BrokerAdapter):
    """Fyers v3 API broker adapter.

    Free API access. Supports NSE, BSE, MCX.
    """

    name = "fyers"

    PRODUCT_MAP = {
        "DELIVERY": "CNC",
        "CNC": "CNC",
        "INTRADAY": "INTRADAY",
        "MIS": "INTRADAY",
        "NRML": "MARGIN",
        "CARRYFORWARD": "MARGIN",
    }

    ORDER_TYPE_MAP = {
        "MARKET": 2,
        "LIMIT": 1,
        "SL": 3,
        "SL-M": 4,
    }

    SIDE_MAP = {
        "BUY": 1,
        "SELL": -1,
    }

    def __init__(self):
        self._fyers = None
        self._logged_in = False
        self._profile: dict = {}

    async def login(self, credentials: BrokerCredentials) -> dict:
        try:
            from fyers_apiv3 import fyersModel

            client_id = credentials.api_key  # e.g., "XXXX-100"
            secret_key = credentials.api_secret
            redirect_uri = credentials.extras.get("redirect_uri", "https://localhost")

            if credentials.access_token:
                # Reuse existing token
                self._fyers = fyersModel.FyersModel(
                    client_id=client_id,
                    token=credentials.access_token,
                    is_async=False,
                    log_path="",
                )
                self._logged_in = True
            elif credentials.request_token:
                # Exchange auth_code for token
                session = fyersModel.SessionModel(
                    client_id=client_id,
                    secret_key=secret_key,
                    redirect_uri=redirect_uri,
                    response_type="code",
                    grant_type="authorization_code",
                )
                session.set_token(credentials.request_token)
                response = session.generate_token()

                if "access_token" not in response:
                    return {"status": "error", "broker": "fyers",
                            "message": response.get("message", "Token generation failed")}

                self._fyers = fyersModel.FyersModel(
                    client_id=client_id,
                    token=response["access_token"],
                    is_async=False,
                    log_path="",
                )
                self._logged_in = True
            else:
                session = fyersModel.SessionModel(
                    client_id=client_id,
                    secret_key=secret_key,
                    redirect_uri=redirect_uri,
                    response_type="code",
                    grant_type="authorization_code",
                )
                return {
                    "status": "pending",
                    "broker": "fyers",
                    "message": "Visit login URL, login, and provide auth_code",
                    "login_url": session.generate_authcode(),
                }

            # Get profile
            profile = self._fyers.get_profile()
            self._profile = profile.get("data", {})
            logger.info("Fyers login successful", user=self._profile.get("name", ""))

            return {
                "status": "success",
                "broker": "fyers",
                "user_id": self._profile.get("fy_id"),
                "user_name": self._profile.get("name"),
                "email": self._profile.get("email_id"),
            }

        except ImportError:
            return {"status": "error", "broker": "fyers",
                    "message": "fyers-apiv3 not installed. Run: pip install fyers-apiv3"}
        except Exception as e:
            logger.error("Fyers login failed", error=str(e))
            return {"status": "error", "broker": "fyers", "message": str(e)}

    async def place_order(self, params: OrderParams) -> OrderResult:
        if not self._fyers:
            return OrderResult(success=False, broker="fyers", message="Not logged in")

        try:
            order_data = {
                "symbol": f"{params.exchange}:{params.symbol}",
                "qty": params.quantity,
                "type": self.ORDER_TYPE_MAP.get(params.order_type, 2),
                "side": self.SIDE_MAP.get(params.side, 1),
                "productType": self.PRODUCT_MAP.get(params.product, "CNC"),
                "limitPrice": params.price if params.price > 0 else 0,
                "stopPrice": params.trigger_price if params.trigger_price > 0 else 0,
                "validity": params.validity,
                "disclosedQty": 0,
                "offlineOrder": params.variety == "AMO",
            }

            result = self._fyers.place_order(data=order_data)
            order_id = result.get("id", "")

            if result.get("s") == "ok":
                logger.info("Fyers order placed", order_id=order_id, symbol=params.symbol)
                return OrderResult(
                    success=True, order_id=order_id, broker="fyers",
                    status="PLACED", message=f"Order placed: {params.side} {params.quantity} {params.symbol}",
                )
            else:
                return OrderResult(success=False, broker="fyers",
                                 message=result.get("message", "Order failed"))

        except Exception as e:
            return OrderResult(success=False, broker="fyers", message=str(e))

    async def modify_order(self, order_id: str, params: OrderParams) -> OrderResult:
        if not self._fyers:
            return OrderResult(success=False, broker="fyers", message="Not logged in")
        try:
            data = {"id": order_id}
            if params.quantity > 0:
                data["qty"] = params.quantity
            if params.price > 0:
                data["limitPrice"] = params.price
            if params.trigger_price > 0:
                data["stopPrice"] = params.trigger_price
            if params.order_type:
                data["type"] = self.ORDER_TYPE_MAP.get(params.order_type, 2)

            result = self._fyers.modify_order(data=data)
            return OrderResult(success=result.get("s") == "ok", order_id=order_id,
                             broker="fyers", status="MODIFIED", message=result.get("message", ""))
        except Exception as e:
            return OrderResult(success=False, broker="fyers", message=str(e))

    async def cancel_order(self, order_id: str) -> OrderResult:
        if not self._fyers:
            return OrderResult(success=False, broker="fyers", message="Not logged in")
        try:
            result = self._fyers.cancel_order(data={"id": order_id})
            return OrderResult(success=result.get("s") == "ok", order_id=order_id,
                             broker="fyers", status="CANCELLED")
        except Exception as e:
            return OrderResult(success=False, broker="fyers", message=str(e))

    async def get_order_book(self) -> list[dict]:
        if not self._fyers:
            return []
        try:
            result = self._fyers.orderbook()
            return result.get("orderBook", []) or []
        except Exception:
            return []

    async def get_positions(self) -> list[Position]:
        if not self._fyers:
            return []
        try:
            result = self._fyers.positions()
            positions = []
            for item in (result.get("netPositions", []) or []):
                positions.append(Position(
                    symbol=item.get("symbol", "").split(":")[-1],
                    exchange=item.get("symbol", "").split(":")[0] if ":" in item.get("symbol", "") else "",
                    side="BUY" if item.get("netQty", 0) > 0 else "SELL",
                    quantity=abs(item.get("netQty", 0)),
                    avg_price=float(item.get("avgPrice", 0)),
                    ltp=float(item.get("ltp", 0)),
                    pnl=float(item.get("pl", 0)),
                    product=item.get("productType", ""),
                    broker="fyers",
                ))
            return positions
        except Exception:
            return []

    async def get_holdings(self) -> list[Holding]:
        if not self._fyers:
            return []
        try:
            result = self._fyers.holdings()
            holdings = []
            for item in (result.get("holdings", []) or []):
                avg = float(item.get("costPrice", 0))
                ltp = float(item.get("ltp", 0))
                qty = int(item.get("quantity", 0))
                holdings.append(Holding(
                    symbol=item.get("symbol", "").split(":")[-1],
                    exchange=item.get("exchange", ""),
                    quantity=qty, avg_price=avg, ltp=ltp,
                    pnl=round((ltp - avg) * qty, 2),
                    pnl_pct=round((ltp - avg) / avg * 100, 2) if avg else 0,
                    broker="fyers",
                ))
            return holdings
        except Exception:
            return []

    async def get_funds(self) -> dict:
        if not self._fyers:
            return {}
        try:
            result = self._fyers.funds()
            fund_data = result.get("fund_limit", []) or []
            funds = {item["title"]: item["equityAmount"] for item in fund_data}
            return {
                "available": float(funds.get("Available Balance", 0)),
                "used": float(funds.get("Used Margin", 0)),
                "total": float(funds.get("Total Balance", 0)),
                "broker": "fyers",
            }
        except Exception:
            return {}

    async def get_ltp(self, exchange: str, symbol: str) -> float:
        if not self._fyers:
            return 0.0
        try:
            key = f"{exchange}:{symbol}"
            result = self._fyers.quotes(data={"symbols": key})
            return float(result.get("d", [{}])[0].get("v", {}).get("lp", 0))
        except Exception:
            return 0.0

    async def get_quote(self, exchange: str, symbol: str) -> dict:
        if not self._fyers:
            return {}
        try:
            key = f"{exchange}:{symbol}"
            result = self._fyers.quotes(data={"symbols": key})
            return result.get("d", [{}])[0].get("v", {})
        except Exception:
            return {}

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
