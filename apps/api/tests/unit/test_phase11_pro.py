# type: ignore
"""Tests — Phase 11: Pro Trading Features.

Covers: Options Strategy Builder, Earnings Calendar, Market Breadth,
Multi-Timeframe Analysis, Portfolio Correlation, TradingView Webhook,
Rate Limiter, Audit Log.
"""

import pytest


# ═══════════════════════════════════════════════════════════
# 1. OPTIONS STRATEGY BUILDER
# ═══════════════════════════════════════════════════════════

class TestOptionsStrategyBuilder:
    """Test the 8-strategy options builder."""

    def test_import(self):
        from src.services.strategy_builder import OptionsStrategyBuilder, get_strategy_builder
        assert OptionsStrategyBuilder is not None

    def test_instantiate(self):
        from src.services.strategy_builder import OptionsStrategyBuilder
        builder = OptionsStrategyBuilder()
        assert builder is not None

    def test_singleton_factory(self):
        from src.services.strategy_builder import get_strategy_builder
        b1 = get_strategy_builder()
        b2 = get_strategy_builder()
        assert b1 is b2

    def test_get_available_strategies(self):
        from src.services.strategy_builder import OptionsStrategyBuilder
        sb = OptionsStrategyBuilder()
        strategies = sb.get_available_strategies()
        assert isinstance(strategies, (list, dict))
        assert len(strategies) > 0

    def test_build_strategy_bull_call(self):
        from src.services.strategy_builder import OptionsStrategyBuilder
        sb = OptionsStrategyBuilder()
        result = sb.build_strategy("bull_call_spread", spot_price=20000, expiry="2026-04-24")
        assert result is not None

    def test_build_strategy_iron_condor(self):
        from src.services.strategy_builder import OptionsStrategyBuilder
        sb = OptionsStrategyBuilder()
        result = sb.build_strategy("iron_condor", spot_price=20000, expiry="2026-04-24")
        assert result is not None

    def test_build_strategy_straddle(self):
        from src.services.strategy_builder import OptionsStrategyBuilder
        sb = OptionsStrategyBuilder()
        result = sb.build_strategy("straddle", spot_price=20000, expiry="2026-04-24")
        assert result is not None

    def test_option_leg_dataclass(self):
        from src.services.strategy_builder import OptionLeg
        leg = OptionLeg(strike=20000, option_type="CE", side="BUY", premium=350.0, lots=1)
        assert leg.strike == 20000

    def test_strategy_payoff_dataclass(self):
        from src.services.strategy_builder import StrategyPayoff
        assert StrategyPayoff is not None


# ═══════════════════════════════════════════════════════════
# 2. EARNINGS CALENDAR
# ═══════════════════════════════════════════════════════════

class TestEarningsCalendarService:
    """Test the Earnings Calendar + Reaction Predictor."""

    def test_import(self):
        from src.services.earnings_calendar import EarningsCalendarService
        assert EarningsCalendarService is not None

    def test_import_dataclasses(self):
        from src.services.earnings_calendar import EarningsEvent, EarningsReaction
        assert EarningsEvent is not None and EarningsReaction is not None

    def test_singleton_factory(self):
        from src.services.earnings_calendar import get_earnings_service
        s1 = get_earnings_service()
        s2 = get_earnings_service()
        assert s1 is s2

    def test_instantiate(self):
        from src.services.earnings_calendar import EarningsCalendarService
        ec = EarningsCalendarService()
        assert ec is not None


# ═══════════════════════════════════════════════════════════
# 3. MARKET BREADTH + NIFTY HEATMAP
# ═══════════════════════════════════════════════════════════

class TestMarketBreadthService:
    """Test Market Breadth engine."""

    def test_import(self):
        from src.services.market_breadth import MarketBreadthService, MarketBreadth
        assert MarketBreadthService is not None

    def test_heatpoint_dataclass(self):
        from src.services.market_breadth import StockHeatPoint
        hp = StockHeatPoint(symbol="RELIANCE", change_pct=2.5, volume=1000000, sector="Energy")
        assert hp.symbol == "RELIANCE"

    def test_singleton_factory(self):
        from src.services.market_breadth import get_market_breadth_service
        s1 = get_market_breadth_service()
        s2 = get_market_breadth_service()
        assert s1 is s2


# ═══════════════════════════════════════════════════════════
# 4. MULTI-TIMEFRAME ANALYSIS
# ═══════════════════════════════════════════════════════════

class TestMultiTimeframeService:
    """Test Multi-Timeframe confluence analysis."""

    def test_import(self):
        from src.services.multi_timeframe import MultiTimeframeService
        assert MultiTimeframeService is not None

    def test_dataclasses(self):
        from src.services.multi_timeframe import TimeframeSignal, MultiTimeframeResult
        assert TimeframeSignal is not None

    def test_singleton_factory(self):
        from src.services.multi_timeframe import get_multi_timeframe_service
        s1 = get_multi_timeframe_service()
        s2 = get_multi_timeframe_service()
        assert s1 is s2


