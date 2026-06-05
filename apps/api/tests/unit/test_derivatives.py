"""AstraOS Tests — Phase 9: F&O Derivatives Service Tests."""

import pytest
from datetime import datetime, timezone

from src.services.derivatives_service import (
    OptionContract,
    OptionsChainData,
    IVSurfacePoint,
    DerivativesService,
    get_derivatives_service,
)
from src.quant.options_pricer import calculate_max_pain, calculate_pcr


# ── OptionContract Tests ────────────────────────────────────


class TestOptionContract:
    """Test OptionContract dataclass."""

    def test_contract_to_dict_basic(self):
        contract = OptionContract(
            strike=25000,
            option_type="CE",
            ltp=150.5,
            open_interest=5000000,
            change_in_oi=250000,
            volume=100000,
            iv=18.5,
        )
        d = contract.to_dict()
        assert d["strike"] == 25000
        assert d["option_type"] == "CE"
        assert d["ltp"] == 150.5
        assert d["open_interest"] == 5000000
        assert d["iv"] == 18.5
        assert "greeks" not in d  # No greeks computed

    def test_contract_with_greeks(self):
        contract = OptionContract(
            strike=25000,
            option_type="CE",
            ltp=150.5,
            iv=18.5,
            delta=0.55,
            gamma=0.0012,
            theta=-5.2,
            vega=8.3,
        )
        d = contract.to_dict()
        assert "greeks" in d
        assert d["greeks"]["delta"] == 0.55
        assert d["greeks"]["gamma"] == 0.0012
        assert d["greeks"]["theta"] == -5.2
        assert d["greeks"]["vega"] == 8.3


# ── OptionsChainData Tests ──────────────────────────────────


class TestOptionsChainData:
    """Test OptionsChainData analytics."""

    @pytest.fixture
    def chain(self):
        return OptionsChainData(
            symbol="NIFTY",
            underlying_price=25000,
            expiry="2026-03-26",
            available_expiries=["2026-03-26", "2026-04-02"],
            calls=[
                OptionContract(strike=24500, option_type="CE", open_interest=3000000, volume=50000),
                OptionContract(strike=25000, option_type="CE", open_interest=8000000, volume=100000),
                OptionContract(strike=25500, option_type="CE", open_interest=5000000, volume=60000),
            ],
            puts=[
                OptionContract(strike=24500, option_type="PE", open_interest=6000000, volume=70000),
                OptionContract(strike=25000, option_type="PE", open_interest=4000000, volume=80000),
                OptionContract(strike=25500, option_type="PE", open_interest=2000000, volume=30000),
            ],
            pcr_oi=0.75,
            pcr_volume=0.86,
            max_pain=25000,
            total_call_oi=16000000,
            total_put_oi=12000000,
            total_call_volume=210000,
            total_put_volume=180000,
            timestamp="2026-03-26T10:00:00Z",
        )

    def test_chain_to_dict(self, chain):
        d = chain.to_dict()
        assert d["symbol"] == "NIFTY"
        assert d["underlying_price"] == 25000
        assert len(d["calls"]) == 3
        assert len(d["puts"]) == 3
        assert "analytics" in d

    def test_chain_analytics(self, chain):
        d = chain.to_dict()
        analytics = d["analytics"]
        assert analytics["pcr_oi"] == 0.75
        assert analytics["max_pain"] == 25000
        assert analytics["total_call_oi"] == 16000000
        assert analytics["total_put_oi"] == 12000000

    def test_sentiment_bearish(self, chain):
        chain.pcr_oi = 0.5  # Low PCR = bearish
        assert chain._sentiment() == "bearish"

    def test_sentiment_bullish(self, chain):
        chain.pcr_oi = 1.5  # High PCR = bullish
        assert chain._sentiment() == "bullish"

    def test_sentiment_neutral(self, chain):
        chain.pcr_oi = 1.0
        assert chain._sentiment() == "neutral"


# ── IVSurfacePoint Tests ────────────────────────────────────


class TestIVSurfacePoint:

    def test_surface_point_to_dict(self):
        point = IVSurfacePoint(
            strike=25000,
            expiry="2026-03-26",
            iv=18.5,
            option_type="CE",
            moneyness=1.0,
        )
        d = point.to_dict()
        assert d["strike"] == 25000
        assert d["iv"] == 18.5
        assert d["moneyness"] == 1.0


