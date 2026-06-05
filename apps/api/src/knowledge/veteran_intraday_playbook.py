"""Veteran intraday playbook for NIFTY and BANKNIFTY scalps.

Shared by:
- LLM prompts for intraday analyst behavior
- Auto-trader time and event filters
- Intraday backtests comparing baseline vs disciplined execution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd


IST = ZoneInfo("Asia/Kolkata")
SCALP_SYMBOLS = {"NIFTY", "BANKNIFTY", "^NSEI", "^NSEBANK"}
MAJOR_EVENT_KEYWORDS = {
    "rbi", "repo", "policy", "cpi", "inflation", "wpi", "fed", "fomc",
    "budget", "gdp", "payroll", "nfp", "election", "war", "crude",
    "results", "guidance", "default", "downgrade",
}

VETERAN_INTRADAY_PLAYBOOK_PROMPT = """Veteran Intraday Playbook for NIFTY and BANKNIFTY scalps:
- Trade only liquid index setups with clean structure and defined invalidation.
- No trade in first 5 minutes after open; let the opening imbalance settle.
- Avoid fresh entries during lunch session when price discovery is weak.
- Stand aside on event-driven spike candles, abnormal volatility, or headline shocks.
- Prefer opening-range breakouts only when price, VWAP, and fast/slow trend align.
- Skip trades with weak follow-through, stretched candles, or poor reward relative to stop.
- The correct action is often WAIT. Protecting capital matters more than activity.
"""


@dataclass
class TradeGateDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": self.reasons,
            "metadata": self.metadata,
        }


def normalize_symbol(symbol: str) -> str:
    return symbol.upper().replace(".NS", "")


def is_veteran_scalp_symbol(symbol: str) -> bool:
    return normalize_symbol(symbol) in SCALP_SYMBOLS


def get_intraday_playbook_prompt(symbol: str) -> str:
    return VETERAN_INTRADAY_PLAYBOOK_PROMPT if is_veteran_scalp_symbol(symbol) else ""


def _as_ist(dt: datetime | str | None) -> datetime | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            parsed = datetime.fromisoformat(dt)
        except ValueError:
            return None
        return parsed.astimezone(IST) if parsed.tzinfo else parsed.replace(tzinfo=IST)
    return dt.astimezone(IST) if dt.tzinfo else dt.replace(tzinfo=IST)


def _recent_market_spike(alerts: Iterable[dict[str, Any]], now: datetime) -> bool:
    cutoff = now - timedelta(minutes=20)
    for alert in alerts:
        alert_time = _as_ist(alert.get("timestamp"))
        if alert_time is None or alert_time < cutoff:
            continue
        severity = str(alert.get("severity", "")).lower()
        alert_type = str(alert.get("type", "")).upper()
        if severity == "critical" or alert_type in {"TICK_SPIKE", "PRICE_MOVE"}:
            return True
    return False


def _recent_major_news(news_items: Iterable[Any], now: datetime) -> bool:
    cutoff = now - timedelta(minutes=45)
    for item in news_items:
        published = _as_ist(getattr(item, "published", None) or getattr(item, "timestamp", None))
        if published is None or published < cutoff:
            continue
        text = f"{getattr(item, 'title', '')} {getattr(item, 'summary', '')}".lower()
        if any(keyword in text for keyword in MAJOR_EVENT_KEYWORDS):
            return True
    return False


def evaluate_trade_gate(
    now: datetime | None = None,
    alerts: Iterable[dict[str, Any]] | None = None,
    news_items: Iterable[Any] | None = None,
) -> TradeGateDecision:
    current = _as_ist(now or datetime.now(IST)) or datetime.now(IST)
    reasons: list[str] = []

    if current.weekday() > 4:
        reasons.append("market closed")

    market_open = current.replace(hour=9, minute=15, second=0, microsecond=0)
    first_five_end = current.replace(hour=9, minute=20, second=0, microsecond=0)
    lunch_start = current.replace(hour=12, minute=0, second=0, microsecond=0)
    lunch_end = current.replace(hour=13, minute=15, second=0, microsecond=0)
    last_entry = current.replace(hour=15, minute=0, second=0, microsecond=0)

    if market_open <= current < first_five_end:
        reasons.append("opening imbalance window")
    if lunch_start <= current < lunch_end:
        reasons.append("lunch-time chop window")
    if current >= last_entry:
        reasons.append("late-session no-entry window")
    if alerts and _recent_market_spike(alerts, current):
        reasons.append("recent market spike detected")
    if news_items and _recent_major_news(news_items, current):
        reasons.append("major event headline risk")

    return TradeGateDecision(
        allowed=not reasons,
        reasons=reasons,
        metadata={
            "checked_at": current.isoformat(),
            "alerts_checked": len(list(alerts or [])),
            "news_checked": len(list(news_items or [])),
        },
    )


def _ensure_intraday_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    if frame.empty:
        return frame
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.dropna(subset=["Open", "High", "Low", "Close", "Volume"], how="any")
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize(IST)
    else:
        frame.index = frame.index.tz_convert(IST)
    return frame


def _build_intraday_signals(df: pd.DataFrame, strict: bool) -> list[int]:
    frame = _ensure_intraday_frame(df)
    if frame.empty or len(frame) < 30:
        return [0] * len(df)

    close = frame["Close"]
    high = frame["High"]
    low = frame["Low"]
    volume = frame["Volume"].replace(0, 1)

    ema_fast = close.ewm(span=9, adjust=False).mean()
    ema_slow = close.ewm(span=21, adjust=False).mean()
    typical_price = (high + low + close) / 3
    vwap = (typical_price * volume).cumsum() / volume.cumsum()
    bar_return_pct = close.pct_change().fillna(0) * 100
    bar_range_pct = ((high - low) / close.replace(0, pd.NA)).fillna(0) * 100
    rolling_volume = volume.rolling(20, min_periods=5).median().bfill().fillna(volume)

    opening_range_high = float(high.iloc[:3].max())
    opening_range_low = float(low.iloc[:3].min())

    signals: list[int] = []
    for idx, price in close.items():
        current_time = idx.astimezone(IST).time()
        if current_time < datetime.strptime("09:20", "%H:%M").time():
            signals.append(0)
            continue
        if current_time >= datetime.strptime("15:00", "%H:%M").time():
            signals.append(0)
            continue
        if strict and datetime.strptime("12:00", "%H:%M").time() <= current_time < datetime.strptime("13:15", "%H:%M").time():
            signals.append(0)
            continue

        row = frame.loc[idx]
        if strict:
            if abs(float(bar_return_pct.loc[idx])) > 0.45:
                signals.append(0)
                continue
            if float(bar_range_pct.loc[idx]) > 0.7:
                signals.append(0)
                continue
            if float(row["Volume"]) > float(rolling_volume.loc[idx]) * 2.5:
                signals.append(0)
                continue

        bullish_break = (
            price > opening_range_high
            and ema_fast.loc[idx] > ema_slow.loc[idx]
            and price > vwap.loc[idx]
        )
        bearish_break = (
            price < opening_range_low
            and ema_fast.loc[idx] < ema_slow.loc[idx]
            and price < vwap.loc[idx]
        )

        if strict:
            bullish_break = bullish_break and abs(float(price - vwap.loc[idx]) / max(float(price), 1.0)) < 0.008
            bearish_break = bearish_break and abs(float(price - vwap.loc[idx]) / max(float(price), 1.0)) < 0.008

        if bullish_break:
            signals.append(1)
        elif bearish_break:
            signals.append(-1)
        else:
            signals.append(0)

    return signals


def baseline_intraday_orb_strategy(df: pd.DataFrame) -> list[int]:
    return _build_intraday_signals(df, strict=False)


def veteran_intraday_orb_strategy(df: pd.DataFrame) -> list[int]:
    return _build_intraday_signals(df, strict=True)