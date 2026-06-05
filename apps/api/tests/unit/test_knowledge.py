"""AstraOS Tests — Knowledge base, investment frameworks, and strategy engine."""

import pytest

from src.knowledge.investment_frameworks import (
    GrahamScreen, FisherScreen, ShenanigansDetector, damodaran_dcf, ExpectedReturnDecomposition
)
from src.knowledge.banknifty_strategies import (
    classify_regime, recommend_strategy, generate_bank_nifty_setup, MarketRegime, STRATEGY_LIBRARY, _build_legs
)


class TestGrahamScreen:
    """Benjamin Graham defensive investor criteria."""

    def test_strong_value_stock(self):
        screen = GrahamScreen(
            pe_ratio=10, pb_ratio=1.2, current_ratio=3, debt_to_equity=0.2,
            earnings_growth_10y=12, dividend_years=10, market_cap_cr=10000,
        )
        result = screen.score()
        assert result["verdict"] == "STRONG_VALUE"
        assert result["passed"] >= 6

    def test_failing_stock(self):
        screen = GrahamScreen(
            pe_ratio=80, pb_ratio=12, current_ratio=0.5, debt_to_equity=3,
            earnings_growth_10y=-5, dividend_years=0, market_cap_cr=100,
        )
        result = screen.score()
        assert result["verdict"] == "FAIL"
        assert result["passed"] <= 1

    def test_graham_number(self):
        screen = GrahamScreen(pe_ratio=14, pb_ratio=1.5)
        result = screen.score()
        assert result["checks"]["graham_number"] == True  # 14 * 1.5 = 21 < 22.5

    def test_negative_pe_fails(self):
        screen = GrahamScreen(pe_ratio=-5, pb_ratio=1.0)
        result = screen.score()
        assert result["checks"]["pe_under_15"] == False


class TestFisherScreen:
    """Philip Fisher business quality criteria."""

    def test_outstanding_business(self):
        screen = FisherScreen(
            revenue_growth_3y=25, profit_margin=20, roe=25,
            rd_to_revenue=8, management_integrity=9, competitive_moat=9, market_potential=9,
        )
        result = screen.score()
        assert result["verdict"] == "OUTSTANDING"

    def test_average_business(self):
        screen = FisherScreen(
            revenue_growth_3y=5, profit_margin=3, roe=8,
            rd_to_revenue=1, management_integrity=4, competitive_moat=3, market_potential=4,
        )
        result = screen.score()
        assert result["verdict"] == "AVERAGE"


class TestShenanigansDetector:
    """Howard Schilit accounting fraud detection."""

    def test_clean_company(self):
        detector = ShenanigansDetector(
            revenue_growth=15, cfo_growth=18, dso_change=2,
            capex_to_revenue_change=1, other_income_pct=3,
            related_party_pct=1, auditor_changed=False,
        )
        result = detector.detect()
        assert result["risk_level"] == "LOW"
        assert result["recommendation"] == "CLEAR"

    def test_high_fraud_risk(self):
        detector = ShenanigansDetector(
            revenue_growth=50, cfo_growth=5, dso_change=30,
            capex_to_revenue_change=8, other_income_pct=25,
            related_party_pct=12, auditor_changed=True,
            accounting_policy_changed=True, inventory_growth_vs_revenue=40,
        )
        result = detector.detect()
        assert result["risk_level"] == "HIGH"
        assert result["recommendation"] == "AVOID"
        assert result["flagged"] >= 4


class TestDamodaranDCF:
    """Damodaran discounted cash flow valuation."""

    def test_basic_dcf(self):
        result = damodaran_dcf(
            fcf=5000, growth_rate=0.12, terminal_growth=0.04,
            wacc=0.10, projection_years=10, shares_outstanding=100,
        )
        assert result["intrinsic_per_share"] > 0
        assert result["buy_price_25_mos"] < result["intrinsic_per_share"]
        assert result["buy_price_40_mos"] < result["buy_price_25_mos"]
        assert len(result["projected_fcf"]) == 10

    def test_high_growth_dcf(self):
        result = damodaran_dcf(
            fcf=1000, growth_rate=0.25, terminal_growth=0.05,
            wacc=0.12, projection_years=10, shares_outstanding=50,
        )
        assert result["intrinsic_per_share"] > 200  # High growth = high value


class TestExpectedReturns:
    """Ilmanen expected return decomposition."""

    def test_market_only(self):
        decomp = ExpectedReturnDecomposition(market_beta=1.0)
        result = decomp.expected_return()
        assert result["expected_return"] == 12.5  # 6.5 + 1.0 * 6.0

    def test_multi_factor(self):
        decomp = ExpectedReturnDecomposition(
            market_beta=1.0, value_loading=0.5, momentum_loading=0.3,
        )
        result = decomp.expected_return()
        assert result["expected_return"] > 12.5  # More factors = higher return


class TestRegimeClassification:
    """Market regime classification."""

    def test_crisis_regime(self):
        assert classify_regime(35, 15, 3, 5) == MarketRegime.CRISIS

    def test_expiry_regime(self):
        assert classify_regime(16, 20, 1, 1) == MarketRegime.EXPIRY

    def test_high_vol_regime(self):
        assert classify_regime(24, 20, 1.5, 5) == MarketRegime.HIGH_VOL

    def test_trending_up(self):
        assert classify_regime(15, 30, 1, 5, "up") == MarketRegime.TRENDING_UP

    def test_range_regime(self):
        assert classify_regime(13, 18, 0.8, 5) == MarketRegime.RANGE


class TestStrategyRecommender:
    """Options strategy recommendation."""

    def test_trending_strategies(self):
        strategies = recommend_strategy(MarketRegime.TRENDING_UP, 16, 52000, 5)
        assert len(strategies) > 0
        assert all(s.name for s in strategies)

    def test_range_strategies(self):
        strategies = recommend_strategy(MarketRegime.RANGE, 14, 52000, 10)
        assert len(strategies) > 0
        names = [s.name for s in strategies]
        assert any("Strangle" in n or "Condor" in n or "Butterfly" in n or "Spread" in n or "Calendar" in n for n in names)

    def test_strategy_library_completeness(self):
        assert len(STRATEGY_LIBRARY) >= 10


class TestBankNiftySetup:
    """Bank Nifty trade setup generation."""

    def test_trend_setup(self):
        setup = generate_bank_nifty_setup(MarketRegime.TRENDING_UP, 52000, 16, 450)
        assert setup is not None
        assert setup.setup_type == "trend"
        assert setup.stop_loss < setup.entry_price
        assert setup.target_1 > setup.entry_price

    def test_breakout_setup(self):
        setup = generate_bank_nifty_setup(MarketRegime.BREAKOUT, 52000, 20, 500)
        assert setup is not None
        assert setup.setup_type == "breakout_failure"

    def test_range_setup(self):
        setup = generate_bank_nifty_setup(MarketRegime.RANGE, 52000, 13, 300)
        assert setup is not None
        assert setup.setup_type == "range_premium"

    def test_crisis_no_trade(self):
        setup = generate_bank_nifty_setup(MarketRegime.CRISIS, 52000, 35, 800)
        assert setup is not None
        assert setup.setup_type == "no_trade"
        assert setup.position_size == 0

    def test_build_legs(self):
        legs = _build_legs("iron_condor", 52000, 5)
        assert len(legs) == 4  # 4-leg structure
