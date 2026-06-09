"""AstraOS Quant — Comprehensive Market Analyzer.

This is the master analysis module that combines ALL analysis types
to produce a complete market picture for any stock:

  1. Technical Indicators (80+ indicators)
  2. Candlestick Patterns (18 patterns, 1-3 candle)
  3. Chart Patterns (6 patterns — H&S, Double Top/Bottom, etc.)
  4. Support/Resistance (Pivot Points)
  5. Market Regime (Bull/Bear/Sideways/Crisis)
  6. Volume Analysis (Accumulation/Distribution)
  7. Multi-Timeframe Confirmation
  8. ML Model Prediction
  9. Risk Assessment

This module answers: "Should I buy, sell, or wait?"
And more importantly: "WHY?"
"""

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger()
IST = ZoneInfo("Asia/Kolkata")


@dataclass
class MarketAnalysis:
    """Complete market analysis for a single stock."""
    symbol: str
    timestamp: str
    price: float

    # Overall verdict
    verdict: str           # "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "STRONG_SELL"
    confidence: float      # 0-100
    reasoning: str

    # Component scores (-100 to +100)
    trend_score: float = 0
    momentum_score: float = 0
    volume_score: float = 0
    pattern_score: float = 0
    regime_score: float = 0
    mtf_score: float = 0

    # Key levels
    support_1: float = 0
    support_2: float = 0
    resistance_1: float = 0
    resistance_2: float = 0
    pivot: float = 0
    vwap: float = 0

    # Risk metrics
    atr: float = 0
    suggested_sl: float = 0
    suggested_target: float = 0
    risk_reward: float = 0

    # Patterns detected
    candlestick_patterns: list = field(default_factory=list)
    chart_patterns: list = field(default_factory=list)

    # Regime
    regime: str = "unknown"
    volatility: float = 0

    # Detailed breakdown
    indicators: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "price": self.price,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 1),
            "reasoning": self.reasoning,
            "scores": {
                "trend": round(self.trend_score, 1),
                "momentum": round(self.momentum_score, 1),
                "volume": round(self.volume_score, 1),
                "pattern": round(self.pattern_score, 1),
                "regime": round(self.regime_score, 1),
                "mtf": round(self.mtf_score, 1),
            },
            "levels": {
                "support_1": round(self.support_1, 2),
                "support_2": round(self.support_2, 2),
                "resistance_1": round(self.resistance_1, 2),
                "resistance_2": round(self.resistance_2, 2),
                "pivot": round(self.pivot, 2),
                "vwap": round(self.vwap, 2),
            },
            "risk": {
                "atr": round(self.atr, 2),
                "suggested_sl": round(self.suggested_sl, 2),
                "suggested_target": round(self.suggested_target, 2),
                "risk_reward": round(self.risk_reward, 2),
            },
            "candlestick_patterns": [p.to_dict() for p in self.candlestick_patterns],
            "chart_patterns": [p.to_dict() for p in self.chart_patterns],
            "regime": self.regime,
            "volatility": round(self.volatility, 2),
        }


