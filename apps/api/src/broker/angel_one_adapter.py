"""AstraOS Broker — Angel One SmartAPI Adapter.

Connects to Angel One (formerly Angel Broking) via their SmartAPI.
Supports: login, quotes, order placement, positions, holdings, and WebSocket streaming.

Requires: pip install smartapi-python pyotp
API Key: Free from https://smartapi.angelone.in/
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


class AngelOrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "STOPLOSS_LIMIT"
    SL_MARKET = "STOPLOSS_MARKET"


class AngelProductType(str, Enum):
    DELIVERY = "DELIVERY"       # CNC
    INTRADAY = "INTRADAY"       # MIS
    CARRYFORWARD = "CARRYFORWARD"  # NRML (F&O)
    BO = "BO"                   # Bracket Order
    CO = "CO"                   # Cover Order


class AngelExchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"  # NSE F&O
    MCX = "MCX"
    CDS = "CDS"


@dataclass
class AngelOneConfig:
    """Angel One API credentials."""
    api_key: str = ""
    client_id: str = ""       # Angel One login ID
    password: str = ""
    totp_secret: str = ""     # For 2FA (TOTP)
    feed_token: str = ""      # WebSocket feed token
    refresh_token: str = ""


@dataclass
class AngelOrder:
    """Angel One order data."""
    order_id: str
    symbol: str
    exchange: str
    side: str  # BUY / SELL
    order_type: str
    product: str
    quantity: int
    price: float
    trigger_price: float
    status: str
    filled_qty: int = 0
    avg_price: float = 0
    timestamp: str = ""

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id, "symbol": self.symbol,
            "exchange": self.exchange, "side": self.side,
            "order_type": self.order_type, "product": self.product,
            "quantity": self.quantity, "price": self.price,
            "trigger_price": self.trigger_price, "status": self.status,
            "filled_qty": self.filled_qty, "avg_price": self.avg_price,
            "timestamp": self.timestamp,
        }


class AngelOneAdapter:
    """Angel One SmartAPI Broker Adapter.

    Usage:
        adapter = AngelOneAdapter(config)
        await adapter.login()
        quote = await adapter.get_ltp("NSE", "RELIANCE-EQ")
        order_id = await adapter.place_order(...)
    """

    def __init__(self, config: AngelOneConfig):
        self.config = config
        self._smart_api = None
        self._logged_in = False
        self._profile: dict = {}

    async def login(self) -> dict:
        """Authenticate with Angel One SmartAPI."""
        try:
            from SmartApi import SmartConnect
            import pyotp

            self._smart_api = SmartConnect(api_key=self.config.api_key)

            # Generate TOTP
            totp = pyotp.TOTP(self.config.totp_secret).now()

            # Login
            data = self._smart_api.generateSession(
                self.config.client_id,
                self.config.password,
                totp,
            )

            if data.get("status"):
                self.config.feed_token = self._smart_api.getfeedToken()
                self.config.refresh_token = data["data"].get("refreshToken", "")
                self._profile = self._smart_api.getProfile(
                    self.config.refresh_token
                ).get("data", {})
                self._logged_in = True

                logger.info("Angel One login successful",
                           client=self.config.client_id,
                           name=self._profile.get("name", ""))
                return {
                    "status": "success",
                    "client_id": self.config.client_id,
                    "name": self._profile.get("name", ""),
                    "email": self._profile.get("email", ""),
                    "broker": self._profile.get("broker", "ANGEL"),
                }
            else:
                logger.error("Angel One login failed", data=data)
                return {"status": "failed", "message": data.get("message", "Login failed")}

        except ImportError:
            logger.warning("smartapi-python not installed — using paper trading")
            return {"status": "paper", "message": "SmartAPI not installed. Using paper trading mode."}
        except Exception as e:
            logger.error("Angel One login error", error=str(e))
            return {"status": "error", "message": str(e)}

    async def get_ltp(self, exchange: str, symbol: str) -> dict:
        """Get Last Traded Price."""
        if not self._smart_api:
            return {"error": "Not logged in"}

        try:
            data = self._smart_api.ltpData(exchange, symbol, "")
            return data.get("data", {})
        except Exception as e:
            return {"error": str(e)}

    async def get_quote(self, exchange: str, symbol: str) -> dict:
        """Get full market quote."""
        if not self._smart_api:
            return {"error": "Not logged in"}

        try:
            mode = "FULL"
            token_list = [{"exchange": exchange, "tokens": [symbol]}]
            data = self._smart_api.getMarketData(mode, token_list)
            return data.get("data", {})
        except Exception as e:
            return {"error": str(e)}

    async def place_order(
        self,
        symbol: str,
        token: str,
        exchange: str = "NSE",
        side: str = "BUY",
        order_type: str = "MARKET",
        product: str = "DELIVERY",
        quantity: int = 1,
        price: float = 0,
        trigger_price: float = 0,
        variety: str = "NORMAL",
    ) -> dict:
        """Place an order on Angel One.

        Returns order_id on success.
        """
        if not self._smart_api:
            return {"error": "Not logged in"}

        try:
            order_params = {
                "variety": variety,
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": side,
                "exchange": exchange,
                "ordertype": order_type,
                "producttype": product,
                "duration": "DAY",
                "quantity": str(quantity),
                "price": str(price),
                "triggerprice": str(trigger_price),
            }

            result = self._smart_api.placeOrder(order_params)
            logger.info("Order placed", symbol=symbol, side=side, qty=quantity, result=result)
            return {"status": "success", "order_id": result}

        except Exception as e:
            logger.error("Order placement failed", error=str(e))
            return {"status": "failed", "error": str(e)}

    async def modify_order(self, order_id: str, **kwargs) -> dict:
        """Modify an existing order."""
        if not self._smart_api:
            return {"error": "Not logged in"}
        try:
            result = self._smart_api.modifyOrder({
                "orderid": order_id, **kwargs
            })
            return {"status": "success", "result": result}
        except Exception as e:
            return {"error": str(e)}

    async def cancel_order(self, order_id: str, variety: str = "NORMAL") -> dict:
        """Cancel an order."""
        if not self._smart_api:
            return {"error": "Not logged in"}
        try:
            result = self._smart_api.cancelOrder(order_id, variety)
            return {"status": "cancelled", "result": result}
        except Exception as e:
            return {"error": str(e)}

    async def get_order_book(self) -> list[dict]:
        """Get all orders for today."""
        if not self._smart_api:
            return []
        try:
            data = self._smart_api.orderBook()
            return data.get("data", []) or []
        except Exception:
            return []

    async def get_positions(self) -> list[dict]:
        """Get open positions."""
        if not self._smart_api:
            return []
        try:
            data = self._smart_api.position()
            return data.get("data", []) or []
        except Exception:
            return []

    async def get_holdings(self) -> list[dict]:
        """Get portfolio holdings (delivery stocks)."""
        if not self._smart_api:
            return []
        try:
            data = self._smart_api.holding()
            return data.get("data", []) or []
        except Exception:
            return []

    async def get_funds(self) -> dict:
        """Get available funds/margin."""
        if not self._smart_api:
            return {}
        try:
            data = self._smart_api.rmsLimit()
            return data.get("data", {})
        except Exception:
            return {}

    async def get_candle_data(
        self, exchange: str, symbol_token: str,
        interval: str = "ONE_DAY",
        from_date: str = "", to_date: str = "",
    ) -> list[dict]:
        """Get historical candle data.

        Intervals: ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE, THIRTY_MINUTE,
                   ONE_HOUR, ONE_DAY
        """
        if not self._smart_api:
            return []
        try:
            params = {
                "exchange": exchange,
                "symboltoken": symbol_token,
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date,
            }
            data = self._smart_api.getCandleData(params)
            return data.get("data", []) or []
        except Exception:
            return []

    @property
    def is_logged_in(self) -> bool:
        return self._logged_in

    @property
    def profile(self) -> dict:
        return self._profile


def get_angel_one_adapter(config: Optional[AngelOneConfig] = None) -> AngelOneAdapter:
    """Factory for Angel One adapter."""
    if config is None:
        import os
        config = AngelOneConfig(
            api_key=os.getenv("ANGEL_API_KEY", ""),
            client_id=os.getenv("ANGEL_CLIENT_ID", ""),
            password=os.getenv("ANGEL_PASSWORD", ""),
            totp_secret=os.getenv("ANGEL_TOTP_SECRET", ""),
        )
    return AngelOneAdapter(config)
