"""AstraOS Tests — Phase 7: Fundamentals Service Tests."""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

import pandas as pd

from src.services.fundamentals_service import (
    FundamentalsService,
    CompanyRatios,
    CompanyProfile,
    CorporateAction,
    get_fundamentals_service,
)


# ── Mock yfinance Data ──────────────────────────────────────

MOCK_INFO = {
    "longName": "Reliance Industries Limited",
    "sector": "Energy",
    "industry": "Oil & Gas Refining & Marketing",
    "longBusinessSummary": "Reliance Industries Limited operates as a conglomerate.",
    "website": "https://www.ril.com",
    "country": "India",
    "city": "Mumbai",
    "fullTimeEmployees": 389000,
    "exchange": "NSI",
    "currency": "INR",
    "trailingPE": 28.5,
    "forwardPE": 24.1,
    "trailingEps": 92.3,
    "forwardEps": 108.5,
    "priceToBook": 2.8,
    "pegRatio": 1.5,
    "currentRatio": 1.2,
    "debtToEquity": 35.0,
    "returnOnEquity": 0.12,
    "returnOnAssets": 0.06,
    "profitMargins": 0.08,
    "operatingMargins": 0.15,
    "revenueGrowth": 0.12,
    "earningsGrowth": 0.18,
    "dividendYield": 0.003,
    "dividendRate": 8.0,
    "payoutRatio": 0.09,
    "marketCap": 18000000000000,
    "enterpriseValue": 20000000000000,
    "enterpriseToEbitda": 12.5,
    "beta": 0.95,
    "fiftyTwoWeekHigh": 3025.0,
    "fiftyTwoWeekLow": 2200.0,
    "currentPrice": 2850.0,
}


# ── CompanyRatios Tests ─────────────────────────────────────


class TestCompanyRatios:
    """Test CompanyRatios dataclass."""

    def test_ratios_to_dict(self):
        ratios = CompanyRatios(
            symbol="RELIANCE",
            trailing_pe=28.5,
            forward_pe=24.1,
            eps_trailing=92.3,
            market_cap=18000000000000,
        )
        d = ratios.to_dict()
        assert d["symbol"] == "RELIANCE"
        assert d["trailing_pe"] == 28.5
        assert d["market_cap"] == 18000000000000

    def test_ratios_to_dict_excludes_none(self):
        ratios = CompanyRatios(symbol="TEST", trailing_pe=10.0)
        d = ratios.to_dict()
        assert "forward_pe" not in d
        assert "trailing_pe" in d


class TestCompanyProfile:
    """Test CompanyProfile dataclass."""

    def test_profile_to_dict(self):
        profile = CompanyProfile(
            symbol="RELIANCE",
            name="Reliance Industries",
            sector="Energy",
            industry="Oil & Gas",
        )
        d = profile.to_dict()
        assert d["symbol"] == "RELIANCE"
        assert d["name"] == "Reliance Industries"

    def test_profile_excludes_empty(self):
        profile = CompanyProfile(symbol="TEST", name="Test Co")
        d = profile.to_dict()
        assert "sector" not in d  # empty string excluded


class TestCorporateAction:
    """Test CorporateAction dataclass."""

    def test_action_to_dict(self):
        action = CorporateAction(
            symbol="RELIANCE",
            action_type="dividend",
            date="2026-03-15",
            details={"amount": 8.0, "currency": "INR"},
        )
        d = action.to_dict()
        assert d["symbol"] == "RELIANCE"
        assert d["action_type"] == "dividend"
        assert d["details"]["amount"] == 8.0


# ── FundamentalsService Tests ───────────────────────────────


