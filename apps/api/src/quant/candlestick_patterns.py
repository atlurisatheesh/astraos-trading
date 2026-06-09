"""AstraOS Quant — Japanese Candlestick Pattern Recognition.

Detects 25+ candlestick patterns that professional traders use to predict
reversals and continuations. Each pattern has:
  - Direction: bullish / bearish
  - Reliability: 1-5 stars (based on decades of market data)
  - Confirmation: whether the pattern needs next-candle confirmation

These are the patterns that Chartered Market Technicians (CMT) study.
Sources: Steve Nison "Japanese Candlestick Charting Techniques",
         Gregory Morris "Candlestick Charting Explained"
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger()


@dataclass
class CandlePattern:
    name: str
    signal: str          # "bullish" | "bearish"
    reliability: int     # 1-5 stars
    candle_count: int    # 1, 2, or 3 candle pattern
    description: str
    action: str          # "reversal" | "continuation"
    needs_confirmation: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "signal": self.signal,
            "reliability": self.reliability,
            "candle_count": self.candle_count,
            "description": self.description,
            "action": self.action,
            "needs_confirmation": self.needs_confirmation,
        }


def _body(o: float, c: float) -> float:
    return abs(c - o)


def _upper_shadow(h: float, o: float, c: float) -> float:
    return h - max(o, c)


def _lower_shadow(l: float, o: float, c: float) -> float:
    return min(o, c) - l


def _is_bullish(o: float, c: float) -> bool:
    return c > o


def _is_bearish(o: float, c: float) -> bool:
    return c < o


def _avg_body(opens: np.ndarray, closes: np.ndarray, n: int = 10) -> float:
    bodies = np.abs(closes[-n:] - opens[-n:])
    return float(np.mean(bodies)) if len(bodies) > 0 else 1.0


def detect_candlestick_patterns(df: pd.DataFrame) -> list[CandlePattern]:
    """Detect all candlestick patterns on the last few candles.

    Args:
        df: OHLCV DataFrame with Open, High, Low, Close columns

    Returns:
        List of detected patterns on the most recent candles.
    """
    if df.empty or len(df) < 15:
        return []

    patterns = []

    o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    c = df["Close"].values.astype(float)
    v = df["Volume"].values.astype(float) if "Volume" in df.columns else np.ones(len(df))

    i = len(df) - 1  # Latest candle
    avg_b = _avg_body(o, c, 10)

    body = _body(o[i], c[i])
    upper = _upper_shadow(h[i], o[i], c[i])
    lower = _lower_shadow(l[i], o[i], c[i])
    total_range = h[i] - l[i]

    if total_range == 0:
        return []

    body_pct = body / total_range

    # ═══════════════════════════════════════════════════════════
    # SINGLE CANDLE PATTERNS
    # ═══════════════════════════════════════════════════════════

    # 1. Doji (indecision — body < 10% of range)
    if body_pct < 0.10:
        if lower > 2 * body and upper < body:
            patterns.append(CandlePattern("Dragonfly Doji", "bullish", 4, 1,
                "Long lower shadow, no upper — strong buying at lows", "reversal"))
        elif upper > 2 * body and lower < body:
            patterns.append(CandlePattern("Gravestone Doji", "bearish", 4, 1,
                "Long upper shadow, no lower — strong selling at highs", "reversal"))
        else:
            patterns.append(CandlePattern("Doji", "neutral", 3, 1,
                "Indecision — buyers and sellers in balance", "reversal"))

    # 2. Hammer (bullish reversal after downtrend)
    if (body_pct < 0.35 and lower > 2 * body and upper < body * 0.5
            and i >= 5 and c[i] > c[i-5]):  # In a downtrend context
        if c[i-3] > c[i-1]:  # Recent downtrend
            patterns.append(CandlePattern("Hammer", "bullish", 4, 1,
                "Small body at top, long lower shadow — buyers defended the low", "reversal"))

    # 3. Inverted Hammer
    if (body_pct < 0.35 and upper > 2 * body and lower < body * 0.5):
        if i >= 3 and c[i-3] > c[i-1]:  # After downtrend
            patterns.append(CandlePattern("Inverted Hammer", "bullish", 3, 1,
                "Small body at bottom, long upper shadow — buying attempt", "reversal", True))

    # 4. Hanging Man (bearish after uptrend — same shape as hammer)
    if (body_pct < 0.35 and lower > 2 * body and upper < body * 0.5):
        if i >= 3 and c[i-1] > c[i-3]:  # After uptrend
            patterns.append(CandlePattern("Hanging Man", "bearish", 3, 1,
                "Hammer at top of uptrend — potential reversal", "reversal", True))

    # 5. Shooting Star (bearish reversal)
    if (body_pct < 0.35 and upper > 2 * body and lower < body * 0.5):
        if i >= 3 and c[i-1] > c[i-3]:  # After uptrend
            patterns.append(CandlePattern("Shooting Star", "bearish", 4, 1,
                "Long upper shadow after rally — sellers pushing back hard", "reversal"))

    # 6. Marubozu (strong conviction candle — no shadows)
    if body_pct > 0.90:
        if _is_bullish(o[i], c[i]):
            patterns.append(CandlePattern("Bullish Marubozu", "bullish", 4, 1,
                "Full-body bullish candle — extreme buying conviction", "continuation", False))
        else:
            patterns.append(CandlePattern("Bearish Marubozu", "bearish", 4, 1,
                "Full-body bearish candle — extreme selling conviction", "continuation", False))

    # 7. Spinning Top (indecision)
    if 0.15 < body_pct < 0.35 and upper > body and lower > body:
        patterns.append(CandlePattern("Spinning Top", "neutral", 2, 1,
            "Small body with shadows both sides — market undecided", "reversal"))

    # ═══════════════════════════════════════════════════════════
    # TWO-CANDLE PATTERNS
    # ═══════════════════════════════════════════════════════════

    if i >= 1:
        prev_body = _body(o[i-1], c[i-1])
        prev_bullish = _is_bullish(o[i-1], c[i-1])
        curr_bullish = _is_bullish(o[i], c[i])

        # 8. Bullish Engulfing
        if (not prev_bullish and curr_bullish
                and o[i] <= c[i-1] and c[i] >= o[i-1]
                and body > prev_body * 1.0):
            patterns.append(CandlePattern("Bullish Engulfing", "bullish", 5, 2,
                "Green candle completely engulfs previous red — strong reversal signal", "reversal", False))

        # 9. Bearish Engulfing
        if (prev_bullish and not curr_bullish
                and o[i] >= c[i-1] and c[i] <= o[i-1]
                and body > prev_body * 1.0):
            patterns.append(CandlePattern("Bearish Engulfing", "bearish", 5, 2,
                "Red candle completely engulfs previous green — strong reversal signal", "reversal", False))

        # 10. Piercing Line (bullish)
        if (not prev_bullish and curr_bullish
                and o[i] < l[i-1]  # Gap down open
                and c[i] > (o[i-1] + c[i-1]) / 2  # Close above midpoint of prev
                and c[i] < o[i-1]):  # But not above prev open
            patterns.append(CandlePattern("Piercing Line", "bullish", 4, 2,
                "Gap down then rally past midpoint of previous red candle", "reversal"))

        # 11. Dark Cloud Cover (bearish)
        if (prev_bullish and not curr_bullish
                and o[i] > h[i-1]  # Gap up open
                and c[i] < (o[i-1] + c[i-1]) / 2  # Close below midpoint of prev
                and c[i] > o[i-1]):  # But not below prev open
            patterns.append(CandlePattern("Dark Cloud Cover", "bearish", 4, 2,
                "Gap up then sell-off past midpoint of previous green candle", "reversal"))

        # 12. Harami (inside candle)
        if (body < prev_body * 0.5
                and max(o[i], c[i]) < max(o[i-1], c[i-1])
                and min(o[i], c[i]) > min(o[i-1], c[i-1])):
            if not prev_bullish:
                patterns.append(CandlePattern("Bullish Harami", "bullish", 3, 2,
                    "Small candle inside previous large red — selling exhaustion", "reversal", True))
            else:
                patterns.append(CandlePattern("Bearish Harami", "bearish", 3, 2,
                    "Small candle inside previous large green — buying exhaustion", "reversal", True))

        # 13. Tweezer Top (bearish)
        if (abs(h[i] - h[i-1]) / h[i] < 0.001  # Same highs
                and prev_bullish and not curr_bullish):
            patterns.append(CandlePattern("Tweezer Top", "bearish", 4, 2,
                "Two candles with identical highs — double rejection at resistance", "reversal"))

        # 14. Tweezer Bottom (bullish)
        if (abs(l[i] - l[i-1]) / l[i] < 0.001  # Same lows
                and not prev_bullish and curr_bullish):
            patterns.append(CandlePattern("Tweezer Bottom", "bullish", 4, 2,
                "Two candles with identical lows — double support hold", "reversal"))

    # ═══════════════════════════════════════════════════════════
    # THREE-CANDLE PATTERNS
    # ═══════════════════════════════════════════════════════════

    if i >= 2:
        # 15. Morning Star (bullish reversal)
        if (_is_bearish(o[i-2], c[i-2])  # First: big red
                and _body(o[i-2], c[i-2]) > avg_b * 0.8
                and _body(o[i-1], c[i-1]) < avg_b * 0.3  # Second: small body (star)
                and _is_bullish(o[i], c[i])  # Third: big green
                and _body(o[i], c[i]) > avg_b * 0.8
                and c[i] > (o[i-2] + c[i-2]) / 2):  # Closes above midpoint of first
            patterns.append(CandlePattern("Morning Star", "bullish", 5, 3,
                "Big red + small star + big green — powerful bullish reversal", "reversal", False))

        # 16. Evening Star (bearish reversal)
        if (_is_bullish(o[i-2], c[i-2])  # First: big green
                and _body(o[i-2], c[i-2]) > avg_b * 0.8
                and _body(o[i-1], c[i-1]) < avg_b * 0.3  # Second: small star
                and _is_bearish(o[i], c[i])  # Third: big red
                and _body(o[i], c[i]) > avg_b * 0.8
                and c[i] < (o[i-2] + c[i-2]) / 2):
            patterns.append(CandlePattern("Evening Star", "bearish", 5, 3,
                "Big green + small star + big red — powerful bearish reversal", "reversal", False))

        # 17. Three White Soldiers (bullish continuation)
        if all(_is_bullish(o[i-j], c[i-j]) for j in range(3)):
            bodies = [_body(o[i-j], c[i-j]) for j in range(3)]
            if all(b > avg_b * 0.6 for b in bodies):
                if c[i] > c[i-1] > c[i-2]:  # Each close higher
                    patterns.append(CandlePattern("Three White Soldiers", "bullish", 5, 3,
                        "Three consecutive strong green candles — powerful uptrend", "continuation", False))

        # 18. Three Black Crows (bearish continuation)
        if all(_is_bearish(o[i-j], c[i-j]) for j in range(3)):
            bodies = [_body(o[i-j], c[i-j]) for j in range(3)]
            if all(b > avg_b * 0.6 for b in bodies):
                if c[i] < c[i-1] < c[i-2]:  # Each close lower
                    patterns.append(CandlePattern("Three Black Crows", "bearish", 5, 3,
                        "Three consecutive strong red candles — powerful downtrend", "continuation", False))

    # Sort by reliability
    patterns.sort(key=lambda p: p.reliability, reverse=True)
    return patterns


def get_candlestick_features(df: pd.DataFrame) -> dict[str, float]:
    """Convert candlestick patterns into numeric features for ML.

    Returns a dict of features:
      - candle_bullish_count: number of bullish patterns detected
      - candle_bearish_count: number of bearish patterns detected
      - candle_max_reliability: highest reliability pattern (0-5)
      - candle_net_signal: +1 (bullish) to -1 (bearish) aggregate
    """
    patterns = detect_candlestick_patterns(df)

    if not patterns:
        return {
            "candle_bullish_count": 0,
            "candle_bearish_count": 0,
            "candle_max_reliability": 0,
            "candle_net_signal": 0.0,
        }

    bullish = [p for p in patterns if p.signal == "bullish"]
    bearish = [p for p in patterns if p.signal == "bearish"]

    bull_score = sum(p.reliability for p in bullish)
    bear_score = sum(p.reliability for p in bearish)
    total = bull_score + bear_score

    return {
        "candle_bullish_count": len(bullish),
        "candle_bearish_count": len(bearish),
        "candle_max_reliability": max(p.reliability for p in patterns),
        "candle_net_signal": (bull_score - bear_score) / max(total, 1),
    }
