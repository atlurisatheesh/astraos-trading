"""AstraOS Data Feed — NSE/BSE Official Data Adapters.

Provides adapters for:
1. NSE Official APIs — Bhav copy, indices, F&O data, corporate actions
2. BSE Official APIs — Bhavcopy, announcements, corporate actions
3. Instrument Master sync — NIFTY 500 symbol list
4. F&O Lot sizes + Expiry calendar

All endpoints are free (NSE/BSE public APIs) — no exchange licensing.
For low-latency tick data, use broker WebSocket (Kite Connect).
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone, date, timedelta
from typing import Any, Optional
import csv
import io

import httpx
import structlog

logger = structlog.get_logger()

# ── Common Headers (NSE blocks default user agents) ──
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
}

BSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.bseindia.com/",
}


# ── Data Classes ──

@dataclass
class NSEQuote:
    """NSE live quote data."""
    symbol: str
    series: str
    open_price: float
    high: float
    low: float
    close: float
    last_price: float
    prev_close: float
    change: float
    change_pct: float
    volume: int
    value: float  # ₹ in lakhs
    total_buy_qty: int
    total_sell_qty: int
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol, "series": self.series,
            "open": self.open_price, "high": self.high, "low": self.low,
            "close": self.close, "last_price": self.last_price,
            "prev_close": self.prev_close, "change": round(self.change, 2),
            "change_pct": round(self.change_pct, 2), "volume": self.volume,
            "value_lakhs": self.value, "buy_qty": self.total_buy_qty,
            "sell_qty": self.total_sell_qty, "timestamp": self.timestamp,
        }


@dataclass
class FOData:
    """F&O derivative data from NSE."""
    symbol: str
    expiry: str
    strike: float
    option_type: str  # CE / PE / FUT
    open_price: float
    high: float
    low: float
    close: float
    ltp: float
    volume: int
    oi: int
    change_in_oi: int

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol, "expiry": self.expiry, "strike": self.strike,
            "option_type": self.option_type, "open": self.open_price,
            "high": self.high, "low": self.low, "close": self.close,
            "ltp": self.ltp, "volume": self.volume, "oi": self.oi,
            "change_in_oi": self.change_in_oi,
        }


@dataclass
class IndexData:
    """Market index data."""
    name: str
    last: float
    change: float
    change_pct: float
    high: float
    low: float
    open_price: float
    prev_close: float
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "name": self.name, "last": self.last, "change": round(self.change, 2),
            "change_pct": round(self.change_pct, 2), "high": self.high,
            "low": self.low, "open": self.open_price, "prev_close": self.prev_close,
            "timestamp": self.timestamp,
        }


# ── NSE Adapter ──

class NSEAdapter:
    """NSE India official API adapter (free, public endpoints)."""

    BASE_URL = "https://www.nseindia.com"

    def __init__(self):
        self._session: Optional[httpx.AsyncClient] = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Create session with NSE cookies (required for API access)."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                headers=NSE_HEADERS,
                timeout=15,
                follow_redirects=True,
            )
            # Warm up by hitting the homepage to get cookies
            try:
                await self._session.get(self.BASE_URL)
            except Exception:
                pass
        return self._session

    async def _get(self, path: str) -> dict:
        """Make authenticated GET request to NSE API."""
        session = await self._get_session()
        url = f"{self.BASE_URL}{path}"
        try:
            resp = await session.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error("NSE API error", url=url, error=str(e))
            return {}

    async def get_quote(self, symbol: str) -> Optional[NSEQuote]:
        """Get live quote for a symbol from NSE."""
        data = await self._get(f"/api/quote-equity?symbol={symbol}")
        pi = data.get("priceInfo", {})
        if not pi:
            return None

        return NSEQuote(
            symbol=symbol,
            series=data.get("info", {}).get("series", "EQ"),
            open_price=pi.get("open", 0),
            high=pi.get("intraDayHighLow", {}).get("max", 0),
            low=pi.get("intraDayHighLow", {}).get("min", 0),
            close=pi.get("close", 0),
            last_price=pi.get("lastPrice", 0),
            prev_close=pi.get("previousClose", 0),
            change=pi.get("change", 0),
            change_pct=pi.get("pChange", 0),
            volume=data.get("securityWiseDP", {}).get("quantityTraded", 0),
            value=pi.get("intraDayHighLow", {}).get("value", 0),
            total_buy_qty=data.get("preOpenMarket", {}).get("totalBuyQuantity", 0),
            total_sell_qty=data.get("preOpenMarket", {}).get("totalSellQuantity", 0),
            timestamp=pi.get("lastUpdateTime", ""),
        )

    async def get_index(self, index_name: str = "NIFTY 50") -> Optional[IndexData]:
        """Get live index data."""
        data = await self._get(f"/api/equity-stockIndices?index={index_name.replace(' ', '%20')}")
        metadata = data.get("metadata", {})
        if not metadata:
            return None

        return IndexData(
            name=metadata.get("indexName", index_name),
            last=metadata.get("last", 0),
            change=metadata.get("change", 0),
            change_pct=metadata.get("pChange", 0),
            high=metadata.get("high", 0),
            low=metadata.get("low", 0),
            open_price=metadata.get("open", 0),
            prev_close=metadata.get("previousClose", 0),
            timestamp=metadata.get("timeVal", ""),
        )

    async def get_all_indices(self) -> list[IndexData]:
        """Get all major indices."""
        data = await self._get("/api/allIndices")
        indices = []
        for item in data.get("data", []):
            indices.append(IndexData(
                name=item.get("index", ""),
                last=item.get("last", 0),
                change=item.get("variation", 0),
                change_pct=item.get("percentChange", 0),
                high=item.get("high", 0),
                low=item.get("low", 0),
                open_price=item.get("open", 0),
                prev_close=item.get("previousClose", 0),
                timestamp=item.get("timeVal", ""),
            ))
        return indices

    async def get_option_chain(self, symbol: str = "NIFTY") -> dict:
        """Get F&O option chain from NSE."""
        data = await self._get(f"/api/option-chain-equities?symbol={symbol}")
        if not data:
            # Try index option chain
            data = await self._get(f"/api/option-chain-indices?symbol={symbol}")

        records = data.get("records", {})
        filtered = data.get("filtered", {})

        return {
            "symbol": symbol,
            "expiry_dates": records.get("expiryDates", []),
            "strike_prices": records.get("strikePrices", []),
            "underlying_value": records.get("underlyingValue", 0),
            "timestamp": records.get("timestamp", ""),
            "total_ce_oi": filtered.get("CE", {}).get("totOI", 0),
            "total_pe_oi": filtered.get("PE", {}).get("totOI", 0),
            "total_ce_vol": filtered.get("CE", {}).get("totVol", 0),
            "total_pe_vol": filtered.get("PE", {}).get("totVol", 0),
            "pcr_oi": round(
                filtered.get("PE", {}).get("totOI", 0) /
                max(filtered.get("CE", {}).get("totOI", 1), 1), 2
            ),
            "chain": records.get("data", []),
        }

    async def get_fno_lot_sizes(self) -> dict:
        """Get F&O lot sizes for all symbols."""
        data = await self._get("/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O")
        lot_sizes = {}
        for item in data.get("data", []):
            symbol = item.get("symbol", "")
            if symbol:
                lot_sizes[symbol] = {
                    "symbol": symbol,
                    "last_price": item.get("lastPrice", 0),
                    "change_pct": item.get("pChange", 0),
                }
        return lot_sizes

    async def get_corporate_actions(self, symbol: str) -> list[dict]:
        """Get upcoming corporate actions (dividends, splits, bonuses)."""
        data = await self._get(f"/api/corporates-corporateActions?index=equities&symbol={symbol}")
        return data if isinstance(data, list) else []

    async def get_nifty500_constituents(self) -> list[dict]:
        """Get NIFTY 500 constituent list (instrument master)."""
        data = await self._get("/api/equity-stockIndices?index=NIFTY%20500")
        constituents = []
        for item in data.get("data", []):
            if item.get("symbol"):
                constituents.append({
                    "symbol": item.get("symbol"),
                    "name": item.get("meta", {}).get("companyName", ""),
                    "industry": item.get("meta", {}).get("industry", ""),
                    "series": item.get("series", "EQ"),
                    "isin": item.get("meta", {}).get("isin", ""),
                    "last_price": item.get("lastPrice", 0),
                    "change_pct": item.get("pChange", 0),
                    "year_high": item.get("yearHigh", 0),
                    "year_low": item.get("yearLow", 0),
                })
        return constituents

    async def close(self):
        """Close the HTTP session."""
        if self._session:
            await self._session.aclose()
            self._session = None


# ── BSE Adapter ──

class BSEAdapter:
    """BSE India official API adapter (free, public endpoints)."""

    BASE_URL = "https://api.bseindia.com/BseIndiaAPI/api"

    async def _get(self, path: str, params: dict | None = None) -> Any:
        """Make GET request to BSE API."""
        async with httpx.AsyncClient(headers=BSE_HEADERS, timeout=15) as client:
            try:
                resp = await client.get(f"{self.BASE_URL}{path}", params=params)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as e:
                logger.error("BSE API error", path=path, error=str(e))
                return {}

    async def get_stock_quote(self, scrip_code: str) -> dict:
        """Get stock quote by BSE scrip code."""
        data = await self._get(f"/StockReachGraph/GetStockGraphData", params={
            "scripcode": scrip_code, "flag": "0", "fromdate": "", "todate": "",
        })
        return data if isinstance(data, dict) else {}

    async def get_sensex(self) -> dict:
        """Get SENSEX index data."""
        data = await self._get("/Sensex/getSensexData", params={"json": "1"})
        return data if isinstance(data, dict) else {}

    async def get_gainers_losers(self, index_type: str = "16") -> dict:
        """Get top gainers and losers.

        index_type: 16 = S&P BSE Sensex
        """
        data = await self._get("/MktRSSS498/getGainersnLosers", params={
            "type": "gainer", "indexcode": index_type,
        })
        return data

    async def get_announcements(self, from_date: str = "", to_date: str = "") -> list:
        """Get corporate announcements."""
        if not from_date:
            from_date = (date.today() - timedelta(days=7)).strftime("%Y%m%d")
        if not to_date:
            to_date = date.today().strftime("%Y%m%d")

        data = await self._get("/AnnGetData/Get", params={
            "strCat": "-1", "strPrevDate": from_date, "strScrip": "",
            "strSearch": "P", "strToDate": to_date, "strType": "C",
        })
        return data if isinstance(data, list) else []


# ── F&O Calendar ──

class FOCalendar:
    """F&O expiry calendar for NSE derivatives."""

    # Monthly expiry: Last Thursday of the month
    # Weekly expiry: Every Thursday (NIFTY, BANKNIFTY, FINNIFTY)

    WEEKLY_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}

    # Standard lot sizes (updated periodically by NSE)
    LOT_SIZES = {
        "NIFTY": 25, "BANKNIFTY": 15, "FINNIFTY": 25, "MIDCPNIFTY": 50,
        "RELIANCE": 250, "TCS": 150, "HDFCBANK": 550, "INFY": 300,
        "ICICIBANK": 1375, "SBIN": 1500, "WIPRO": 1500, "ITC": 1600,
        "LT": 300, "HCLTECH": 350, "BHARTIARTL": 950, "AXISBANK": 1200,
        "KOTAKBANK": 400, "MARUTI": 100, "BAJFINANCE": 125, "SUNPHARMA": 700,
        "TATAMOTORS": 1350, "HINDUNILVR": 300, "TATASTEEL": 5500,
        "ASIANPAINT": 200, "DRREDDY": 125, "ULTRACEMCO": 100,
        "POWERGRID": 2700, "NTPC": 2800, "TECHM": 600,
        "ADANIENT": 250, "JSWSTEEL": 675, "ONGC": 3850,
    }

    @classmethod
    def get_lot_size(cls, symbol: str) -> int:
        """Get lot size for a symbol."""
        return cls.LOT_SIZES.get(symbol.upper(), 1)

    @classmethod
    def get_next_expiry(cls, symbol: str = "NIFTY") -> date:
        """Calculate next expiry date (Thursday)."""
        today = date.today()
        days_ahead = 3 - today.weekday()  # Thursday = 3
        if days_ahead <= 0:
            days_ahead += 7
        return today + timedelta(days=days_ahead)

    @classmethod
    def get_monthly_expiry(cls, year: int, month: int) -> date:
        """Get monthly expiry (last Thursday of month)."""
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        last_date = date(year, month, last_day)

        while last_date.weekday() != 3:  # Thursday
            last_date -= timedelta(days=1)

        return last_date

    @classmethod
    def get_expiry_calendar(cls, months_ahead: int = 3) -> list[dict]:
        """Get upcoming expiry dates for the next N months."""
        today = date.today()
        expiries = []

        for m in range(months_ahead):
            month = today.month + m
            year = today.year
            if month > 12:
                month -= 12
                year += 1

            monthly = cls.get_monthly_expiry(year, month)
            expiries.append({
                "date": monthly.isoformat(),
                "type": "monthly",
                "day": monthly.strftime("%A"),
                "month": monthly.strftime("%B %Y"),
            })

        # Weekly expiries for next 4 weeks
        next_thursday = cls.get_next_expiry()
        for w in range(4):
            exp_date = next_thursday + timedelta(weeks=w)
            if exp_date.isoformat() not in [e["date"] for e in expiries]:
                expiries.append({
                    "date": exp_date.isoformat(),
                    "type": "weekly",
                    "day": exp_date.strftime("%A"),
                    "month": exp_date.strftime("%B %Y"),
                })

        expiries.sort(key=lambda x: x["date"])
        return expiries


# ── Singleton Adapters ──

_nse_adapter: Optional[NSEAdapter] = None
_bse_adapter: Optional[BSEAdapter] = None


def get_nse_adapter() -> NSEAdapter:
    global _nse_adapter
    if _nse_adapter is None:
        _nse_adapter = NSEAdapter()
    return _nse_adapter


def get_bse_adapter() -> BSEAdapter:
    global _bse_adapter
    if _bse_adapter is None:
        _bse_adapter = BSEAdapter()
    return _bse_adapter