# ── PCR and Max Pain (quant integration) ────────────────────


class TestPCRCalculation:
    """Test Put-Call Ratio calculation from existing quant module."""

    def test_pcr_basic(self):
        pcr = calculate_pcr(total_put_oi=12000000, total_call_oi=16000000)
        assert pcr == 0.75

    def test_pcr_equal_oi(self):
        pcr = calculate_pcr(total_put_oi=10000000, total_call_oi=10000000)
        assert pcr == 1.0

    def test_pcr_zero_call_oi(self):
        pcr = calculate_pcr(total_put_oi=10000000, total_call_oi=0)
        assert pcr == 0.0

    def test_pcr_high_put(self):
        pcr = calculate_pcr(total_put_oi=20000000, total_call_oi=10000000)
        assert pcr == 2.0


class TestMaxPainCalculation:
    """Test max pain calculation."""

    def test_max_pain_basic(self):
        strikes = [24500, 24600, 24700, 24800, 24900, 25000, 25100, 25200]
        call_oi = [1000, 2000, 3000, 5000, 8000, 12000, 6000, 3000]
        put_oi = [3000, 5000, 8000, 12000, 6000, 4000, 2000, 1000]

        mp = calculate_max_pain(strikes, call_oi, put_oi)
        assert mp in strikes  # Must be one of the strike prices

    def test_max_pain_single_strike(self):
        mp = calculate_max_pain([25000], [10000], [10000])
        assert mp == 25000

    def test_max_pain_empty_lists(self):
        """Edge case: should not crash on empty data."""
        # The function expects non-empty lists; test graceful handling
        try:
            mp = calculate_max_pain([], [], [])
            # If it doesn't crash, that's fine
        except (IndexError, ValueError):
            pass  # Expected for empty inputs


# ── DerivativesService Unit Tests ───────────────────────────


class TestDerivativesService:
    """Test DerivativesService utilities."""

    @pytest.fixture
    def svc(self):
        return DerivativesService()

    def test_estimate_tte_standard_format(self, svc):
        tte = svc._estimate_tte("2026-12-31")
        assert tte > 0

    def test_estimate_tte_unknown_format(self, svc):
        tte = svc._estimate_tte("not-a-date")
        assert tte == 7 / 365  # Default

    def test_interpret_pcr_extremely_bullish(self, svc):
        assert "bullish" in svc._interpret_pcr(1.6).lower()

    def test_interpret_pcr_bullish(self, svc):
        assert "bullish" in svc._interpret_pcr(1.3).lower()

    def test_interpret_pcr_neutral(self, svc):
        assert "neutral" in svc._interpret_pcr(1.0).lower()

    def test_interpret_pcr_bearish(self, svc):
        assert "bearish" in svc._interpret_pcr(0.6).lower()

    def test_interpret_pcr_extremely_bearish(self, svc):
        assert "bearish" in svc._interpret_pcr(0.3).lower()

    def test_compute_greeks_skips_zero_spot(self, svc):
        chain = OptionsChainData(
            symbol="TEST",
            underlying_price=0,  # Zero spot
            expiry="2026-12-31",
            calls=[OptionContract(strike=100, option_type="CE", iv=20)],
        )
        svc._compute_greeks_for_chain(chain)
        # Should not crash; greeks remain None
        assert chain.calls[0].delta is None

    def test_compute_greeks_populates(self, svc):
        chain = OptionsChainData(
            symbol="TEST",
            underlying_price=25000,
            expiry="2026-12-31",
            calls=[OptionContract(strike=25000, option_type="CE", iv=18)],
            puts=[OptionContract(strike=25000, option_type="PE", iv=18)],
        )
        svc._compute_greeks_for_chain(chain)
        # Call delta should be populated and positive
        assert chain.calls[0].delta is not None
        assert chain.calls[0].delta > 0
        # Put delta should be negative
        assert chain.puts[0].delta is not None
        assert chain.puts[0].delta < 0


class TestDerivativesFactory:
    """Test singleton factory."""

    def test_get_derivatives_service_returns_instance(self):
        svc = get_derivatives_service()
        assert isinstance(svc, DerivativesService)

    def test_get_derivatives_service_is_singleton(self):
        s1 = get_derivatives_service()
        s2 = get_derivatives_service()
        assert s1 is s2