class TestFundamentalsService:
    """Test FundamentalsService with mocked yfinance."""

    @pytest.fixture
    def svc(self):
        return FundamentalsService()

    @patch("src.services.fundamentals_service.yf.Ticker")
    @pytest.mark.asyncio
    async def test_get_ratios(self, mock_ticker_cls, svc):
        mock_ticker = MagicMock()
        mock_ticker.info = MOCK_INFO
        mock_ticker_cls.return_value = mock_ticker

        ratios = await svc.get_ratios("RELIANCE")
        assert ratios.symbol == "RELIANCE"
        assert ratios.trailing_pe == 28.5
        assert ratios.eps_trailing == 92.3
        assert ratios.market_cap == 18000000000000

    @patch("src.services.fundamentals_service.yf.Ticker")
    @pytest.mark.asyncio
    async def test_get_profile(self, mock_ticker_cls, svc):
        mock_ticker = MagicMock()
        mock_ticker.info = MOCK_INFO
        mock_ticker_cls.return_value = mock_ticker

        profile = await svc.get_profile("RELIANCE")
        assert profile.name == "Reliance Industries Limited"
        assert profile.sector == "Energy"
        assert profile.country == "India"

    @patch("src.services.fundamentals_service.yf.Ticker")
    @pytest.mark.asyncio
    async def test_get_ratios_handles_missing_fields(self, mock_ticker_cls, svc):
        mock_ticker = MagicMock()
        mock_ticker.info = {"currentPrice": 100}  # Minimal info
        mock_ticker_cls.return_value = mock_ticker

        ratios = await svc.get_ratios("UNKNOWN")
        assert ratios.symbol == "UNKNOWN"
        assert ratios.trailing_pe is None

    @patch("src.services.fundamentals_service.yf.Ticker")
    @pytest.mark.asyncio
    async def test_get_income_statement(self, mock_ticker_cls, svc):
        mock_ticker = MagicMock()
        # Create a mock DataFrame
        df = pd.DataFrame(
            {"Total Revenue": [100000, 120000], "Net Income": [10000, 15000]},
            index=pd.to_datetime(["2025-03-31", "2024-03-31"]),
        ).T
        mock_ticker.income_stmt = df
        mock_ticker_cls.return_value = mock_ticker

        result = await svc.get_income_statement("RELIANCE")
        assert len(result) == 2

    @patch("src.services.fundamentals_service.yf.Ticker")
    @pytest.mark.asyncio
    async def test_get_corporate_actions_dividends(self, mock_ticker_cls, svc):
        mock_ticker = MagicMock()
        mock_ticker.dividends = pd.Series(
            [8.0, 9.0],
            index=pd.to_datetime(["2025-09-15", "2026-02-15"]),
        )
        mock_ticker.splits = pd.Series(dtype=float)
        mock_ticker.calendar = None
        mock_ticker_cls.return_value = mock_ticker

        actions = await svc.get_corporate_actions("RELIANCE")
        div_actions = [a for a in actions if a.action_type == "dividend"]
        assert len(div_actions) == 2
        assert div_actions[0].details["amount"] == 8.0

    def test_safe_get_handles_none(self, svc):
        assert svc._safe_get({"key": None}, "key", "default") == "default"

    def test_safe_get_handles_nan(self, svc):
        assert svc._safe_get({"key": float("nan")}, "key", "default") == "default"

    def test_safe_get_returns_value(self, svc):
        assert svc._safe_get({"key": 42}, "key") == 42

    def test_nse_symbol_conversion(self, svc):
        assert svc._to_nse_symbol("RELIANCE") == "RELIANCE.NS"
        assert svc._to_nse_symbol("RELIANCE.NS") == "RELIANCE.NS"
        assert svc._to_nse_symbol("^NSEI") == "^NSEI"


class TestFundamentalsFactory:
    """Test singleton factory."""

    def test_get_fundamentals_service_returns_instance(self):
        svc = get_fundamentals_service()
        assert isinstance(svc, FundamentalsService)

    def test_get_fundamentals_service_is_singleton(self):
        svc1 = get_fundamentals_service()
        svc2 = get_fundamentals_service()
        assert svc1 is svc2