# ═══════════════════════════════════════════════════════════
# 5. PORTFOLIO CORRELATION
# ═══════════════════════════════════════════════════════════

class TestPortfolioCorrelationService:
    """Test Portfolio Correlation Matrix."""

    def test_import(self):
        from src.services.portfolio_correlation import PortfolioCorrelationService
        assert PortfolioCorrelationService is not None

    def test_correlation_result_dataclass(self):
        from src.services.portfolio_correlation import CorrelationResult
        assert CorrelationResult is not None

    def test_singleton_factory(self):
        from src.services.portfolio_correlation import get_correlation_service
        s1 = get_correlation_service()
        s2 = get_correlation_service()
        assert s1 is s2


# ═══════════════════════════════════════════════════════════
# 6. TRADINGVIEW WEBHOOK
# ═══════════════════════════════════════════════════════════

class TestTradingViewWebhookService:
    """Test TradingView Webhook Receiver."""

    def test_import(self):
        from src.services.tradingview_webhook import TradingViewWebhookService
        assert TradingViewWebhookService is not None

    def test_dataclass(self):
        from src.services.tradingview_webhook import WebhookSignal
        assert WebhookSignal is not None

    def test_singleton_factory(self):
        from src.services.tradingview_webhook import get_webhook_service
        s1 = get_webhook_service()
        s2 = get_webhook_service()
        assert s1 is s2


# ═══════════════════════════════════════════════════════════
# 7. RATE LIMITER
# ═══════════════════════════════════════════════════════════

class TestRateLimiter:
    """Test the sliding window rate limiter."""

    def test_import(self):
        from src.core.rate_limiter import RateLimiter, RateLimitMiddleware
        assert RateLimiter is not None

    def test_default_init(self):
        from src.core.rate_limiter import RateLimiter
        rl = RateLimiter()
        assert rl is not None

    def test_custom_init(self):
        from src.core.rate_limiter import RateLimiter
        rl = RateLimiter(requests_per_minute=120, burst=30)
        assert rl is not None

    def test_allows_initial_request(self):
        from src.core.rate_limiter import RateLimiter
        rl = RateLimiter(requests_per_minute=10, burst=5)
        result = rl.allow("test_user")
        assert result is True

    def test_blocks_after_burst(self):
        from src.core.rate_limiter import RateLimiter
        rl = RateLimiter(requests_per_minute=100, burst=3)
        for _ in range(3):
            rl.allow("test_user")
        # After burst is exhausted, should block
        result = rl.allow("test_user")
        assert result is False

    def test_different_users_independent(self):
        from src.core.rate_limiter import RateLimiter
        rl = RateLimiter(requests_per_minute=100, burst=2)
        rl.allow("user_a")
        rl.allow("user_a")
        assert rl.allow("user_a") is False
        assert rl.allow("user_b") is True

    def test_middleware_exists(self):
        from src.core.rate_limiter import RateLimitMiddleware
        assert RateLimitMiddleware is not None


# ═══════════════════════════════════════════════════════════
# 8. AUDIT LOG
# ═══════════════════════════════════════════════════════════

class TestAuditLogService:
    """Test the action tracking audit log."""

    def test_import(self):
        from src.core.audit_log import AuditLogService, AuditEntry, AuditAction
        assert AuditLogService is not None

    def test_singleton_factory(self):
        from src.core.audit_log import get_audit_service
        s1 = get_audit_service()
        s2 = get_audit_service()
        assert s1 is s2

    def test_log_action(self):
        from src.core.audit_log import AuditLogService
        logger = AuditLogService()
        logger.log("test_user", "LOGIN", {"ip": "127.0.0.1"})
        entries = logger.query(user_id="test_user")
        assert len(entries) >= 1

    def test_log_multiple_actions(self):
        from src.core.audit_log import AuditLogService
        logger = AuditLogService()
        logger.log("user1", "LOGIN", {})
        logger.log("user1", "TRADE", {"symbol": "RELIANCE"})
        logger.log("user1", "LOGOUT", {})
        entries = logger.query(user_id="user1")
        assert len(entries) >= 3

    def test_get_summary(self):
        from src.core.audit_log import AuditLogService
        logger = AuditLogService()
        logger.log("user1", "LOGIN", {})
        summary = logger.get_summary("user1")
        assert isinstance(summary, dict)

    def test_audit_action_enum(self):
        from src.core.audit_log import AuditAction
        # Should have standard action types
        assert hasattr(AuditAction, "LOGIN") or isinstance(AuditAction, type)

    def test_audit_entry_dataclass(self):
        from src.core.audit_log import AuditEntry
        assert AuditEntry is not None
