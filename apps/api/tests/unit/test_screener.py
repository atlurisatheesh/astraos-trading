"""AstraOS Tests — Phase 8: Advanced Stock Screener Tests."""

import pytest

from src.services.screener_engine import (
    ScreenerFilter,
    ScreenerQuery,
    ScreenerResult,
    ScreenerEngine,
    NIFTY_50_SYMBOLS,
    ALL_FIELDS,
    VALID_OPERATORS,
    get_screener_engine,
)


# ── ScreenerFilter Tests ────────────────────────────────────


class TestScreenerFilter:
    """Test individual filter validation."""

    def test_valid_filter(self):
        f = ScreenerFilter(field="trailing_pe", op="<", value=20)
        assert f.validate() is None

    def test_invalid_field(self):
        f = ScreenerFilter(field="unknown_field", op=">", value=10)
        err = f.validate()
        assert "Unknown field" in err

    def test_invalid_operator(self):
        f = ScreenerFilter(field="trailing_pe", op="LIKE", value=10)
        err = f.validate()
        assert "Invalid operator" in err

    def test_all_operators_valid(self):
        for op in VALID_OPERATORS:
            f = ScreenerFilter(field="market_cap", op=op, value=100)
            assert f.validate() is None


# ── ScreenerQuery Tests ─────────────────────────────────────


class TestScreenerQuery:
    """Test query construction and validation."""

    def test_from_dict(self):
        data = {
            "filters": [
                {"field": "market_cap", "op": ">", "value": 100000},
                {"field": "trailing_pe", "op": "<", "value": 20},
            ],
            "logic": "AND",
            "sort_by": "market_cap",
            "sort_order": "desc",
            "limit": 50,
        }
        q = ScreenerQuery.from_dict(data)
        assert len(q.filters) == 2
        assert q.logic == "AND"
        assert q.sort_by == "market_cap"
        assert q.limit == 50

    def test_from_dict_defaults(self):
        data = {"filters": [{"field": "trailing_pe", "op": "<", "value": 20}]}
        q = ScreenerQuery.from_dict(data)
        assert q.logic == "AND"
        assert q.sort_by == "market_cap"
        assert q.sort_order == "desc"
        assert q.limit == 50

    def test_from_dict_limit_capped(self):
        data = {"filters": [{"field": "trailing_pe", "op": "<", "value": 20}], "limit": 500}
        q = ScreenerQuery.from_dict(data)
        assert q.limit == 200

    def test_validate_valid_query(self):
        q = ScreenerQuery(
            filters=[ScreenerFilter("market_cap", ">", 100000)],
            logic="AND",
        )
        assert q.validate() == []

    def test_validate_invalid_logic(self):
        q = ScreenerQuery(
            filters=[ScreenerFilter("market_cap", ">", 100000)],
            logic="XOR",
        )
        errors = q.validate()
        assert any("Invalid logic" in e for e in errors)

    def test_validate_invalid_filter(self):
        q = ScreenerQuery(
            filters=[ScreenerFilter("bad_field", ">", 100)],
            logic="AND",
        )
        errors = q.validate()
        assert len(errors) > 0


# ── ScreenerResult Tests ────────────────────────────────────


class TestScreenerResult:
    """Test result serialization."""

    def test_to_dict(self):
        r = ScreenerResult(
            symbol="RELIANCE",
            name="Reliance Industries",
            sector="Energy",
            industry="Oil & Gas",
            data={"trailing_pe": 28.5, "market_cap": 18000000000000},
        )
        d = r.to_dict()
        assert d["symbol"] == "RELIANCE"
        assert d["trailing_pe"] == 28.5
        assert d["market_cap"] == 18000000000000

    def test_to_dict_empty_data(self):
        r = ScreenerResult(symbol="TEST")
        d = r.to_dict()
        assert d["symbol"] == "TEST"
        assert d["name"] == ""


# ── ScreenerEngine Filter Logic Tests ───────────────────────