async def analyze_stock_complete(symbol: str) -> MarketAnalysis:
    """Run complete market analysis on a stock.

    This combines all available analysis into a single actionable report.
    """
    from ..services.market_data_service import get_market_data_provider
    from .technical import compute_all_indicators, get_signal_summary
    from .candlestick_patterns import detect_candlestick_patterns
    from ..ml.pattern_detector import PatternDetector
    from .regime_detector import RegimeDetector

    provider = get_market_data_provider()
    df = await provider.get_ohlcv(symbol, period="1y")

    if df.empty or len(df) < 60:
        return MarketAnalysis(
            symbol=symbol,
            timestamp=datetime.now(IST).isoformat(),
            price=0,
            verdict="HOLD",
            confidence=0,
            reasoning="Insufficient data for analysis",
        )

    # Compute all indicators
    indicators_df = compute_all_indicators(df)
    summary = get_signal_summary(indicators_df)
    latest = indicators_df.iloc[-1]
    price = float(summary["price"])

    # ── 1. Trend Score (-100 to +100) ──
    trend_score = 0
    if summary["trend"] == "bullish":
        trend_score += 40
    else:
        trend_score -= 40

    # EMA alignment (9 > 21 > 50 = strong trend)
    ema9 = float(latest.get("EMA_9", 0))
    ema21 = float(latest.get("EMA_21", 0))
    ema50 = float(latest.get("EMA_50", 0))
    if ema9 > ema21 > ema50:
        trend_score += 30  # Perfect bullish alignment
    elif ema9 < ema21 < ema50:
        trend_score -= 30  # Perfect bearish alignment

    # Price vs SMA200
    sma200 = float(latest.get("SMA_200", 0))
    if sma200 > 0:
        if price > sma200:
            trend_score += 20
        else:
            trend_score -= 20

    # ADX strength
    adx = float(summary.get("adx", 0))
    if adx > 25:
        trend_score = int(trend_score * 1.3)  # Amplify in strong trend

    trend_score = max(-100, min(100, trend_score))

    # ── 2. Momentum Score (-100 to +100) ──
    rsi = float(summary["rsi"])
    momentum_score = 0

    if rsi > 70:
        momentum_score -= 40  # Overbought
    elif rsi > 60:
        momentum_score += 20  # Bullish momentum
    elif rsi < 30:
        momentum_score += 40  # Oversold (contrarian buy)
    elif rsi < 40:
        momentum_score -= 20  # Bearish momentum

    # MACD
    if summary["macd"] > summary["macd_signal"]:
        momentum_score += 30
    else:
        momentum_score -= 30

    # Stochastic
    stoch_k = float(latest.get("Stoch_K", 50))
    if stoch_k > 80:
        momentum_score -= 15
    elif stoch_k < 20:
        momentum_score += 15

    momentum_score = max(-100, min(100, momentum_score))

    # ── 3. Volume Score (-100 to +100) ──
    volume_score = 0
    rel_vol = float(latest.get("rel_volume", 1)) if "rel_volume" in indicators_df.columns else 1
    cmf = float(latest.get("CMF", 0))
    obv_trend = 0
    if "OBV" in indicators_df.columns and len(indicators_df) > 20:
        obv_now = float(indicators_df["OBV"].iloc[-1])
        obv_20 = float(indicators_df["OBV"].iloc[-20])
        obv_trend = 1 if obv_now > obv_20 else -1

    if rel_vol > 1.5:
        volume_score += 30 * (1 if trend_score > 0 else -1)  # Volume confirms trend
    if cmf > 0.1:
        volume_score += 30  # Money flowing in
    elif cmf < -0.1:
        volume_score -= 30  # Money flowing out
    volume_score += obv_trend * 20

    volume_score = max(-100, min(100, volume_score))

    # ── 4. Pattern Score (-100 to +100) ──
    candle_patterns = detect_candlestick_patterns(indicators_df)
    chart_patterns = []
    try:
        detector = PatternDetector()
        chart_patterns = detector.detect_all(symbol, period="6mo")
    except Exception:
        pass

    pattern_score = 0
    for cp in candle_patterns:
        weight = cp.reliability * 8
        if cp.signal == "bullish":
            pattern_score += weight
        elif cp.signal == "bearish":
            pattern_score -= weight

    for chp in chart_patterns:
        weight = int(chp.confidence * 40)
        if chp.signal == "bullish":
            pattern_score += weight
        else:
            pattern_score -= weight

    pattern_score = max(-100, min(100, pattern_score))

    # ── 5. Regime Score (-100 to +100) ──
    regime_info = RegimeDetector().detect(df)
    regime = regime_info["regime"]
    vol_20d = regime_info["indicators"].get("volatility_20d", 15)

    regime_score = 0
    if regime == "bull":
        regime_score = 50
    elif regime == "bear":
        regime_score = -50
    elif regime == "crisis":
        regime_score = -80
    # else sideways = 0

    # ── 6. Multi-Timeframe Score (-100 to +100) ──
    mtf_alignment = int(latest.get("mtf_alignment", 0)) if "mtf_alignment" in indicators_df.columns else 0
    mtf_score = (mtf_alignment - 1.5) / 1.5 * 100  # 0 -> -100, 1.5 -> 0, 3 -> +100

    # ── Combine all scores ──
    weights = {
        "trend": 0.25,
        "momentum": 0.20,
        "volume": 0.15,
        "pattern": 0.15,
        "regime": 0.15,
        "mtf": 0.10,
    }

    composite = (
        trend_score * weights["trend"] +
        momentum_score * weights["momentum"] +
        volume_score * weights["volume"] +
        pattern_score * weights["pattern"] +
        regime_score * weights["regime"] +
        mtf_score * weights["mtf"]
    )

    # Map composite to verdict
    if composite > 50:
        verdict = "STRONG_BUY"
    elif composite > 20:
        verdict = "BUY"
    elif composite < -50:
        verdict = "STRONG_SELL"
    elif composite < -20:
        verdict = "SELL"
    else:
        verdict = "HOLD"

    confidence = min(95, 50 + abs(composite) * 0.5)

    # ── Key Levels ──
    atr = float(summary.get("atr", price * 0.02))
    if atr == 0:
        atr = price * 0.02
    vwap = float(latest.get("VWAP", price)) if "VWAP" in indicators_df.columns else price
    pivot_val = float(latest.get("pivot", price)) if "pivot" in indicators_df.columns else price
    r1 = float(latest.get("R1", price + atr)) if "R1" in indicators_df.columns else price + atr
    r2 = float(latest.get("R2", price + 2*atr)) if "R2" in indicators_df.columns else price + 2*atr
    s1 = float(latest.get("S1", price - atr)) if "S1" in indicators_df.columns else price - atr
    s2 = float(latest.get("S2", price - 2*atr)) if "S2" in indicators_df.columns else price - 2*atr

    # SL and Target
    if composite > 0:  # Bullish
        sl = price - atr * 1.5
        target = price + atr * 3
    else:
        sl = price + atr * 1.5
        target = price - atr * 3

    risk = abs(price - sl)
    reward = abs(target - price)
    rr = reward / risk if risk > 0 else 0

    # ── Build reasoning ──
    reasons = []
    if abs(trend_score) > 30:
        reasons.append(f"Trend {'bullish' if trend_score > 0 else 'bearish'} ({trend_score:+.0f})")
    if abs(momentum_score) > 30:
        reasons.append(f"RSI {rsi:.0f} {'oversold' if rsi < 30 else 'overbought' if rsi > 70 else ''}")
    if candle_patterns:
        top_cp = candle_patterns[0]
        reasons.append(f"{top_cp.name} ({top_cp.signal}, {top_cp.reliability} stars)")
    if chart_patterns:
        reasons.append(f"Chart: {chart_patterns[0].pattern}")
    if abs(volume_score) > 20:
        reasons.append(f"Volume {'confirming' if (volume_score > 0) == (trend_score > 0) else 'diverging'}")
    reasons.append(f"Regime: {regime}")
    reasons.append(f"VWAP: {'above' if price > vwap else 'below'}")

    return MarketAnalysis(
        symbol=symbol,
        timestamp=datetime.now(IST).isoformat(),
        price=price,
        verdict=verdict,
        confidence=confidence,
        reasoning=" | ".join(reasons),
        trend_score=trend_score,
        momentum_score=momentum_score,
        volume_score=volume_score,
        pattern_score=pattern_score,
        regime_score=regime_score,
        mtf_score=mtf_score,
        support_1=s1,
        support_2=s2,
        resistance_1=r1,
        resistance_2=r2,
        pivot=pivot_val,
        vwap=vwap,
        atr=atr,
        suggested_sl=sl,
        suggested_target=target,
        risk_reward=rr,
        candlestick_patterns=candle_patterns,
        chart_patterns=chart_patterns,
        regime=regime,
        volatility=vol_20d,
        indicators=summary,
    )
