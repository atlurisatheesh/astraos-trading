"""AstraOS Tests — WebSocket, FinBERT, NSE/BSE, and F&O Calendar tests."""

import pytest
from datetime import date, timedelta

from src.services.nse_bse_feed import FOCalendar
from src.nlp.finbert import FinBERTAnalyzer
from src.services.order_fsm import OrderStateMachine, OrderState


class TestFOCalendar:
    """F&O lot sizes and expiry calendar."""

    def test_lot_size_nifty(self):
        assert FOCalendar.get_lot_size("NIFTY") == 25

    def test_lot_size_banknifty(self):
        assert FOCalendar.get_lot_size("BANKNIFTY") == 15

    def test_lot_size_reliance(self):
        assert FOCalendar.get_lot_size("RELIANCE") == 250

    def test_lot_size_unknown_returns_1(self):
        assert FOCalendar.get_lot_size("UNKNOWN_XYZ") == 1

    def test_next_expiry_is_thursday(self):
        exp = FOCalendar.get_next_expiry()
        assert exp.weekday() == 3  # Thursday

    def test_next_expiry_is_future(self):
        exp = FOCalendar.get_next_expiry()
        assert exp >= date.today()

    def test_monthly_expiry_is_thursday(self):
        exp = FOCalendar.get_monthly_expiry(2026, 3)
        assert exp.weekday() == 3

    def test_expiry_calendar_has_entries(self):
        cal = FOCalendar.get_expiry_calendar(months_ahead=2)
        assert len(cal) > 0
        for entry in cal:
            assert "date" in entry
            assert "type" in entry
            assert entry["type"] in {"weekly", "monthly"}


class TestFinBERTFallback:
    """FinBERT keyword fallback (runs without torch installed)."""

    @pytest.fixture
    def analyzer(self):
        return FinBERTAnalyzer()

    def test_bullish_text(self, analyzer):
        result = analyzer._keyword_fallback("Stock market rally continues, record gains for investors")
        assert result.label == "positive"
        assert result.positive > result.negative

    def test_bearish_text(self, analyzer):
        result = analyzer._keyword_fallback("Market crash fears grow as stocks decline sharply")
        assert result.label == "negative"
        assert result.negative > result.positive

    def test_neutral_text(self, analyzer):
        result = analyzer._keyword_fallback("The weather is nice today in Mumbai")
        assert result.label == "neutral"

    def test_result_to_dict(self, analyzer):
        result = analyzer._keyword_fallback("Strong growth expected in IT sector")
        d = result.to_dict()
        assert "label" in d
        assert "score" in d
        assert "positive" in d
        assert "negative" in d
        assert "neutral" in d

    def test_mixed_text(self, analyzer):
        result = analyzer._keyword_fallback("Despite profit warning, bullish growth rally expected")
        d = result.to_dict()
        assert d["positive"] + d["negative"] + d["neutral"] <= 1.01  # Within rounding


class TestWebSocketManager:
    """ConnectionManager unit tests."""

    def test_websocket_stats_empty(self):
        from src.routers.websocket import ConnectionManager
        mgr = ConnectionManager()
        assert mgr.stats == {}

    def test_websocket_stats_property(self):
        from src.routers.websocket import ConnectionManager
        mgr = ConnectionManager()
        assert isinstance(mgr.stats, dict)
