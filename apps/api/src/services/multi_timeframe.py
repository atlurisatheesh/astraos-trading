# type: ignore
"""AstraOS Services — Multi-Timeframe Analysis.

Combines signals from multiple timeframes (5m, 15m, 1h, 1d)
to generate higher-confidence trade signals.

Confluence scoring: signal is stronger when multiple timeframes agree.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger()


@dataclass
class TimeframeSignal:
    """Signal from a single timeframe."""
    timeframe: str
    trend: str  # "bullish", "bearish", "neutral"
    rsi: float
    macd_signal: str  # "bullish_cross", "bearish_cross", "neutral"
    sma_alignment: str  # "bullish" (price > SMA20 > SMA50), "bearish", "mixed"
    strength: float  # 0-1

    def to_dict(self) -> dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "trend": self.trend,
            "rsi": round(self.rsi, 2),
            "macd_signal": self.macd_signal,
            "sma_alignment": self.sma_alignment,
            "strength": round(self.strength, 2),
        }


@dataclass
class MultiTimeframeResult:
    """Combined multi-timeframe analysis."""
    symbol: str
    signals: list[TimeframeSignal] = field(default_factory=list)
    confluence_score: float = 0.0  # -1 (all bearish) to +1 (all bullish)
    overall_signal: str = "neutral"
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframes": [s.to_dict() for s in self.signals],
            "confluence_score": round(self.confluence_score, 2),
            "overall_signal": self.overall_signal,
            "confidence": round(self.confidence, 2),
            "recommendation": self._recommendation(),
        }

    def _recommendation(self) -> str:
        if self.confluence_score > 0.6:
            return f"STRONG BUY — {self.confidence:.0%} confluence across timeframes"
        elif self.confluence_score > 0.2:
            return f"BUY — moderate confluence ({self.confidence:.0%})"
        elif self.confluence_score < -0.6:
            return f"STRONG SELL — {self.confidence:.0%} bearish confluence"
        elif self.confluence_score < -0.2:
            return f"SELL — moderate bearish confluence"
        return "HOLD — mixed signals, wait for clarity"


TIMEFRAME_CONFIG = [
    ("5m", "5d", "5m"),
    ("15m", "1mo", "15m"),
    ("1h", "3mo", "1h"),
    ("1d", "1y", "1d"),
]


class MultiTimeframeService:
    """Analyze stocks across multiple timeframes."""

    async def analyze(self, symbol: str) -> MultiTimeframeResult:
        """Run multi-timeframe analysis."""
        yf_sym = f"{symbol}.NS" if not symbol.endswith(".NS") and not symbol.startswith("^") else symbol
        result = MultiTimeframeResult(symbol=symbol)

        for label, period, interval in TIMEFRAME_CONFIG:
            try:
                sig = self._analyze_timeframe(yf_sym, label, period, interval)
                if sig:
                    result.signals.append(sig)
            except Exception as e:
                logger.debug("Timeframe analysis failed", tf=label, error=str(e))

        # Calculate confluence
        if result.signals:
            scores = []
            for s in result.signals:
                if s.trend == "bullish":
                    scores.append(s.strength)
                elif s.trend == "bearish":
                    scores.append(-s.strength)
                else:
                    scores.append(0)

            # Weight higher timeframes more
            weights = [0.15, 0.2, 0.3, 0.35][:len(scores)]
            weighted = sum(s * w for s, w in zip(scores, weights))
            total_w = sum(weights)
            result.confluence_score = weighted / total_w if total_w else 0

            agreement = sum(1 for s in scores if (s > 0) == (weighted > 0)) / len(scores)
            result.confidence = agreement

            if result.confluence_score > 0.2:
                result.overall_signal = "bullish"
            elif result.confluence_score < -0.2:
                result.overall_signal = "bearish"

        return result

    def _analyze_timeframe(self, yf_sym: str, label: str, period: str, interval: str) -> Optional[TimeframeSignal]:
        """Analyze a single timeframe."""
        df = yf.download(yf_sym, period=period, interval=interval, progress=False)
        if df.empty or len(df) < 20:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"]
        last = float(close.iloc[-1])

        # SMA
        sma20 = float(close.rolling(20).mean().iloc[-1])
        sma50 = float(close.rolling(min(50, len(close))).mean().iloc[-1])

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50

        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        macd_cross = "neutral"
        if len(macd_line) >= 2:
            if float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]) and float(macd_line.iloc[-2]) <= float(signal_line.iloc[-2]):
                macd_cross = "bullish_cross"
            elif float(macd_line.iloc[-1]) < float(signal_line.iloc[-1]) and float(macd_line.iloc[-2]) >= float(signal_line.iloc[-2]):
                macd_cross = "bearish_cross"

        # SMA alignment
        if last > sma20 > sma50:
            sma_align = "bullish"
        elif last < sma20 < sma50:
            sma_align = "bearish"
        else:
            sma_align = "mixed"

        # Overall trend + strength
        bullish_factors = 0
        if last > sma20:
            bullish_factors += 1
        if last > sma50:
            bullish_factors += 1
        if rsi > 50:
            bullish_factors += 1
        if float(macd_line.iloc[-1]) > float(signal_line.iloc[-1]):
            bullish_factors += 1

        if bullish_factors >= 3:
            trend = "bullish"
        elif bullish_factors <= 1:
            trend = "bearish"
        else:
            trend = "neutral"

        strength = abs(bullish_factors - 2) / 2  # 0 to 1

        return TimeframeSignal(
            timeframe=label, trend=trend, rsi=rsi,
            macd_signal=macd_cross, sma_alignment=sma_align, strength=strength,
        )


_service: Optional[MultiTimeframeService] = None

def get_multi_timeframe_service() -> MultiTimeframeService:
    global _service
    if _service is None:
        _service = MultiTimeframeService()
    return _service
