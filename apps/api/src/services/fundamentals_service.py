"""AstraOS Services — Deep Fundamentals & Corporate Actions.

Leverages yfinance to fetch and serve institutional-grade fundamental data:
- Company Ratios: P/E, Forward P/E, EPS, P/B, PEG, Current Ratio, D/E
- Financial Statements: quarterly/annual Income, Balance Sheet, Cash Flow
- Corporate Actions: upcoming dividends, splits, earnings dates
- Company Profile: sector, industry, description, key officers

All data is FREE via yfinance — no paid API keys required.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger()


@dataclass
class CompanyRatios:
    """Key financial ratios for a company."""
    symbol: str
    trailing_pe: float | None = None
    forward_pe: float | None = None
    eps_trailing: float | None = None
    eps_forward: float | None = None
    price_to_book: float | None = None
    peg_ratio: float | None = None
    current_ratio: float | None = None
    debt_to_equity: float | None = None
    return_on_equity: float | None = None
    return_on_assets: float | None = None
    profit_margin: float | None = None
    operating_margin: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    dividend_yield: float | None = None
    dividend_rate: float | None = None
    payout_ratio: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    ev_to_ebitda: float | None = None
    beta: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class CompanyProfile:
    """Company overview and metadata."""
    symbol: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    description: str = ""
    website: str = ""
    country: str = ""
    city: str = ""
    employees: int | None = None
    exchange: str = ""
    currency: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v}


@dataclass
class CorporateAction:
    """A corporate action event (dividend, split, earnings)."""
    symbol: str
    action_type: str  # "dividend" | "split" | "earnings"
    date: str
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action_type": self.action_type,
            "date": self.date,
            "details": self.details,
        }


class FundamentalsService:
    """Fetch deep fundamental data using yfinance.

    Provides company ratios, financial statements, corporate actions,
    and profile data for any NSE/BSE listed stock.
    """

    def _to_nse_symbol(self, symbol: str) -> str:
        """Convert symbol to yfinance NSE format."""
        if not symbol.endswith(".NS") and not symbol.endswith(".BO") and not symbol.startswith("^"):
            return f"{symbol}.NS"
        return symbol

    def _safe_get(self, info: dict, key: str, default: Any = None) -> Any:
        """Safely get a value from yfinance info dict."""
        val = info.get(key, default)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return val

    async def get_ratios(self, symbol: str) -> CompanyRatios:
        """Get key financial ratios for a company."""
        yf_symbol = self._to_nse_symbol(symbol)
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info

        return CompanyRatios(
            symbol=symbol,
            trailing_pe=self._safe_get(info, "trailingPE"),
            forward_pe=self._safe_get(info, "forwardPE"),
            eps_trailing=self._safe_get(info, "trailingEps"),
            eps_forward=self._safe_get(info, "forwardEps"),
            price_to_book=self._safe_get(info, "priceToBook"),
            peg_ratio=self._safe_get(info, "pegRatio"),
            current_ratio=self._safe_get(info, "currentRatio"),
            debt_to_equity=self._safe_get(info, "debtToEquity"),
            return_on_equity=self._safe_get(info, "returnOnEquity"),
            return_on_assets=self._safe_get(info, "returnOnAssets"),
            profit_margin=self._safe_get(info, "profitMargins"),
            operating_margin=self._safe_get(info, "operatingMargins"),
            revenue_growth=self._safe_get(info, "revenueGrowth"),
            earnings_growth=self._safe_get(info, "earningsGrowth"),
            dividend_yield=self._safe_get(info, "dividendYield"),
            dividend_rate=self._safe_get(info, "dividendRate"),
            payout_ratio=self._safe_get(info, "payoutRatio"),
            market_cap=self._safe_get(info, "marketCap"),
            enterprise_value=self._safe_get(info, "enterpriseValue"),
            ev_to_ebitda=self._safe_get(info, "enterpriseToEbitda"),
            beta=self._safe_get(info, "beta"),
            fifty_two_week_high=self._safe_get(info, "fiftyTwoWeekHigh"),
            fifty_two_week_low=self._safe_get(info, "fiftyTwoWeekLow"),
        )

    async def get_profile(self, symbol: str) -> CompanyProfile:
        """Get company profile and overview."""
        yf_symbol = self._to_nse_symbol(symbol)
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info

        return CompanyProfile(
            symbol=symbol,
            name=self._safe_get(info, "longName", ""),
            sector=self._safe_get(info, "sector", ""),
            industry=self._safe_get(info, "industry", ""),
            description=self._safe_get(info, "longBusinessSummary", ""),
            website=self._safe_get(info, "website", ""),
            country=self._safe_get(info, "country", ""),
            city=self._safe_get(info, "city", ""),
            employees=self._safe_get(info, "fullTimeEmployees"),
            exchange=self._safe_get(info, "exchange", ""),
            currency=self._safe_get(info, "currency", ""),
        )

    async def get_income_statement(self, symbol: str, quarterly: bool = False) -> list[dict]:
        """Get income statement (quarterly or annual)."""
        yf_symbol = self._to_nse_symbol(symbol)
        ticker = yf.Ticker(yf_symbol)

        df = ticker.quarterly_income_stmt if quarterly else ticker.income_stmt
        return self._df_to_records(df, symbol)

    async def get_balance_sheet(self, symbol: str, quarterly: bool = False) -> list[dict]:
        """Get balance sheet (quarterly or annual)."""
        yf_symbol = self._to_nse_symbol(symbol)
        ticker = yf.Ticker(yf_symbol)

        df = ticker.quarterly_balance_sheet if quarterly else ticker.balance_sheet
        return self._df_to_records(df, symbol)

    async def get_cash_flow(self, symbol: str, quarterly: bool = False) -> list[dict]:
        """Get cash flow statement (quarterly or annual)."""
        yf_symbol = self._to_nse_symbol(symbol)
        ticker = yf.Ticker(yf_symbol)

        df = ticker.quarterly_cashflow if quarterly else ticker.cashflow
        return self._df_to_records(df, symbol)

    async def get_corporate_actions(self, symbol: str) -> list[CorporateAction]:
        """Get upcoming corporate actions: dividends, splits, earnings dates."""
        yf_symbol = self._to_nse_symbol(symbol)
        ticker = yf.Ticker(yf_symbol)
        actions: list[CorporateAction] = []

        # Dividends
        try:
            dividends = ticker.dividends
            if not dividends.empty:
                for date_idx, amount in dividends.tail(5).items():
                    actions.append(CorporateAction(
                        symbol=symbol,
                        action_type="dividend",
                        date=str(date_idx.date()) if hasattr(date_idx, "date") else str(date_idx),
                        details={"amount": float(amount), "currency": "INR"},
                    ))
        except Exception as e:
            logger.warning("Failed to fetch dividends", symbol=symbol, error=str(e))

        # Splits
        try:
            splits = ticker.splits
            if not splits.empty:
                for date_idx, ratio in splits.tail(5).items():
                    actions.append(CorporateAction(
                        symbol=symbol,
                        action_type="split",
                        date=str(date_idx.date()) if hasattr(date_idx, "date") else str(date_idx),
                        details={"ratio": float(ratio)},
                    ))
        except Exception as e:
            logger.warning("Failed to fetch splits", symbol=symbol, error=str(e))

        # Earnings dates
        try:
            calendar = ticker.calendar
            if calendar is not None and isinstance(calendar, dict):
                if "Earnings Date" in calendar:
                    for ed in calendar["Earnings Date"]:
                        actions.append(CorporateAction(
                            symbol=symbol,
                            action_type="earnings",
                            date=str(ed),
                            details={
                                "eps_estimate": calendar.get("Earnings Average"),
                                "revenue_estimate": calendar.get("Revenue Average"),
                            },
                        ))
        except Exception as e:
            logger.warning("Failed to fetch earnings dates", symbol=symbol, error=str(e))

        return actions

    async def get_analyst_recommendations(self, symbol: str) -> list[dict]:
        """Get analyst recommendations and target prices."""
        yf_symbol = self._to_nse_symbol(symbol)
        ticker = yf.Ticker(yf_symbol)

        try:
            recs = ticker.recommendations
            if recs is not None and not recs.empty:
                return recs.tail(10).reset_index().to_dict(orient="records")
        except Exception as e:
            logger.warning("Failed to fetch recommendations", symbol=symbol, error=str(e))

        return []

    def _df_to_records(self, df: pd.DataFrame, symbol: str) -> list[dict]:
        """Convert a yfinance financial statement DataFrame to records."""
        if df is None or df.empty:
            return []

        records = []
        for col in df.columns:
            period_data = {"period": str(col.date()) if hasattr(col, "date") else str(col)}
            for idx in df.index:
                val = df.loc[idx, col]
                if pd.notna(val):
                    period_data[str(idx)] = float(val)
            records.append(period_data)

        return records


# ── Factory ─────────────────────────────────────────────────


_service: FundamentalsService | None = None


def get_fundamentals_service() -> FundamentalsService:
    """Get singleton fundamentals service."""
    global _service
    if _service is None:
        _service = FundamentalsService()
    return _service
