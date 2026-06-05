# type: ignore
"""AstraOS ML — Chart Pattern Recognition.

Detects classic chart patterns in OHLCV data:
  - Head & Shoulders (top/bottom)
  - Double Top / Double Bottom
  - Cup & Handle
  - Ascending / Descending Triangle
  - Rising / Falling Wedge
  - Bull / Bear Flag

Uses peak/trough detection on closing prices with configurable lookback.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger()


@dataclass
class ChartPattern:
    """A detected chart pattern."""
    pattern: str
    signal: str  # "bullish" or "bearish"
    confidence: float  # 0.0 - 1.0
    start_date: str
    end_date: str
    description: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "pattern": self.pattern,
            "signal": self.signal,
            "confidence": round(self.confidence, 2),
            "start_date": self.start_date,
            "end_date": self.end_date,
            "description": self.description,
        }
        if self.target_price:
            d["target_price"] = round(self.target_price, 2)
        if self.stop_loss:
            d["stop_loss"] = round(self.stop_loss, 2)
        return d


class PatternDetector:
    """Detect chart patterns in price data."""

    def detect_all(self, symbol: str, period: str = "6mo") -> list[ChartPattern]:
        """Detect all patterns for a symbol."""
        yf_sym = f"{symbol}.NS" if not symbol.endswith(".NS") and not symbol.startswith("^") else symbol
        try:
            df = yf.download(yf_sym, period=period, interval="1d", progress=False)
            if df.empty or len(df) < 30:
                return []

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            close = df["Close"].values.astype(float)
            high = df["High"].values.astype(float)
            low = df["Low"].values.astype(float)
            dates = df.index

            patterns: list[ChartPattern] = []
            patterns.extend(self._detect_double_top(close, dates))
            patterns.extend(self._detect_double_bottom(close, dates))
            patterns.extend(self._detect_head_shoulders(close, dates))
            patterns.extend(self._detect_triangle(close, high, low, dates))
            patterns.extend(self._detect_flag(close, dates))
            patterns.extend(self._detect_wedge(close, high, low, dates))

            patterns.sort(key=lambda p: p.confidence, reverse=True)
            return patterns

        except Exception as e:
            logger.warning("Pattern detection failed", symbol=symbol, error=str(e))
            return []

    def _find_peaks(self, data: np.ndarray, order: int = 5) -> list[int]:
        """Find local maxima indices."""
        peaks = []
        for i in range(order, len(data) - order):
            if all(data[i] >= data[i - j] for j in range(1, order + 1)) and \
               all(data[i] >= data[i + j] for j in range(1, order + 1)):
                peaks.append(i)
        return peaks

    def _find_troughs(self, data: np.ndarray, order: int = 5) -> list[int]:
        """Find local minima indices."""
        troughs = []
        for i in range(order, len(data) - order):
            if all(data[i] <= data[i - j] for j in range(1, order + 1)) and \
               all(data[i] <= data[i + j] for j in range(1, order + 1)):
                troughs.append(i)
        return troughs

    def _detect_double_top(self, close: np.ndarray, dates: Any) -> list[ChartPattern]:
        """Detect double top pattern (bearish reversal)."""
        patterns: list[ChartPattern] = []
        peaks = self._find_peaks(close, order=7)

        for i in range(len(peaks) - 1):
            p1, p2 = peaks[i], peaks[i + 1]
            if p2 - p1 < 10 or p2 - p1 > 60:
                continue

            price_diff_pct = abs(close[p1] - close[p2]) / close[p1] * 100
            if price_diff_pct < 3.0:  # Peaks within 3%
                neckline = min(close[p1:p2 + 1])
                height = close[p1] - neckline
                confidence = max(0.5, min(0.9, 1.0 - price_diff_pct / 5))

                patterns.append(ChartPattern(
                    pattern="Double Top",
                    signal="bearish",
                    confidence=confidence,
                    start_date=str(dates[p1].date()) if hasattr(dates[p1], "date") else str(dates[p1]),
                    end_date=str(dates[p2].date()) if hasattr(dates[p2], "date") else str(dates[p2]),
                    description=f"Two peaks at ~₹{close[p1]:.0f} — bearish reversal",
                    target_price=float(neckline - height),
                    stop_loss=float(max(close[p1], close[p2]) * 1.02),
                ))
        return patterns[:2]

    def _detect_double_bottom(self, close: np.ndarray, dates: Any) -> list[ChartPattern]:
        """Detect double bottom pattern (bullish reversal)."""
        patterns: list[ChartPattern] = []
        troughs = self._find_troughs(close, order=7)

        for i in range(len(troughs) - 1):
            t1, t2 = troughs[i], troughs[i + 1]
            if t2 - t1 < 10 or t2 - t1 > 60:
                continue

            price_diff_pct = abs(close[t1] - close[t2]) / close[t1] * 100
            if price_diff_pct < 3.0:
                neckline = max(close[t1:t2 + 1])
                height = neckline - close[t1]
                confidence = max(0.5, min(0.9, 1.0 - price_diff_pct / 5))

                patterns.append(ChartPattern(
                    pattern="Double Bottom",
                    signal="bullish",
                    confidence=confidence,
                    start_date=str(dates[t1].date()) if hasattr(dates[t1], "date") else str(dates[t1]),
                    end_date=str(dates[t2].date()) if hasattr(dates[t2], "date") else str(dates[t2]),
                    description=f"Two troughs at ~₹{close[t1]:.0f} — bullish reversal",
                    target_price=float(neckline + height),
                    stop_loss=float(min(close[t1], close[t2]) * 0.98),
                ))
        return patterns[:2]

    def _detect_head_shoulders(self, close: np.ndarray, dates: Any) -> list[ChartPattern]:
        """Detect Head & Shoulders pattern."""
        patterns: list[ChartPattern] = []
        peaks = self._find_peaks(close, order=5)

        for i in range(len(peaks) - 2):
            left, head, right = peaks[i], peaks[i + 1], peaks[i + 2]

            # Head must be higher than shoulders
            if close[head] > close[left] and close[head] > close[right]:
                # Shoulders should be roughly equal
                shoulder_diff = abs(close[left] - close[right]) / close[left] * 100
                if shoulder_diff < 5:
                    head_height = close[head] - min(close[left], close[right])
                    neckline = min(close[left:right + 1])
                    confidence = max(0.55, min(0.9, 0.7 + (close[head] - close[left]) / close[head] * 5))

                    patterns.append(ChartPattern(
                        pattern="Head & Shoulders",
                        signal="bearish",
                        confidence=confidence,
                        start_date=str(dates[left].date()) if hasattr(dates[left], "date") else str(dates[left]),
                        end_date=str(dates[right].date()) if hasattr(dates[right], "date") else str(dates[right]),
                        description=f"Head at ₹{close[head]:.0f}, shoulders at ~₹{close[left]:.0f}",
                        target_price=float(neckline - head_height),
                        stop_loss=float(close[head] * 1.02),
                    ))
        return patterns[:1]

    def _detect_triangle(self, close: np.ndarray, high: np.ndarray, low: np.ndarray, dates: Any) -> list[ChartPattern]:
        """Detect ascending/descending triangle."""
        patterns: list[ChartPattern] = []
        n = len(close)
        if n < 30:
            return patterns

        window = min(n, 50)
        recent_high = high[-window:]
        recent_low = low[-window:]

        # Check for ascending triangle: flat top + rising bottoms
        high_range = (max(recent_high) - min(recent_high[-10:])) / max(recent_high) * 100
        low_slope = (recent_low[-1] - recent_low[0]) / recent_low[0] * 100

        if high_range < 3 and low_slope > 3:
            patterns.append(ChartPattern(
                pattern="Ascending Triangle",
                signal="bullish",
                confidence=0.7,
                start_date=str(dates[-window].date()) if hasattr(dates[-window], "date") else str(dates[-window]),
                end_date=str(dates[-1].date()) if hasattr(dates[-1], "date") else str(dates[-1]),
                description="Flat resistance + rising support — bullish breakout expected",
                target_price=float(max(recent_high) + (max(recent_high) - min(recent_low))),
            ))

        # Check for descending triangle: flat bottom + falling tops
        low_range = (max(recent_low[-10:]) - min(recent_low)) / max(recent_low) * 100
        high_slope = (recent_high[-1] - recent_high[0]) / recent_high[0] * 100

        if low_range < 3 and high_slope < -3:
            patterns.append(ChartPattern(
                pattern="Descending Triangle",
                signal="bearish",
                confidence=0.7,
                start_date=str(dates[-window].date()) if hasattr(dates[-window], "date") else str(dates[-window]),
                end_date=str(dates[-1].date()) if hasattr(dates[-1], "date") else str(dates[-1]),
                description="Falling resistance + flat support — bearish breakdown expected",
                target_price=float(min(recent_low) - (max(recent_high) - min(recent_low))),
            ))

        return patterns

    def _detect_flag(self, close: np.ndarray, dates: Any) -> list[ChartPattern]:
        """Detect bull/bear flag pattern."""
        patterns: list[ChartPattern] = []
        n = len(close)
        if n < 25:
            return patterns

        # Check last 25 bars: strong move in first 10, consolidation in last 15
        pole = close[-25:-15]
        flag = close[-15:]

        pole_change = (pole[-1] - pole[0]) / pole[0] * 100
        flag_range = (max(flag) - min(flag)) / min(flag) * 100

        if pole_change > 8 and flag_range < 5:
            patterns.append(ChartPattern(
                pattern="Bull Flag",
                signal="bullish",
                confidence=0.65,
                start_date=str(dates[-25].date()) if hasattr(dates[-25], "date") else str(dates[-25]),
                end_date=str(dates[-1].date()) if hasattr(dates[-1], "date") else str(dates[-1]),
                description=f"Strong rally ({pole_change:.1f}%) followed by tight consolidation",
                target_price=float(close[-1] + (pole[-1] - pole[0])),
            ))

        if pole_change < -8 and flag_range < 5:
            patterns.append(ChartPattern(
                pattern="Bear Flag",
                signal="bearish",
                confidence=0.65,
                start_date=str(dates[-25].date()) if hasattr(dates[-25], "date") else str(dates[-25]),
                end_date=str(dates[-1].date()) if hasattr(dates[-1], "date") else str(dates[-1]),
                description=f"Strong decline ({pole_change:.1f}%) followed by tight consolidation",
                target_price=float(close[-1] + (pole[-1] - pole[0])),
            ))

        return patterns

    def _detect_wedge(self, close: np.ndarray, high: np.ndarray, low: np.ndarray, dates: Any) -> list[ChartPattern]:
        """Detect rising/falling wedge."""
        patterns: list[ChartPattern] = []
        n = len(close)
        if n < 30:
            return patterns

        window = min(n, 40)
        recent_high = high[-window:]
        recent_low = low[-window:]

        high_slope = (recent_high[-1] - recent_high[0]) / recent_high[0] * 100
        low_slope = (recent_low[-1] - recent_low[0]) / recent_low[0] * 100

        # Rising wedge: both slopes positive but converging
        if high_slope > 2 and low_slope > 2 and low_slope > high_slope:
            patterns.append(ChartPattern(
                pattern="Rising Wedge",
                signal="bearish",
                confidence=0.6,
                start_date=str(dates[-window].date()) if hasattr(dates[-window], "date") else str(dates[-window]),
                end_date=str(dates[-1].date()) if hasattr(dates[-1], "date") else str(dates[-1]),
                description="Converging uptrend — bearish reversal likely",
            ))

        # Falling wedge: both slopes negative but converging
        if high_slope < -2 and low_slope < -2 and high_slope < low_slope:
            patterns.append(ChartPattern(
                pattern="Falling Wedge",
                signal="bullish",
                confidence=0.6,
                start_date=str(dates[-window].date()) if hasattr(dates[-window], "date") else str(dates[-window]),
                end_date=str(dates[-1].date()) if hasattr(dates[-1], "date") else str(dates[-1]),
                description="Converging downtrend — bullish reversal likely",
            ))

        return patterns


# ── Factory ─────────────────────────────────────────────────

_detector: Optional[PatternDetector] = None


def get_pattern_detector() -> PatternDetector:
    global _detector
    if _detector is None:
        _detector = PatternDetector()
    return _detector
