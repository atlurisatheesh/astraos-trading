# type: ignore
"""AstraOS Services — Earnings Calendar & Reaction Predictor.

Tracks upcoming earnings dates for watchlist stocks and predicts
post-earnings price reactions using historical earnings surprises.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger()


@dataclass
class EarningsEvent:
    """An upcoming or past earnings event."""
    symbol: str
    name: str
    date: str
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    surprise_pct: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_actual: Optional[float] = None
    is_upcoming: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "date": self.date,
            "eps_estimate": self.eps_estimate,
            "eps_actual": self.eps_actual,
            "surprise_pct": self.surprise_pct,
            "revenue_estimate": self.revenue_estimate,
            "revenue_actual": self.revenue_actual,
            "is_upcoming": self.is_upcoming,
        }


@dataclass
class EarningsReaction:
    """Historical earnings reaction analysis."""
    symbol: str
    avg_post_earnings_move: float  # avg % move day after earnings
    positive_surprise_avg: float
    negative_surprise_avg: float
    beat_rate: float  # % of times company beat estimates
    last_4_reactions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "avg_post_earnings_move": round(self.avg_post_earnings_move, 2),
            "positive_surprise_avg_move": round(self.positive_surprise_avg, 2),
            "negative_surprise_avg_move": round(self.negative_surprise_avg, 2),
            "beat_rate_pct": round(self.beat_rate, 1),
            "prediction": self._predict(),
            "last_4_reactions": self.last_4_reactions,
        }

    def _predict(self) -> str:
        if self.beat_rate > 70 and self.positive_surprise_avg > 2:
            return "Likely BULLISH — stock consistently beats and rallies"
        elif self.beat_rate < 40:
            return "Likely BEARISH — stock frequently misses estimates"
        return "NEUTRAL — mixed reaction history"


NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "AXISBANK",
    "BAJFINANCE", "ASIANPAINT", "MARUTI", "TATAMOTORS", "SUNPHARMA",
    "HCLTECH", "WIPRO", "ULTRACEMCO", "TITAN", "NESTLEIND",
]


class EarningsCalendarService:
    """Track earnings dates and predict post-earnings reactions."""

    async def get_upcoming_earnings(self, symbols: Optional[list[str]] = None, days: int = 30) -> list[EarningsEvent]:
        """Get upcoming earnings for given symbols."""
        if symbols is None:
            symbols = NIFTY_50
        events: list[EarningsEvent] = []

        for symbol in symbols[:30]:  # Cap at 30 to avoid rate limits
            try:
                yf_sym = f"{symbol}.NS"
                t = yf.Ticker(yf_sym)
                cal = t.calendar
                info = t.info
                name = info.get("longName", info.get("shortName", symbol))

                if cal is not None and not (isinstance(cal, pd.DataFrame) and cal.empty):
                    if isinstance(cal, dict):
                        ed = cal.get("Earnings Date")
                        if ed:
                            date_str = str(ed[0]) if isinstance(ed, list) else str(ed)
                            events.append(EarningsEvent(
                                symbol=symbol, name=name, date=date_str,
                                eps_estimate=cal.get("Earnings Average"),
                                revenue_estimate=cal.get("Revenue Average"),
                            ))
                    elif isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.index:
                        date_val = cal.loc["Earnings Date"].iloc[0]
                        events.append(EarningsEvent(
                            symbol=symbol, name=name, date=str(date_val),
                        ))
            except Exception as e:
                logger.debug("Earnings fetch failed", symbol=symbol, error=str(e))

        events.sort(key=lambda e: e.date)
        return events

    async def get_earnings_reaction(self, symbol: str) -> EarningsReaction:
        """Analyze historical post-earnings price reactions."""
        yf_sym = f"{symbol}.NS"
        t = yf.Ticker(yf_sym)

        # Get earnings history
        earnings = t.earnings_dates
        info = t.info
        reactions: list[dict[str, Any]] = []
        moves: list[float] = []
        pos_moves: list[float] = []
        neg_moves: list[float] = []
        beats = 0
        total = 0

        if earnings is not None and not earnings.empty:
            df = yf.download(yf_sym, period="2y", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            for idx, row in list(earnings.iterrows())[:8]:
                try:
                    date = pd.Timestamp(idx).tz_localize(None) if pd.Timestamp(idx).tz else pd.Timestamp(idx)
                    est = row.get("EPS Estimate")
                    actual = row.get("Reported EPS")
                    surprise = row.get("Surprise(%)")

                    # Find price move after this date
                    mask = df.index >= date
                    post = df[mask]
                    if len(post) >= 2:
                        move_pct = float((post["Close"].iloc[1] / post["Close"].iloc[0] - 1) * 100)
                    else:
                        move_pct = 0.0

                    total += 1
                    moves.append(abs(move_pct))

                    is_beat = False
                    if est is not None and actual is not None and not pd.isna(est) and not pd.isna(actual):
                        is_beat = float(actual) >= float(est)
                        if is_beat:
                            beats += 1
                            pos_moves.append(move_pct)
                        else:
                            neg_moves.append(move_pct)

                    reactions.append({
                        "date": str(date.date()),
                        "eps_estimate": float(est) if est and not pd.isna(est) else None,
                        "eps_actual": float(actual) if actual and not pd.isna(actual) else None,
                        "surprise_pct": float(surprise) if surprise and not pd.isna(surprise) else None,
                        "price_move_pct": round(move_pct, 2),
                        "beat": is_beat,
                    })
                except Exception:
                    continue

        return EarningsReaction(
            symbol=symbol,
            avg_post_earnings_move=sum(moves) / len(moves) if moves else 0,
            positive_surprise_avg=sum(pos_moves) / len(pos_moves) if pos_moves else 0,
            negative_surprise_avg=sum(neg_moves) / len(neg_moves) if neg_moves else 0,
            beat_rate=(beats / total * 100) if total > 0 else 0,
            last_4_reactions=reactions[:4],
        )


_service: Optional[EarningsCalendarService] = None

def get_earnings_service() -> EarningsCalendarService:
    global _service
    if _service is None:
        _service = EarningsCalendarService()
    return _service
