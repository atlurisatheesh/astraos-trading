"""AstraOS Quant — Regime Detector (HMM-based market regime classification)."""

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger()


class RegimeDetector:
    """Detect market regimes: Bull, Bear, Sideways, Crisis.

    Uses a simplified volatility + trend approach (works without hmmlearn).
    For production, swap in HMM from hmmlearn.
    """

    REGIMES = {0: "bull", 1: "sideways", 2: "bear", 3: "crisis"}

    def detect(self, df: pd.DataFrame) -> dict:
        """Classify current market regime from OHLCV data."""
        if df.empty or len(df) < 60:
            return {"regime": "unknown", "confidence": 0, "indicators": {}}

        close = df["Close"].values if "Close" in df.columns else df.iloc[:, 3].values
        returns = np.diff(np.log(close))

        # Indicators
        sma_20 = np.mean(close[-20:])
        sma_50 = np.mean(close[-50:])
        current_price = close[-1]
        vol_20 = np.std(returns[-20:]) * np.sqrt(252) * 100  # annualized vol
        vol_60 = np.std(returns[-60:]) * np.sqrt(252) * 100
        trend_20 = (close[-1] - close[-20]) / close[-20] * 100
        trend_50 = (close[-1] - close[-50]) / close[-50] * 100

        # Classification rules
        if vol_20 > 35:
            regime = "crisis"
            confidence = min(95, 60 + vol_20)
        elif trend_20 > 3 and current_price > sma_50 and vol_20 < 20:
            regime = "bull"
            confidence = min(90, 50 + trend_20 * 5)
        elif trend_20 < -3 and current_price < sma_50:
            regime = "bear"
            confidence = min(90, 50 + abs(trend_20) * 5)
        else:
            regime = "sideways"
            confidence = max(40, 70 - abs(trend_20) * 5)

        return {
            "regime": regime,
            "confidence": round(confidence, 1),
            "indicators": {
                "volatility_20d": round(vol_20, 2),
                "volatility_60d": round(vol_60, 2),
                "trend_20d_pct": round(trend_20, 2),
                "trend_50d_pct": round(trend_50, 2),
                "price_vs_sma50": "above" if current_price > sma_50 else "below",
                "vol_regime": "high" if vol_20 > 25 else "normal" if vol_20 > 15 else "low",
            },
        }


class PositionSizer:
    """Fractional Kelly Criterion position sizing with constraints."""

    def calculate(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        capital: float,
        max_position_pct: float = 5.0,
        kelly_fraction: float = 0.25,  # Use 1/4 Kelly for safety
    ) -> dict:
        """Calculate optimal position size.

        Returns recommended position size as % of capital.
        Uses fractional Kelly (default 1/4) for safety.
        """
        if avg_loss == 0 or win_rate <= 0:
            return {"pct_of_capital": 0, "amount": 0, "kelly_full": 0}

        # Full Kelly
        b = avg_win / avg_loss  # win/loss ratio
        p = win_rate
        q = 1 - p
        kelly_full = (b * p - q) / b

        # Fractional Kelly (conservative)
        kelly = max(0, kelly_full * kelly_fraction)

        # Cap at max position
        kelly = min(kelly * 100, max_position_pct)

        return {
            "pct_of_capital": round(kelly, 2),
            "amount": round(capital * kelly / 100, 2),
            "kelly_full": round(kelly_full * 100, 2),
            "kelly_fraction_used": kelly_fraction,
        }