class TestScreenerEngineFilterLogic:
    """Test the filter comparison engine with a mock dataset."""

    @pytest.fixture
    def engine(self):
        return ScreenerEngine()

    def test_compare_greater_than(self, engine):
        assert engine._compare(25, ">", 20) is True
        assert engine._compare(15, ">", 20) is False

    def test_compare_less_than(self, engine):
        assert engine._compare(15, "<", 20) is True
        assert engine._compare(25, "<", 20) is False

    def test_compare_equals(self, engine):
        assert engine._compare(20, "==", 20) is True
        assert engine._compare(15, "==", 20) is False

    def test_compare_not_equals(self, engine):
        assert engine._compare(15, "!=", 20) is True
        assert engine._compare(20, "!=", 20) is False

    def test_compare_gte(self, engine):
        assert engine._compare(20, ">=", 20) is True
        assert engine._compare(21, ">=", 20) is True
        assert engine._compare(19, ">=", 20) is False

    def test_compare_lte(self, engine):
        assert engine._compare(20, "<=", 20) is True
        assert engine._compare(19, "<=", 20) is True
        assert engine._compare(21, "<=", 20) is False

    def test_matches_filters_and_logic(self, engine):
        data = {"trailing_pe": 15, "market_cap": 200000}
        query = ScreenerQuery(
            filters=[
                ScreenerFilter("trailing_pe", "<", 20),
                ScreenerFilter("market_cap", ">", 100000),
            ],
            logic="AND",
        )
        assert engine._matches_filters(data, query) is True

    def test_matches_filters_and_logic_fails(self, engine):
        data = {"trailing_pe": 25, "market_cap": 200000}
        query = ScreenerQuery(
            filters=[
                ScreenerFilter("trailing_pe", "<", 20),
                ScreenerFilter("market_cap", ">", 100000),
            ],
            logic="AND",
        )
        assert engine._matches_filters(data, query) is False

    def test_matches_filters_or_logic(self, engine):
        data = {"trailing_pe": 25, "market_cap": 200000}
        query = ScreenerQuery(
            filters=[
                ScreenerFilter("trailing_pe", "<", 20),  # Fails
                ScreenerFilter("market_cap", ">", 100000),  # Passes
            ],
            logic="OR",
        )
        assert engine._matches_filters(data, query) is True

    def test_matches_filters_or_logic_all_fail(self, engine):
        data = {"trailing_pe": 25, "market_cap": 50000}
        query = ScreenerQuery(
            filters=[
                ScreenerFilter("trailing_pe", "<", 20),
                ScreenerFilter("market_cap", ">", 100000),
            ],
            logic="OR",
        )
        assert engine._matches_filters(data, query) is False

    def test_matches_filters_missing_field(self, engine):
        data = {"market_cap": 200000}  # No trailing_pe
        query = ScreenerQuery(
            filters=[ScreenerFilter("trailing_pe", "<", 20)],
            logic="AND",
        )
        # Missing field should fail
        assert engine._matches_filters(data, query) is False


# ── Constants Tests ─────────────────────────────────────────


class TestScreenerConstants:
    """Test screener constants are properly defined."""

    def test_nifty50_has_expected_count(self):
        assert len(NIFTY_50_SYMBOLS) >= 49

    def test_known_symbols_in_nifty50(self):
        assert "RELIANCE" in NIFTY_50_SYMBOLS
        assert "TCS" in NIFTY_50_SYMBOLS
        assert "HDFCBANK" in NIFTY_50_SYMBOLS

    def test_all_fields_has_expected_entries(self):
        assert "trailing_pe" in ALL_FIELDS
        assert "rsi_14" in ALL_FIELDS
        assert "market_cap" in ALL_FIELDS
        assert "sma_200" in ALL_FIELDS

    def test_valid_operators(self):
        assert ">" in VALID_OPERATORS
        assert "<" in VALID_OPERATORS
        assert "==" in VALID_OPERATORS


class TestScreenerFactory:
    """Test singleton factory."""

    def test_get_screener_engine_returns_instance(self):
        engine = get_screener_engine()
        assert isinstance(engine, ScreenerEngine)

    def test_get_screener_engine_is_singleton(self):
        e1 = get_screener_engine()
        e2 = get_screener_engine()
        assert e1 is e2
