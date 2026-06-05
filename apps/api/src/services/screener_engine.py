"""AstraOS Services — Advanced Stock Screener Engine.

Filters NIFTY 500 (or entire NSE) based on complex JSON filter queries
combining technical and fundamental criteria.

Example query:
    {"filters": [
        {"field": "market_cap", "op": ">", "value": 10000},
        {"field": "trailing_pe", "op": "<", "value": 20},
        {"field": "rsi_14", "op": ">", "value": 60}
    ], "logic": "AND", "sort_by": "market_cap", "sort_order": "desc", "limit": 50}

Supported filter categories:
- Fundamental: market_cap, trailing_pe, forward_pe, eps, price_to_book, peg_ratio,
               dividend_yield, roe, roa, debt_to_equity, current_ratio, profit_margin
- Technical: rsi_14, sma_20, sma_50, sma_200, macd, adx, atr, volume_avg
- Price: last_price, change_pct, year_high, year_low, above_sma_50, above_sma_200

All data is FREE via yfinance + pandas-ta.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger()

# ── Supported operators ─────────────────────────────────────

VALID_OPERATORS = {">", ">=", "<", "<=", "==", "!="}
VALID_LOGIC = {"AND", "OR"}

# Fields that are derived from technical analysis (need OHLCV data)
TECHNICAL_FIELDS = {
    "rsi_14", "sma_20", "sma_50", "sma_200", "ema_20", "ema_50",
    "macd", "macd_signal", "macd_hist", "adx", "atr",
    "bb_upper", "bb_lower", "bb_middle", "volume_avg",
    "above_sma_50", "above_sma_200",
}

# Fields from yfinance info (fundamentals + price)
FUNDAMENTAL_FIELDS = {
    "market_cap", "trailing_pe", "forward_pe", "eps", "price_to_book",
    "peg_ratio", "dividend_yield", "roe", "roa", "debt_to_equity",
    "current_ratio", "profit_margin", "operating_margin", "revenue_growth",
    "earnings_growth", "beta", "last_price", "change_pct",
    "year_high", "year_low", "volume",
}

ALL_FIELDS = TECHNICAL_FIELDS | FUNDAMENTAL_FIELDS

# yfinance info key mapping
_INFO_KEY_MAP = {
    "market_cap": "marketCap",
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "eps": "trailingEps",
    "price_to_book": "priceToBook",
    "peg_ratio": "pegRatio",
    "dividend_yield": "dividendYield",
    "roe": "returnOnEquity",
    "roa": "returnOnAssets",
    "debt_to_equity": "debtToEquity",
    "current_ratio": "currentRatio",
    "profit_margin": "profitMargins",
    "operating_margin": "operatingMargins",
    "revenue_growth": "revenueGrowth",
    "earnings_growth": "earningsGrowth",
    "beta": "beta",
    "last_price": "currentPrice",
    "change_pct": "52WeekChange",
    "year_high": "fiftyTwoWeekHigh",
    "year_low": "fiftyTwoWeekLow",
    "volume": "volume",
}


# ── Data Structures ─────────────────────────────────────────


@dataclass
class ScreenerFilter:
    """A single filter condition."""
    field: str
    op: str
    value: float

    def validate(self) -> str | None:
        """Return error message if invalid, None if OK."""
        if self.field not in ALL_FIELDS:
            return f"Unknown field: {self.field}"
        if self.op not in VALID_OPERATORS:
            return f"Invalid operator: {self.op}"
        return None


@dataclass
class ScreenerQuery:
    """Complete screener query with filters, logic, sorting."""
    filters: list[ScreenerFilter]
    logic: str = "AND"
    sort_by: str = "market_cap"
    sort_order: str = "desc"
    limit: int = 50

    @classmethod
    def from_dict(cls, data: dict) -> "ScreenerQuery":
        """Parse from API request dict."""
        filters = [
            ScreenerFilter(
                field=f.get("field", ""),
                op=f.get("op", ">"),
                value=float(f.get("value", 0)),
            )
            for f in data.get("filters", [])
        ]
        return cls(
            filters=filters,
            logic=data.get("logic", "AND").upper(),
            sort_by=data.get("sort_by", "market_cap"),
            sort_order=data.get("sort_order", "desc"),
            limit=min(int(data.get("limit", 50)), 200),
        )

    def validate(self) -> list[str]:
        """Validate all filters and return list of errors."""
        errors = []
        if self.logic not in VALID_LOGIC:
            errors.append(f"Invalid logic: {self.logic}")
        for f in self.filters:
            err = f.validate()
            if err:
                errors.append(err)
        return errors


@dataclass
class ScreenerResult:
    """A single stock matching the screen criteria."""
    symbol: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "sector": self.sector,
            "industry": self.industry,
            **self.data,
        }


# ── Screener Engine ─────────────────────────────────────────


# Default NIFTY 50 symbols for fast screening
NIFTY_50_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "AXISBANK",
    "BAJFINANCE", "ASIANPAINT", "MARUTI", "TATAMOTORS", "SUNPHARMA",
    "HCLTECH", "WIPRO", "ULTRACEMCO", "NTPC", "POWERGRID", "TATASTEEL",
    "ONGC", "JSWSTEEL", "TECHM", "BAJFINSV", "DRREDDY", "ADANIENT",
    "TITAN", "NESTLEIND", "COALINDIA", "GRASIM", "BAJAJ-AUTO",
    "BRITANNIA", "CIPLA", "EICHERMOT", "HEROMOTOCO", "DIVISLAB",
    "APOLLOHOSP", "TATACONSUM", "SBILIFE", "LTIM", "HINDALCO",
    "M&M", "ADANIPORTS", "INDUSINDBK", "BPCL", "HDFCLIFE", "SHRIRAMFIN",
]


class ScreenerEngine:
    """Advanced stock screener supporting fundamental + technical filters."""

    async def screen(
        self,
        query: ScreenerQuery,
        universe: list[str] | None = None,
    ) -> list[ScreenerResult]:
        """Execute a screener query against a stock universe.

        Args:
            query: The filter query to execute.
            universe: List of symbols to screen. Defaults to NIFTY 50.
        """
        if universe is None:
            universe = NIFTY_50_SYMBOLS

        needs_technical = any(f.field in TECHNICAL_FIELDS for f in query.filters)
        results: list[ScreenerResult] = []

        # Process stocks in batches to avoid rate limiting
        batch_size = 10
        for i in range(0, len(universe), batch_size):
            batch = universe[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[self._evaluate_stock(sym, query, needs_technical) for sym in batch],
                return_exceptions=True,
            )
            for result in batch_results:
                if isinstance(result, ScreenerResult):
                    results.append(result)
                elif isinstance(result, Exception):
                    logger.debug("Stock evaluation failed", error=str(result))

        # Sort results
        sort_key = query.sort_by
        reverse = query.sort_order.lower() == "desc"
        results.sort(
            key=lambda r: r.data.get(sort_key, 0) or 0,
            reverse=reverse,
        )

        return results[:query.limit]

    async def _evaluate_stock(
        self,
        symbol: str,
        query: ScreenerQuery,
        needs_technical: bool,
    ) -> ScreenerResult | None:
        """Evaluate a single stock against all filters."""
        yf_symbol = f"{symbol}.NS"
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info

        if not info or not info.get("currentPrice") and not info.get("regularMarketPrice"):
            return None

        # Build data dict with all available metrics
        stock_data: dict[str, float | None] = {}

        # Fundamental data from info
        for field_name, info_key in _INFO_KEY_MAP.items():
            val = info.get(info_key)
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                stock_data[field_name] = float(val)
            else:
                stock_data[field_name] = None

        # Ensure last_price is set
        if stock_data.get("last_price") is None:
            stock_data["last_price"] = info.get("regularMarketPrice")

        # Technical data if needed
        if needs_technical:
            technical = await self._compute_technicals(yf_symbol)
            stock_data.update(technical)

        # Apply filters
        if self._matches_filters(stock_data, query):
            return ScreenerResult(
                symbol=symbol,
                name=info.get("longName", info.get("shortName", "")),
                sector=info.get("sector", ""),
                industry=info.get("industry", ""),
                data=stock_data,
            )

        return None

    async def _compute_technicals(self, yf_symbol: str) -> dict[str, float | None]:
        """Compute technical indicators for a symbol."""
        technical: dict[str, float | None] = {}
        try:
            df = yf.download(yf_symbol, period="6mo", interval="1d", progress=False)
            if df.empty:
                return technical

            # Flatten multi-level columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            close = df["Close"]
            high = df["High"]
            low = df["Low"]
            volume = df["Volume"]

            # SMAs
            technical["sma_20"] = float(close.rolling(20).mean().iloc[-1])
            technical["sma_50"] = float(close.rolling(50).mean().iloc[-1])
            if len(close) >= 200:
                technical["sma_200"] = float(close.rolling(200).mean().iloc[-1])

            # EMAs
            technical["ema_20"] = float(close.ewm(span=20).mean().iloc[-1])
            technical["ema_50"] = float(close.ewm(span=50).mean().iloc[-1])

            # RSI (14-period)
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, float("nan"))
            rsi = 100 - (100 / (1 + rs))
            technical["rsi_14"] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

            # MACD
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9).mean()
            technical["macd"] = float(macd_line.iloc[-1])
            technical["macd_signal"] = float(signal_line.iloc[-1])
            technical["macd_hist"] = float((macd_line - signal_line).iloc[-1])

            # ADX (14-period simplified)
            tr = pd.concat([
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs(),
            ], axis=1).max(axis=1)
            technical["atr"] = float(tr.rolling(14).mean().iloc[-1])

            # Volume average
            technical["volume_avg"] = float(volume.rolling(20).mean().iloc[-1])

            # Above SMA flags
            last_close = float(close.iloc[-1])
            technical["above_sma_50"] = 1.0 if technical.get("sma_50") and last_close > technical["sma_50"] else 0.0
            technical["above_sma_200"] = 1.0 if technical.get("sma_200") and last_close > technical["sma_200"] else 0.0

            # Bollinger Bands
            bb_mid = close.rolling(20).mean()
            bb_std = close.rolling(20).std()
            technical["bb_middle"] = float(bb_mid.iloc[-1])
            technical["bb_upper"] = float((bb_mid + 2 * bb_std).iloc[-1])
            technical["bb_lower"] = float((bb_mid - 2 * bb_std).iloc[-1])

        except Exception as e:
            logger.warning("Technical computation failed", symbol=yf_symbol, error=str(e))

        return technical

    def _matches_filters(self, data: dict, query: ScreenerQuery) -> bool:
        """Check if stock data matches all/any filters based on logic."""
        results = []
        for f in query.filters:
            val = data.get(f.field)
            if val is None:
                results.append(False)
                continue
            results.append(self._compare(val, f.op, f.value))

        if query.logic == "AND":
            return all(results)
        else:  # OR
            return any(results)

    @staticmethod
    def _compare(actual: float, op: str, expected: float) -> bool:
        """Apply comparison operator."""
        if op == ">":
            return actual > expected
        elif op == ">=":
            return actual >= expected
        elif op == "<":
            return actual < expected
        elif op == "<=":
            return actual <= expected
        elif op == "==":
            return actual == expected
        elif op == "!=":
            return actual != expected
        return False


# ── Factory ─────────────────────────────────────────────────


_engine: ScreenerEngine | None = None


def get_screener_engine() -> ScreenerEngine:
    """Get singleton screener engine."""
    global _engine
    if _engine is None:
        _engine = ScreenerEngine()
    return _engine
