"""AstraOS Broker — Zerodha Kite Connect Adapter.

Full integration with Zerodha Kite via kiteconnect SDK.
Supports: login, orders, positions, holdings, funds, LTP, quotes, historical data.

Requirements:
    pip install kiteconnect
    API Key: https://kite.trade (₹2000/month for API access)

Auth Flow:
    1. User visits: https://kite.zerodha.com/connect/login?v=3&api_key=YOUR_KEY
    2. After login, Zerodha redirects with ?request_token=xxx
    3. Call login() with the request_token to get access_token
"""

from datetime import datetime, timezone

import structlog  # type: ignore

from . import BrokerAdapter, BrokerCredentials, OrderParams, OrderResult, Position, Holding  # type: ignore

logger = structlog.get_logger()


class KiteAdapter(BrokerAdapter):
    """Zerodha Kite Connect broker adapter.

    Supports all NSE, BSE, NFO, MCX, CDS segments.
    F&O, equity, commodity trading.
    """

    name = "kite"

    # Product type mapping: unified -> Kite
    PRODUCT_MAP = {
        "DELIVERY": "CNC",
        "CNC": "CNC",
        "INTRADAY": "MIS",
        "MIS": "MIS",
        "NRML": "NRML",
        "CARRYFORWARD": "NRML",
    }

    # Order type mapping
    ORDER_TYPE_MAP = {
        "MARKET": "MARKET",
        "LIMIT": "LIMIT",
        "SL": "SL",
        "SL-M": "SL-M",
        "STOPLOSS_LIMIT": "SL",
        "STOPLOSS_MARKET": "SL-M",
    }

    # Variety mapping
    VARIETY_MAP = {
        "NORMAL": "regular",
        "AMO": "amo",
        "BO": "bo",
        "CO": "co",
        "ICEBERG": "iceberg",
        "AUCTION": "auction",
    }

    def __init__(self):
        self._kite = None
        self._logged_in = False
        self._profile: dict = {}
        self._api_key: str = ""

    async def login(self, credentials: BrokerCredentials) -> dict:
        """Login to Kite Connect.

        Requires api_key + api_secret + request_token (from redirect URL).
        OR api_key + access_token (if already have a valid session).
        """
        try:
            from kiteconnect import KiteConnect

            self._api_key = credentials.api_key
            self._kite = KiteConnect(api_key=credentials.api_key)

            if credentials.access_token:
                # Reuse existing session
                self._kite.set_access_token(credentials.access_token)
            elif credentials.request_token:
                # Generate new session
                data = self._kite.generate_session(
                    credentials.request_token,
                    api_secret=credentials.api_secret,
                )
                self._kite.set_access_token(data["access_token"])
            else:
                login_url = self._kite.login_url()
                return {
                    "status": "pending",
                    "broker": "kite",
                    "message": "Visit the login URL and provide the request_token from the redirect",
                    "login_url": login_url,
                }

            self._profile = self._kite.profile()
            self._logged_in = True

            logger.info("Kite login successful",
                       user=self._profile.get("user_name", ""),
                       client=self._profile.get("user_id", ""))

            return {
                "status": "success",
                "broker": "kite",
                "user_id": self._profile.get("user_id"),
                "user_name": self._profile.get("user_name"),
                "email": self._profile.get("email"),
                "exchanges": self._profile.get("exchanges", []),
                "products": self._profile.get("products", []),
            }

        except ImportError:
            return {"status": "error", "broker": "kite",
                    "message": "kiteconnect not installed. Run: pip install kiteconnect"}
        except Exception as e:
            logger.error("Kite login failed", error=str(e))
            return {"status": "error", "broker": "kite", "message": str(e)}

    async def place_order(self, params: OrderParams) -> OrderResult:
        if not self._kite:
            return OrderResult(success=False, broker="kite", message="Not logged in")

        try:
            variety = self.VARIETY_MAP.get(params.variety, "regular")
            product = self.PRODUCT_MAP.get(params.product, "CNC")
            order_type = self.ORDER_TYPE_MAP.get(params.order_type, "MARKET")

            order_params = {
                "tradingsymbol": params.symbol,
                "exchange": params.exchange,
                "transaction_type": params.side,
                "quantity": params.quantity,
                "order_type": order_type,
                "product": product,
                "validity": params.validity,
            }

            if params.price > 0:
                order_params["price"] = params.price
            if params.trigger_price > 0:
                order_params["trigger_price"] = params.trigger_price
            if params.tag:
                order_params["tag"] = params.tag

            order_id = self._kite.place_order(variety=variety, **order_params)

            logger.info("Kite order placed", order_id=order_id,
                       symbol=params.symbol, side=params.side, qty=params.quantity)

            return OrderResult(
                success=True, order_id=str(order_id), broker="kite",
                status="PLACED", message=f"Order placed: {params.side} {params.quantity} {params.symbol}",
            )

        except Exception as e:
            logger.error("Kite order failed", error=str(e))
            return OrderResult(success=False, broker="kite", message=str(e))

    async def modify_order(self, order_id: str, params: OrderParams) -> OrderResult:
        if not self._kite:
            return OrderResult(success=False, broker="kite", message="Not logged in")

        try:
            variety = self.VARIETY_MAP.get(params.variety, "regular")
            mod_params = {}
            if params.quantity > 0:
                mod_params["quantity"] = params.quantity
            if params.price > 0:
                mod_params["price"] = params.price
            if params.trigger_price > 0:
                mod_params["trigger_price"] = params.trigger_price
            if params.order_type:
                mod_params["order_type"] = self.ORDER_TYPE_MAP.get(params.order_type, "MARKET")

            self._kite.modify_order(variety=variety, order_id=order_id, **mod_params)
            return OrderResult(success=True, order_id=order_id, broker="kite",
                             status="MODIFIED", message="Order modified")
        except Exception as e:
            return OrderResult(success=False, broker="kite", message=str(e))

    async def cancel_order(self, order_id: str) -> OrderResult:
        if not self._kite:
            return OrderResult(success=False, broker="kite", message="Not logged in")

        try:
            self._kite.cancel_order(variety="regular", order_id=order_id)
            return OrderResult(success=True, order_id=order_id, broker="kite",
                             status="CANCELLED", message="Order cancelled")
        except Exception as e:
            return OrderResult(success=False, broker="kite", message=str(e))

    async def get_order_book(self) -> list[dict]:
        if not self._kite:
            return []
        try:
            return self._kite.orders() or []
        except Exception:
            return []

    async def get_positions(self) -> list[Position]:
        if not self._kite:
            return []
        try:
            data = self._kite.positions()
            positions = []
            for item in (data.get("net", []) or []):
                positions.append(Position(
                    symbol=item.get("tradingsymbol", ""),
                    exchange=item.get("exchange", ""),
                    side="BUY" if item.get("quantity", 0) > 0 else "SELL",
                    quantity=abs(item.get("quantity", 0)),
                    avg_price=float(item.get("average_price", 0)),
                    ltp=float(item.get("last_price", 0)),
                    pnl=float(item.get("pnl", 0)),
                    product=item.get("product", ""),
                    broker="kite",
                ))
            return positions
        except Exception:
            return []

    async def get_holdings(self) -> list[Holding]:
        if not self._kite:
            return []
        try:
            data = self._kite.holdings() or []
            holdings = []
            for item in data:
                avg = float(item.get("average_price", 0))
                ltp = float(item.get("last_price", 0))
                qty = int(item.get("quantity", 0))
                pnl = (ltp - avg) * qty
                pnl_pct = ((ltp - avg) / avg * 100) if avg > 0 else 0

                holdings.append(Holding(
                    symbol=item.get("tradingsymbol", ""),
                    exchange=item.get("exchange", ""),
                    quantity=qty,
                    avg_price=avg,
                    ltp=ltp,
                    pnl=round(pnl, 2),
                    pnl_pct=round(pnl_pct, 2),
                    broker="kite",
                ))
            return holdings
        except Exception:
            return []

    async def get_funds(self) -> dict:
        if not self._kite:
            return {}
        try:
            margins = self._kite.margins()
            equity = margins.get("equity", {})
            return {
                "available": float(equity.get("available", {}).get("cash", 0)),
                "used": float(equity.get("utilised", {}).get("debits", 0)),
                "total": float(equity.get("net", 0)),
                "broker": "kite",
            }
        except Exception:
            return {}

    async def get_ltp(self, exchange: str, symbol: str) -> float:
        if not self._kite:
            return 0.0
        try:
            key = f"{exchange}:{symbol}"
            data = self._kite.ltp(key)
            return float(data.get(key, {}).get("last_price", 0))
        except Exception:
            return 0.0

    async def get_quote(self, exchange: str, symbol: str) -> dict:
        if not self._kite:
            return {}
        try:
            key = f"{exchange}:{symbol}"
            data = self._kite.quote(key)
            return data.get(key, {})
        except Exception:
            return {}

    async def get_historical_data(
        self, instrument_token: str,
        from_date: str, to_date: str,
        interval: str = "day",
    ) -> list[dict]:
        """Get historical candle data.

        Intervals: minute, 3minute, 5minute, 10minute, 15minute,
                   30minute, 60minute, day, week, month
        """
        if not self._kite:
            return []
        try:
            data = self._kite.historical_data(
                instrument_token, from_date, to_date, interval,
            )
            return data or []
        except Exception:
            return []

    def get_login_url(self) -> str:
        """Get the Kite login URL for OAuth flow."""
        if self._kite:
            return self._kite.login_url()
        return ""

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in
