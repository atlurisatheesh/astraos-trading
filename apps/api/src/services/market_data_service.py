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

    def _quote_sync(self, symbol: str) -> Quote:
        """Fetch a quote via fast_info (reliable on cloud hosts, unlike .info)."""
        yf_symbol = self._to_nse_symbol(symbol)
        ticker = yf.Ticker(yf_symbol)
        fi = ticker.fast_info

        price = Decimal(str(fi.last_price or 0))
        prev_close = Decimal(str(fi.previous_close or 0))
        change = price - prev_close if prev_close else Decimal("0")
        change_pct = float(change / prev_close * 100) if prev_close else 0.0

        return Quote(
            symbol=symbol,
            price=price,
            change=change,
            change_pct=round(change_pct, 2),
            volume=int(fi.last_volume or 0),
            high=Decimal(str(fi.day_high or 0)),
            low=Decimal(str(fi.day_low or 0)),
            open_price=Decimal(str(fi.open or 0)),
            prev_close=prev_close,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_quote(self, symbol: str) -> Quote:
        """Get a delayed quote for a single stock."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._quote_sync, symbol)

    async def get_ohlcv(self, symbol: str, interval: str = "1d", period: str = "1y") -> pd.DataFrame:
        """Get historical OHLCV data.

        Supports intraday intervals: 1m, 2m, 5m, 15m, 30m, 60m, 90m
        Note: yfinance limits intraday data to last 60 days (5m) or 7 days (1m).
        """
        yf_symbol = self._to_nse_symbol(symbol)

        # Adjust period for intraday (yfinance limits)
        if interval in ("1m", "2m"):
            period = min(period, "7d") if period not in ("1d", "5d", "7d") else period
        elif interval in ("5m", "15m", "30m"):
            period = "60d" if period not in ("1d", "5d", "1mo", "60d") else period

        df = yf.download(yf_symbol, period=period, interval=interval, progress=False)
        if df.empty:
            logger.warning("No data returned from yfinance", symbol=symbol, interval=interval)
            return pd.DataFrame()

        # Flatten multi-level columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.index.name = "date"
        return df

    async def get_intraday_ohlcv(self, symbol: str, interval: str = "15m") -> pd.DataFrame:
        """Get intraday OHLCV data (last 60 days for 5m+, 7 days for 1m).

        This is what real intraday traders use — not daily candles.
        """
        period = "7d" if interval in ("1m", "2m") else "60d"
        return await self.get_ohlcv(symbol, interval=interval, period=period)

    async def get_multiple_quotes(self, symbols: list[str]) -> list[Quote]:
        """Get quotes for multiple symbols in parallel."""
        import asyncio

        async def safe(symbol: str) -> Quote | None:
            try:
                return await self.get_quote(symbol)
            except Exception as e:
                logger.error("Failed to get quote", symbol=symbol, error=str(e))
                return None

        results = await asyncio.gather(*[safe(s) for s in symbols])
        return [q for q in results if q is not None]

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
    """Factory: get market data provider by name.

    Automatically upgrades to Angel One if credentials are configured,
    keeping yfinance as fallback for historical data.
    """
    # Auto-detect: if Angel One is configured, use it for quotes
    try:
        from ..core.config import get_settings
        settings = get_settings()
        if settings.angel_api_key and settings.angel_client_id:
            logger.info("Angel One credentials detected — real-time data available")
            # Still return yfinance for OHLCV (Angel One is better for live quotes)
            # The realtime_data_service handles live quote upgrades separately
    except Exception:
        pass

    providers = {
        "yfinance": YFinanceProvider,
    }
    cls = providers.get(provider, YFinanceProvider)
    return cls()
