from datetime import datetime

import pandas as pd
import pytest

from src.knowledge.veteran_intraday_playbook import (
    evaluate_trade_gate,
    get_intraday_playbook_prompt,
    is_veteran_scalp_symbol,
    veteran_intraday_orb_strategy,
)
from src.quant.backtester import compare_backtests


def _sample_intraday_frame(rows: int = 600) -> pd.DataFrame:
    index = pd.date_range("2026-02-02 09:15", periods=rows, freq="5min", tz="Asia/Kolkata")
    close = pd.Series([100 + i * 0.08 for i in range(rows)], index=index)
    frame = pd.DataFrame(
        {
            "Open": close - 0.05,
            "High": close + 0.25,
            "Low": close - 0.25,
            "Close": close,
            "Volume": [1000 + (i % 20) * 15 for i in range(rows)],
        },
        index=index,
    )
    return frame


def test_intraday_playbook_targets_only_index_scalps():
    assert is_veteran_scalp_symbol("NIFTY") is True
    assert is_veteran_scalp_symbol("BANKNIFTY") is True
    assert is_veteran_scalp_symbol("RELIANCE") is False
    assert "NIFTY and BANKNIFTY" in get_intraday_playbook_prompt("NIFTY")


def test_trade_gate_blocks_opening_lunch_and_major_news():
    opening_gate = evaluate_trade_gate(
        now=datetime(2026, 3, 27, 9, 17),
        alerts=[],
        news_items=[],
    )
    assert opening_gate.allowed is False
    assert "opening imbalance window" in opening_gate.reasons

    lunch_gate = evaluate_trade_gate(
        now=datetime(2026, 3, 27, 12, 20),
        alerts=[],
        news_items=[],
    )
    assert lunch_gate.allowed is False
    assert "lunch-time chop window" in lunch_gate.reasons

    class News:
        title = "RBI policy surprise shocks index market"
        summary = "Emergency liquidity and repo commentary"
        published = datetime(2026, 3, 27, 10, 0)

    news_gate = evaluate_trade_gate(
        now=datetime(2026, 3, 27, 10, 15),
        alerts=[],
        news_items=[News()],
    )
    assert news_gate.allowed is False
    assert "major event headline risk" in news_gate.reasons


def test_compare_backtests_reports_expectancy_and_drawdown_deltas():
    frame = _sample_intraday_frame()

    def baseline(df: pd.DataFrame) -> list[int]:
        return [1 if i % 3 == 0 else 0 for i in range(len(df))]

    comparison = compare_backtests(
        frame,
        baseline,
        veteran_intraday_orb_strategy,
        train_window=300,
        test_window=120,
        step=60,
    )

    assert "baseline" in comparison
    assert "filtered" in comparison
    assert "improvements" in comparison
    assert "expectancy_delta" in comparison["improvements"]
    assert "drawdown_delta" in comparison["improvements"]


@pytest.mark.asyncio
async def test_veteran_intraday_backtest_route(client, auth_headers, monkeypatch):
    from src.routers import backtest as backtest_router

    class DummyProvider:
        async def get_ohlcv(self, symbol: str, interval: str = "1d", period: str = "1y") -> pd.DataFrame:
            assert symbol == "BANKNIFTY"
            assert interval == "5m"
            return _sample_intraday_frame()

    monkeypatch.setattr(backtest_router, "get_market_data_provider", lambda: DummyProvider())

    response = await client.get(
        "/api/v1/backtest/BANKNIFTY?strategy=veteran_intraday_compare&period=60d",
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "veteran_intraday_compare"
    assert payload["interval"] == "5m"
    assert payload["playbook"] == "veteran_intraday_orb"
    assert "comparison" in payload
    assert "improvements" in payload["comparison"]