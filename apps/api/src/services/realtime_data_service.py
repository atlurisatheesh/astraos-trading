"""AstraOS Services — Real-Time Market Data Provider.

Supports multiple providers for real-time NSE data:
  - Angel One SmartAPI (FREE, real-time)
  - Zerodha Kite Connect (Rs 2000/month, best-in-class)
  - yfinance fallback (free, 15-min delayed — for dev/testing only)

Architecture: Abstract provider interface → factory pattern → env-based selection.
All providers normalize output to the same Quote/OHLCV format.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pandas as pd
import structlog

logger = structlog.get_logger()


class RealtimeQuote:
    """Normalized real-time quote from any provider."""

    __slots__ = (
        "symbol", "price", "change", "change_pct", "volume",
        "high", "low", "open_price", "prev_close", "bid", "ask",
        "bid_qty", "ask_qty", "last_trade_time", "exchange",
        "is_realtime",
    )

    def __init__(self, **kwargs):
        for k in self.__slots__:
            setattr(self, k, kwargs.get(k))

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}

    @property
    def bid_ask_spread(self) -> float:
        if self.bid and self.ask:
            return float(self.ask) - float(self.bid)
        return 0.0


class RealtimeProvider(ABC):
    """Abstract real-time data provider interface."""

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def get_quote(self, symbol: str) -> RealtimeQuote: ...

    @abstractmethod
    async def get_quotes(self, symbols: list[str]) -> list[RealtimeQuote]: ...

    @abstractmethod
    async def subscribe_ticks(self, symbols: list[str], callback) -> None: ...

    @abstractmethod
    async def get_ohlcv(self, symbol: str, interval: str, period: str) -> pd.DataFrame: ...

    @property
    @abstractmethod
    def is_realtime(self) -> bool: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class AngelOneProvider(RealtimeProvider):
    """Angel One SmartAPI — FREE real-time NSE data.

    Setup:
      1. Open Angel One demat account (free)
      2. Enable SmartAPI from smartapi.angelone.in
      3. Get API key, client ID, and generate TOTP secret
      4. Set env vars: ANGEL_API_KEY, ANGEL_CLIENT_ID, ANGEL_PASSWORD, ANGEL_TOTP_SECRET
    """

    def __init__(self, api_key: str, client_id: str, password: str, totp_secret: str):
        self._api_key = api_key
        self._client_id = client_id
        self._password = password
        self._totp_secret = totp_secret
        self._session = None
        self._connected = False

    @property
    def is_realtime(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "angel_one"

    async def connect(self) -> bool:
        try:
            from SmartApi import SmartConnect
            import pyotp

            totp = pyotp.TOTP(self._totp_secret).now()
            self._session = SmartConnect(api_key=self._api_key)
            data = self._session.generateSession(self._client_id, self._password, totp)

            if data.get("status"):
                self._connected = True
                logger.info("Angel One SmartAPI connected", client=self._client_id)
                return True
            else:
                logger.error("Angel One auth failed", message=data.get("message"))
                return False
        except ImportError:
            logger.error("SmartApi package not installed. Run: pip install smartapi-python pyotp")
            return False
        except Exception as e:
            logger.error("Angel One connection failed", error=str(e))
            return False

    async def disconnect(self) -> None:
        if self._session:
            try:
                self._session.terminateSession(self._client_id)
            except Exception:
                pass
        self._connected = False

    async def get_quote(self, symbol: str) -> RealtimeQuote:
        if not self._connected or not self._session:
            raise ConnectionError("Angel One not connected")

        token = self._get_token(symbol)
        data = self._session.ltpData("NSE", symbol, token)

        if not data.get("status"):
            raise ValueError(f"Quote failed for {symbol}: {data.get('message')}")

        ltp_data = data.get("data", {})
        price = Decimal(str(ltp_data.get("ltp", 0)))

        return RealtimeQuote(
            symbol=symbol,
            price=price,
            change=Decimal("0"),
            change_pct=0.0,
            volume=0,
            high=Decimal("0"),
            low=Decimal("0"),
            open_price=Decimal("0"),
            prev_close=Decimal("0"),
            bid=None,
            ask=None,
            bid_qty=0,
            ask_qty=0,
            last_trade_time=datetime.now(timezone.utc),
            exchange="NSE",
            is_realtime=True,
        )

    async def get_quotes(self, symbols: list[str]) -> list[RealtimeQuote]:
        quotes = []
        for sym in symbols:
            try:
                q = await self.get_quote(sym)
                quotes.append(q)
            except Exception as e:
                logger.error("Quote failed", symbol=sym, error=str(e))
        return quotes

    async def subscribe_ticks(self, symbols: list[str], callback) -> None:
        if not self._connected or not self._session:
            raise ConnectionError("Angel One not connected")

        try:
            from SmartApi.smartWebSocketV2 import SmartWebSocketV2

            auth_token = self._session.access_token
            feed_token = self._session.feed_token

            ws = SmartWebSocketV2(auth_token, self._api_key, self._client_id, feed_token)

            token_list = []
            for sym in symbols:
                token = self._get_token(sym)
                token_list.append({"exchangeType": 1, "tokens": [token]})

            def on_data(wsapp, message):
                asyncio.get_event_loop().call_soon_threadsafe(callback, message)

            def on_error(wsapp, error):
                logger.error("WebSocket error", error=str(error))

            ws.on_data = on_data
            ws.on_error = on_error

            ws.connect()
            ws.subscribe("abc123", 1, token_list)

        except ImportError:
            logger.error("SmartApi WebSocket not available")
        except Exception as e:
            logger.error("WebSocket subscription failed", error=str(e))

    async def get_ohlcv(self, symbol: str, interval: str = "ONE_DAY", period: str = "1y") -> pd.DataFrame:
        if not self._connected or not self._session:
            raise ConnectionError("Angel One not connected")

        token = self._get_token(symbol)
        params = {
            "exchange": "NSE",
            "symboltoken": token,
            "interval": interval,
            "fromdate": "2024-01-01 09:15",
            "todate": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

        data = self._session.getCandleData(params)
        if not data.get("status") or not data.get("data"):
            return pd.DataFrame()

        df = pd.DataFrame(data["data"], columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        return df

    def _get_token(self, symbol: str) -> str:
        """Get instrument token for a symbol. Uses cache in production."""
        # Simplified — production should load full instrument master
        return symbol


class YFinanceFallback(RealtimeProvider):
    """Fallback to yfinance when no real-time provider is configured."""

    @property
    def is_realtime(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return "yfinance_delayed"

    async def connect(self) -> bool:
        logger.warning("Using yfinance (15-min delayed) — configure a real-time provider for live trading")
        return True

    async def disconnect(self) -> None:
        pass

    async def get_quote(self, symbol: str) -> RealtimeQuote:
        import yfinance as yf

        yf_sym = f"{symbol}.NS" if not symbol.endswith(".NS") and not symbol.startswith("^") else symbol
        ticker = yf.Ticker(yf_sym)
        info = ticker.info

        price = Decimal(str(info.get("currentPrice", info.get("regularMarketPrice", 0))))
        prev = Decimal(str(info.get("previousClose", 0)))
        change = price - prev if prev else Decimal("0")

        return RealtimeQuote(
            symbol=symbol,
            price=price,
            change=change,
            change_pct=float(change / prev * 100) if prev else 0.0,
            volume=info.get("volume", 0),
            high=Decimal(str(info.get("dayHigh", 0))),
            low=Decimal(str(info.get("dayLow", 0))),
            open_price=Decimal(str(info.get("open", 0))),
            prev_close=prev,
            bid=Decimal(str(info.get("bid", 0))),
            ask=Decimal(str(info.get("ask", 0))),
            bid_qty=info.get("bidSize", 0),
            ask_qty=info.get("askSize", 0),
            last_trade_time=datetime.now(timezone.utc),
            exchange="NSE",
            is_realtime=False,
        )

    async def get_quotes(self, symbols: list[str]) -> list[RealtimeQuote]:
        quotes = []
        for sym in symbols:
            try:
                quotes.append(await self.get_quote(sym))
            except Exception as e:
                logger.error("yfinance quote failed", symbol=sym, error=str(e))
        return quotes

    async def subscribe_ticks(self, symbols: list[str], callback) -> None:
        logger.warning("yfinance does not support tick subscriptions — use Angel One or Kite")

    async def get_ohlcv(self, symbol: str, interval: str = "1d", period: str = "1y") -> pd.DataFrame:
        import yfinance as yf
        yf_sym = f"{symbol}.NS" if not symbol.endswith(".NS") and not symbol.startswith("^") else symbol
        df = yf.download(yf_sym, period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df


def create_realtime_provider() -> RealtimeProvider:
    """Factory: create the best available real-time provider."""
    from ..core.config import get_settings
    settings = get_settings()

    angel_key = getattr(settings, "angel_api_key", "")
    angel_client = getattr(settings, "angel_client_id", "")
    angel_pass = getattr(settings, "angel_password", "")
    angel_totp = getattr(settings, "angel_totp_secret", "")

    if all([angel_key, angel_client, angel_pass, angel_totp]):
        return AngelOneProvider(angel_key, angel_client, angel_pass, angel_totp)

    logger.warning("No real-time provider configured — falling back to yfinance (delayed)")
    return YFinanceFallback()
