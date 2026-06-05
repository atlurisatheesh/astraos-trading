"""AstraOS Broker — Upstox v2 API Adapter.

Full integration with Upstox via their v2 REST API.
Supports: OAuth login, orders, positions, holdings, funds, market data.

Requirements:
    pip install upstox-python-sdk
    API Key: https://api.upstox.com/ (Free)

Auth Flow:
    1. User visits: https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id=YOUR_KEY&redirect_uri=YOUR_URI
    2. After login, redirects with ?code=xxx
    3. Exchange code for access_token via login()
"""

from datetime import datetime, timezone

import structlog  # type: ignore

from . import BrokerAdapter, BrokerCredentials, OrderParams, OrderResult, Position, Holding  # type: ignore

logger = structlog.get_logger()


class UpstoxAdapter(BrokerAdapter):
    """Upstox v2 API broker adapter.

    Free API access. Supports NSE, BSE, NFO, MCX.
    """

    name = "upstox"

    PRODUCT_MAP = {
        "DELIVERY": "D",
        "CNC": "D",
        "INTRADAY": "I",
        "MIS": "I",
        "NRML": "D",
        "CARRYFORWARD": "D",
    }

    ORDER_TYPE_MAP = {
        "MARKET": "MARKET",
        "LIMIT": "LIMIT",
        "SL": "SL",
        "SL-M": "SL-M",
    }

    EXCHANGE_MAP = {
        "NSE": "NSE_EQ",
        "BSE": "BSE_EQ",
        "NFO": "NSE_FO",
        "MCX": "MCX_FO",
    }

    def __init__(self):
        self._api = None
        self._config = None
        self._access_token: str = ""
        self._logged_in = False
        self._profile: dict = {}

    async def login(self, credentials: BrokerCredentials) -> dict:
        try:
            import upstox_client
            from upstox_client.rest import ApiException

            self._config = upstox_client.Configuration()

            if credentials.access_token:
                # Reuse existing token
                self._access_token = credentials.access_token
                self._config.access_token = credentials.access_token
            elif credentials.request_token:
                # Exchange auth code for token
                import httpx
                token_url = "https://api.upstox.com/v2/login/authorization/token"
                resp = httpx.post(token_url, data={
                    "code": credentials.request_token,
                    "client_id": credentials.api_key,
                    "client_secret": credentials.api_secret,
                    "redirect_uri": credentials.extras.get("redirect_uri", "https://localhost"),
                    "grant_type": "authorization_code",
                })
                data = resp.json()
                if "access_token" not in data:
                    return {"status": "error", "broker": "upstox", "message": data.get("message", "Token exchange failed")}
                self._access_token = data["access_token"]
                self._config.access_token = self._access_token
            else:
                login_url = (
                    f"https://api.upstox.com/v2/login/authorization/dialog"
                    f"?response_type=code&client_id={credentials.api_key}"
                    f"&redirect_uri={credentials.extras.get('redirect_uri', 'https://localhost')}"
                )
                return {
                    "status": "pending",
                    "broker": "upstox",
                    "message": "Visit login URL and provide the auth code",
                    "login_url": login_url,
                }

            # Get profile
            api_instance = upstox_client.UserApi(upstox_client.ApiClient(self._config))
            profile = api_instance.get_profile("2.0")
            self._profile = profile.data.__dict__ if profile.data else {}
            self._logged_in = True

            logger.info("Upstox login successful",
                       user=self._profile.get("user_name", ""),
                       client=self._profile.get("user_id", ""))

            return {
                "status": "success",
                "broker": "upstox",
                "user_id": self._profile.get("user_id"),
                "user_name": self._profile.get("user_name"),
                "email": self._profile.get("email"),
            }

        except ImportError:
            return {"status": "error", "broker": "upstox",
                    "message": "upstox-python-sdk not installed. Run: pip install upstox-python-sdk"}
        except Exception as e:
            logger.error("Upstox login failed", error=str(e))
            return {"status": "error", "broker": "upstox", "message": str(e)}

    async def place_order(self, params: OrderParams) -> OrderResult:
        if not self._logged_in:
            return OrderResult(success=False, broker="upstox", message="Not logged in")

        try:
            import upstox_client

            api = upstox_client.OrderApi(upstox_client.ApiClient(self._config))
            exchange = self.EXCHANGE_MAP.get(params.exchange, "NSE_EQ")

            body = upstox_client.PlaceOrderRequest(
                quantity=params.quantity,
                product=self.PRODUCT_MAP.get(params.product, "D"),
                validity=params.validity,
                price=params.price if params.price > 0 else 0,
                tag=params.tag or "quantus",
                instrument_token=f"{exchange}|{params.symbol_token or params.symbol}",
                order_type=self.ORDER_TYPE_MAP.get(params.order_type, "MARKET"),
                transaction_type=params.side,
                disclosed_quantity=0,
                trigger_price=params.trigger_price if params.trigger_price > 0 else 0,
                is_amo=params.variety == "AMO",
            )

            result = api.place_order(body, "2.0")
            order_id = result.data.order_id if result.data else ""

            logger.info("Upstox order placed", order_id=order_id,
                       symbol=params.symbol, side=params.side)

            return OrderResult(
                success=True, order_id=order_id, broker="upstox",
                status="PLACED", message=f"Order placed: {params.side} {params.quantity} {params.symbol}",
            )

        except Exception as e:
            logger.error("Upstox order failed", error=str(e))
            return OrderResult(success=False, broker="upstox", message=str(e))

    async def modify_order(self, order_id: str, params: OrderParams) -> OrderResult:
        if not self._logged_in:
            return OrderResult(success=False, broker="upstox", message="Not logged in")

        try:
            import upstox_client
            api = upstox_client.OrderApi(upstox_client.ApiClient(self._config))

            body = upstox_client.ModifyOrderRequest(
                quantity=params.quantity if params.quantity > 0 else None,
                price=params.price if params.price > 0 else None,
                trigger_price=params.trigger_price if params.trigger_price > 0 else None,
                order_type=self.ORDER_TYPE_MAP.get(params.order_type, None),
                validity=params.validity,
                order_id=order_id,
            )

            api.modify_order(body, "2.0")
            return OrderResult(success=True, order_id=order_id, broker="upstox",
                             status="MODIFIED", message="Order modified")
        except Exception as e:
            return OrderResult(success=False, broker="upstox", message=str(e))

    async def cancel_order(self, order_id: str) -> OrderResult:
        if not self._logged_in:
            return OrderResult(success=False, broker="upstox", message="Not logged in")

        try:
            import upstox_client
            api = upstox_client.OrderApi(upstox_client.ApiClient(self._config))
            api.cancel_order(order_id, "2.0")
            return OrderResult(success=True, order_id=order_id, broker="upstox",
                             status="CANCELLED", message="Order cancelled")
        except Exception as e:
            return OrderResult(success=False, broker="upstox", message=str(e))

    async def get_order_book(self) -> list[dict]:
        if not self._logged_in:
            return []
        try:
            import upstox_client
            api = upstox_client.OrderApi(upstox_client.ApiClient(self._config))
            result = api.get_order_book("2.0")
            return [o.__dict__ for o in (result.data or [])]
        except Exception:
            return []

    async def get_positions(self) -> list[Position]:
        if not self._logged_in:
            return []
        try:
            import upstox_client
            api = upstox_client.PortfolioApi(upstox_client.ApiClient(self._config))
            result = api.get_positions("2.0")
            positions = []
            for item in (result.data or []):
                d = item.__dict__ if hasattr(item, "__dict__") else {}
                positions.append(Position(
                    symbol=d.get("trading_symbol", ""),
                    exchange=d.get("exchange", ""),
                    side="BUY" if d.get("quantity", 0) > 0 else "SELL",
                    quantity=abs(d.get("quantity", 0)),
                    avg_price=float(d.get("average_price", 0)),
                    ltp=float(d.get("last_price", 0)),
                    pnl=float(d.get("pnl", 0)),
                    product=d.get("product", ""),
                    broker="upstox",
                ))
            return positions
        except Exception:
            return []

    async def get_holdings(self) -> list[Holding]:
        if not self._logged_in:
            return []
        try:
            import upstox_client
            api = upstox_client.PortfolioApi(upstox_client.ApiClient(self._config))
            result = api.get_holdings("2.0")
            holdings = []
            for item in (result.data or []):
                d = item.__dict__ if hasattr(item, "__dict__") else {}
                avg = float(d.get("average_price", 0))
                ltp = float(d.get("last_price", 0))
                qty = int(d.get("quantity", 0))
                pnl = (ltp - avg) * qty
                holdings.append(Holding(
                    symbol=d.get("trading_symbol", ""),
                    exchange=d.get("exchange", ""),
                    quantity=qty, avg_price=avg, ltp=ltp,
                    pnl=round(pnl, 2),
                    pnl_pct=round((ltp - avg) / avg * 100, 2) if avg else 0,
                    broker="upstox",
                ))
            return holdings
        except Exception:
            return []

    async def get_funds(self) -> dict:
        if not self._logged_in:
            return {}
        try:
            import upstox_client
            api = upstox_client.UserApi(upstox_client.ApiClient(self._config))
            result = api.get_user_fund_margin("2.0")
            equity = result.data.__dict__ if result.data else {}
            return {
                "available": float(equity.get("available_margin", 0)),
                "used": float(equity.get("used_margin", 0)),
                "broker": "upstox",
            }
        except Exception:
            return {}

    async def get_ltp(self, exchange: str, symbol: str) -> float:
        if not self._logged_in:
            return 0.0
        try:
            import upstox_client
            api = upstox_client.MarketQuoteApi(upstox_client.ApiClient(self._config))
            ux_exchange = self.EXCHANGE_MAP.get(exchange, "NSE_EQ")
            key = f"{ux_exchange}|{symbol}"
            result = api.ltp(key, "2.0")
            return float(result.data.get(key, {}).get("last_price", 0))
        except Exception:
            return 0.0

    async def get_quote(self, exchange: str, symbol: str) -> dict:
        if not self._logged_in:
            return {}
        try:
            import upstox_client
            api = upstox_client.MarketQuoteApi(upstox_client.ApiClient(self._config))
            ux_exchange = self.EXCHANGE_MAP.get(exchange, "NSE_EQ")
            key = f"{ux_exchange}|{symbol}"
            result = api.get_full_market_quote(key, "2.0")
            return result.data.get(key, {}).__dict__ if result.data else {}
        except Exception:
            return {}

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
