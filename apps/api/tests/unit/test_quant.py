"""AstraOS Tests — Integration tests for quant modules and services."""

import pytest
from decimal import Decimal

from src.quant.options_pricer import black_scholes, calculate_max_pain, calculate_pcr
from src.quant.regime_detector import RegimeDetector, PositionSizer
from src.services.order_fsm import OrderStateMachine, OrderState


class TestOptionsPricer:
    """Black-Scholes, max pain, and PCR tests."""

    def test_call_option_price(self):
        """Call option has positive delta and positive price."""
        result = black_scholes(
            spot=24500, strike=24500, time_to_expiry=7/365,
            risk_free_rate=0.065, volatility=0.13, option_type="CE",
        )
        assert result.price > 0
        assert 0.4 < result.delta < 0.6  # ATM call delta ~0.5
        assert result.gamma > 0
        assert result.theta < 0  # Time decay is negative
        assert result.vega > 0

    def test_put_option_price(self):
        """Put option has negative delta."""
        result = black_scholes(
            spot=24500, strike=24500, time_to_expiry=7/365,
            risk_free_rate=0.065, volatility=0.13, option_type="PE",
        )
        assert result.price > 0
        assert -0.6 < result.delta < -0.4  # ATM put delta ~-0.5

    def test_deep_itm_call(self):
        """Deep ITM call has delta close to 1."""
        result = black_scholes(
            spot=25000, strike=24000, time_to_expiry=30/365,
            risk_free_rate=0.065, volatility=0.15, option_type="CE",
        )
        assert result.delta > 0.85  # Deep ITM
        assert result.price > 900

    def test_expired_option(self):
        """Expired option returns intrinsic value."""
        result = black_scholes(
            spot=25000, strike=24500, time_to_expiry=0,
            risk_free_rate=0.065, volatility=0.15, option_type="CE",
        )
        assert result.price == 500  # intrinsic = 25000 - 24500

    def test_max_pain(self):
        """Max pain finds the lowest pain strike."""
        strikes = [24300, 24400, 24500, 24600, 24700]
        call_oi = [100, 200, 500, 300, 100]
        put_oi = [80, 150, 400, 250, 120]
        mp = calculate_max_pain(strikes, call_oi, put_oi)
        assert mp in strikes

    def test_pcr(self):
        """PCR calculation is correct."""
        assert calculate_pcr(150000, 100000) == 1.5
        assert calculate_pcr(100000, 100000) == 1.0
        assert calculate_pcr(0, 100000) == 0.0
        assert calculate_pcr(100000, 0) == 0.0  # Divide by zero handled


class TestPositionSizer:
    """Kelly Criterion position sizing."""

    def test_positive_edge(self):
        """Strategy with positive edge gives positive allocation."""
        sizer = PositionSizer()
        result = sizer.calculate(win_rate=0.6, avg_win=2000, avg_loss=1000, capital=1000000)
        assert result["pct_of_capital"] > 0
        assert result["amount"] > 0

    def test_no_edge(self):
        """Strategy with no edge gives zero allocation."""
        sizer = PositionSizer()
        result = sizer.calculate(win_rate=0.3, avg_win=1000, avg_loss=1000, capital=1000000)
        assert result["pct_of_capital"] == 0

    def test_max_cap(self):
        """Never exceeds max position percentage."""
        sizer = PositionSizer()
        result = sizer.calculate(win_rate=0.9, avg_win=5000, avg_loss=100, capital=1000000, max_position_pct=5.0)
        assert result["pct_of_capital"] <= 5.0


class TestOrderStateMachine:
    """Order FSM state transitions."""

    def test_happy_path_semi_auto(self):
        """DRAFT → RISK → HUMAN → BROKER → FILLED."""
        fsm = OrderStateMachine("order-1")
        assert fsm.state == OrderState.DRAFT

        fsm.submit()
        assert fsm.state == OrderState.RISK_PENDING

        fsm.risk_approve()
        assert fsm.state == OrderState.RISK_APPROVED

        fsm.request_human_approval()
        assert fsm.state == OrderState.HUMAN_PENDING

        fsm.human_approve()
        assert fsm.state == OrderState.HUMAN_APPROVED

        fsm.send_to_broker()
        assert fsm.state == OrderState.SENT

        fsm.fill()
        assert fsm.state == OrderState.FILLED
        assert fsm.is_terminal
        assert len(fsm.history) == 6

    def test_happy_path_full_auto(self):
        """DRAFT → RISK → BROKER → FILLED (skip human approval)."""
        fsm = OrderStateMachine("order-2")
        fsm.submit()
        fsm.risk_approve()
        fsm.send_to_broker()  # Direct to broker in auto mode
        fsm.fill()
        assert fsm.state == OrderState.FILLED

    def test_risk_rejection(self):
        """DRAFT → RISK_PENDING → RISK_REJECTED (terminal)."""
        fsm = OrderStateMachine("order-3")
        fsm.submit()
        fsm.risk_reject("Position too large")
        assert fsm.state == OrderState.RISK_REJECTED
        assert fsm.is_terminal

    def test_invalid_transition(self):
        """Invalid transitions raise ValueError."""
        fsm = OrderStateMachine("order-4")
        with pytest.raises(ValueError):
            fsm.fill()  # Can't fill from DRAFT

    def test_cancel(self):
        """Can cancel from cancellable states."""
        fsm = OrderStateMachine("order-5")
        fsm.submit()
        fsm.risk_approve()
        fsm.request_human_approval()
        fsm.cancel("Changed my mind")
        assert fsm.state == OrderState.CANCELLED
        assert fsm.is_terminal
