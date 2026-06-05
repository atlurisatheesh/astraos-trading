"""AstraOS Services — Market Data Provider (yfinance, free)."""

from abc import ABC, abstractmethod
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger()


class Quote:
    """Real-time (delayed) stock quote."""
    def __init__(self, symbol: str, price: Decimal, change: Decimal, change_pct: float,
                 volume: int, high: Decimal, low: Decimal, open_price: Decimal,
                 prev_close: Decimal, timestamp: datetime):
        self.symbol = symbol
        self.price = price
        self.change = change
        self.change_pct = change_pct
        self.volume = volume
        self.high = high
        self.low = low
        self.open_price = open_price
        self.prev_close = prev_close
        self.timestamp = timestamp

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol, "price": float(self.price),
            "change": float(self.change), "change_pct": self.change_pct,
            "volume": self.volume, "high": float(self.high), "low": float(self.low),
            "open": float(self.open_price), "prev_close": float(self.prev_close),
            "timestamp": self.timestamp.isoformat(),
        }


class MarketDataProvider(ABC):
    """Abstract interface for market data — swap free ↔ paid via env var."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    async def get_ohlcv(self, symbol: str, interval: str = "1d", period: str = "1y") -> pd.DataFrame: ...

    @abstractmethod
    async def get_multiple_quotes(self, symbols: list[str]) -> list[Quote]: ...


class YFinanceProvider(MarketDataProvider):
    """FREE market data provider using yfinance. Delayed 15min, rate-limited."""

    def _to_nse_symbol(self, symbol: str) -> str:
        """Convert symbol to yfinance NSE format."""
        if not symbol.endswith(".NS") and not symbol.startswith("^"):
            return f"{symbol}.NS"
        return symbol

    async def get_quote(self, symbol: str) -> Quote:
        """Get a delayed quote for a single stock."""
        yf_symbol = self._to_nse_symbol(symbol)
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info

        price = Decimal(str(info.get("currentPrice", info.get("regularMarketPrice", 0))))
        prev_close = Decimal(str(info.get("previousClose", info.get("regularMarketPreviousClose", 0))))
        change = price - prev_close if prev_close else Decimal("0")
        change_pct = float(change / prev_close * 100) if prev_close else 0.0

        return Quote(
            symbol=symbol,
            price=price,
            change=change,
            change_pct=round(change_pct, 2),
            volume=info.get("volume", info.get("regularMarketVolume", 0)),
            high=Decimal(str(info.get("dayHigh", info.get("regularMarketDayHigh", 0)))),
            low=Decimal(str(info.get("dayLow", info.get("regularMarketDayLow", 0)))),
            open_price=Decimal(str(info.get("open", info.get("regularMarketOpen", 0)))),
            prev_close=prev_close,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_ohlcv(self, symbol: str, interval: str = "1d", period: str = "1y") -> pd.DataFrame:
        """Get historical OHLCV data."""
        yf_symbol = self._to_nse_symbol(symbol)
        df = yf.download(yf_symbol, period=period, interval=interval, progress=False)
        if df.empty:
            logger.warning("No data returned from yfinance", symbol=symbol)
            return pd.DataFrame()

        # Flatten multi-level columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.index.name = "date"
        return df

    async def get_multiple_quotes(self, symbols: list[str]) -> list[Quote]:
        """Get quotes for multiple symbols."""
        quotes = []
        for symbol in symbols:
            try:
                q = await self.get_quote(symbol)
                quotes.append(q)
            except Exception as e:
                logger.error("Failed to get quote", symbol=symbol, error=str(e))
        return quotes

    async def get_options_chain(self, symbol: str) -> dict:
        """Get options chain data for F&O."""
        yf_symbol = self._to_nse_symbol(symbol)
        ticker = yf.Ticker(yf_symbol)

        try:
            expirations = ticker.options
            if not expirations:
                return {"expirations": [], "calls": [], "puts": []}

            # Get nearest expiry
            nearest = expirations[0]
            chain = ticker.option_chain(nearest)

            calls = chain.calls.to_dict(orient="records") if not chain.calls.empty else []
            puts = chain.puts.to_dict(orient="records") if not chain.puts.empty else []

            return {
                "expirations": list(expirations),
                "selected_expiry": nearest,
                "calls": calls,
                "puts": puts,
            }
        except Exception as e:
            logger.error("Options chain error", symbol=symbol, error=str(e))
            return {"expirations": [], "calls": [], "puts": []}


def get_market_data_provider(provider: str = "yfinance") -> MarketDataProvider:
    """Factory: get market data provider by name."""
    providers = {
        "yfinance": YFinanceProvider,
    }
    cls = providers.get(provider, YFinanceProvider)
    return cls()
