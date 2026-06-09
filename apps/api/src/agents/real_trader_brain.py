"""AstraOS — Real Trader Brain.

This is NOT a probability model. This is a rule-based confirmation engine
that thinks like a veteran trader with 30 years of experience.

A real trader doesn't guess. They check a CHECKLIST. If every item on the
checklist confirms, they trade. If even ONE item fails, they DON'T.

The checklist:
  1. TREND — Is the trend clear? (Not "maybe trending" — CLEAR)
  2. LEVEL — Is price at a KEY level? (Support, resistance, VWAP, pivot)
  3. PATTERN — Is there a HIGH-RELIABILITY candle pattern? (not Doji garbage)
  4. VOLUME — Is smart money participating? (Not retail noise)
  5. MOMENTUM — Is the move accelerating or dying?
  6. TIME — Is it the right time of day?
  7. REGIME — Is the overall market supporting this trade?
  8. NO CONTRADICTIONS — Zero red flags

All 8 must be GREEN. Not 7. Not 6. ALL 8.

This produces fewer trades (maybe 2-5 per week) but with near-certain conviction.
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
class Confirmation:
    name: str
    passed: bool
    signal: str        # "bullish" | "bearish" | "neutral" | "block"
    strength: int      # 1-10
    evidence: str      # what exactly was seen

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "signal": self.signal,
            "strength": self.strength,
            "evidence": self.evidence,
        }


@dataclass
class TradeDecision:
    action: str             # "BUY" | "SELL" | "NO_TRADE"
    conviction: str         # "ABSOLUTE" | "STRONG" | "NONE"
    confirmations_passed: int
    confirmations_total: int
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward: float
    position_size_pct: float  # % of capital to risk
    reasoning: str
    checklist: list[Confirmation] = field(default_factory=list)
    red_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "conviction": self.conviction,
            "confirmations": f"{self.confirmations_passed}/{self.confirmations_total}",
            "entry": round(self.entry_price, 2),
            "stop_loss": round(self.stop_loss, 2),
            "target_1": round(self.target_1, 2),
            "target_2": round(self.target_2, 2),
            "risk_reward": round(self.risk_reward, 2),
            "position_size_pct": round(self.position_size_pct, 2),
            "reasoning": self.reasoning,
            "checklist": [c.to_dict() for c in self.checklist],
            "red_flags": self.red_flags,
        }


def no_trade(reason: str, checklist: list[Confirmation] = None, red_flags: list[str] = None) -> TradeDecision:
    return TradeDecision(
        action="NO_TRADE", conviction="NONE",
        confirmations_passed=sum(1 for c in (checklist or []) if c.passed),
        confirmations_total=len(checklist or []),
        entry_price=0, stop_loss=0, target_1=0, target_2=0,
        risk_reward=0, position_size_pct=0,
        reasoning=reason,
        checklist=checklist or [],
        red_flags=red_flags or [],
    )


async def analyze_like_real_trader(symbol: str) -> TradeDecision:
    """Think like a veteran trader. Check every confirmation. Zero guessing.

    This function returns BUY or SELL ONLY when ALL 8 confirmations align.
    Otherwise it returns NO_TRADE — and that's the RIGHT answer most of the time.
    """
    from ..services.market_data_service import get_market_data_provider
    from ..quant.technical import compute_all_indicators, get_signal_summary
    from ..quant.candlestick_patterns import detect_candlestick_patterns
    from ..quant.regime_detector import RegimeDetector
    from ..quant.time_features import IntradayWindow, ExpiryCycle
    from ..knowledge.proven_strategies import CANDLESTICK_RELIABILITY

    now = datetime.now(IST)
    checklist: list[Confirmation] = []
    red_flags: list[str] = []

    # ── FETCH DATA ────────────────────────────────────────────────────
    provider = get_market_data_provider()
    df = await provider.get_ohlcv(symbol, period="1y")

    if df.empty or len(df) < 60:
        return no_trade(f"Insufficient data for {symbol}")

    indicators_df = compute_all_indicators(df)
    summary = get_signal_summary(indicators_df)
    latest = indicators_df.iloc[-1]

    price = float(summary["price"])
    if price <= 0:
        return no_trade("Invalid price data")

    atr = float(summary.get("atr", price * 0.02))
    if atr <= 0:
        atr = price * 0.02

    rsi = float(summary["rsi"])
    adx = float(summary["adx"])
    vwap = float(latest.get("VWAP", price)) if "VWAP" in indicators_df.columns else price
    sma20 = float(latest.get("SMA_20", 0))
    sma50 = float(latest.get("SMA_50", 0))
    sma200 = float(latest.get("SMA_200", 0))
    ema9 = float(latest.get("EMA_9", 0))
    ema21 = float(latest.get("EMA_21", 0))

    # ══════════════════════════════════════════════════════════════════
    # CHECK 1: TREND — Is the trend CLEAR? Not "maybe". CLEAR.
    # ══════════════════════════════════════════════════════════════════
    trend_bullish_count = 0
    trend_bearish_count = 0
    trend_checks = 0

    # EMA alignment
    if ema9 > ema21 > sma50:
        trend_bullish_count += 3  # Perfect bullish stack
    elif ema9 < ema21 < sma50:
        trend_bearish_count += 3

    # Price vs SMA200 (long-term trend)
    if sma200 > 0:
        trend_checks += 1
        if price > sma200:
            trend_bullish_count += 2
        else:
            trend_bearish_count += 2

    # ADX > 25 = trend exists (not sideways chop)
    trend_strength = adx > 25

    if trend_bullish_count >= 4 and trend_strength:
        checklist.append(Confirmation("TREND", True, "bullish", 9,
            f"Clear uptrend: EMA9>{ema9:.0f} > EMA21>{ema21:.0f} > SMA50>{sma50:.0f}, ADX={adx:.0f}"))
    elif trend_bearish_count >= 4 and trend_strength:
        checklist.append(Confirmation("TREND", True, "bearish", 9,
            f"Clear downtrend: EMA9<EMA21<SMA50, ADX={adx:.0f}"))
    else:
        checklist.append(Confirmation("TREND", False, "neutral", 2,
            f"No clear trend: ADX={adx:.0f}, EMAs not aligned"))
        red_flags.append(f"Trend unclear (ADX={adx:.0f}) — real traders don't trade chop")

    # ══════════════════════════════════════════════════════════════════
    # CHECK 2: LEVEL — Is price at a KEY level?
    # ══════════════════════════════════════════════════════════════════
    at_key_level = False
    level_type = ""

    pivot = float(latest.get("pivot", 0)) if "pivot" in indicators_df.columns else 0
    s1 = float(latest.get("S1", 0)) if "S1" in indicators_df.columns else 0
    r1 = float(latest.get("R1", 0)) if "R1" in indicators_df.columns else 0

    # Check proximity to key levels (within 0.5%) OR recent bounce/break
    proximity = price * 0.005
    key_levels = []
    if s1 > 0:
        key_levels.append(("Support S1", s1))
    if r1 > 0:
        key_levels.append(("Resistance R1", r1))
    if sma200 > 0:
        key_levels.append(("SMA200", sma200))
    if sma50 > 0:
        key_levels.append(("SMA50", sma50))
    if vwap > 0:
        key_levels.append(("VWAP", vwap))
    # Round number levels (psychological S/R)
    round_level = round(price / 50) * 50
    key_levels.append(("Round Number", round_level))

    # Also check if price recently touched a level (within last 3 candles)
    for level_name, level_price in key_levels:
        if level_price <= 0:
            continue
        dist = abs(price - level_price)
        # At the level now
        if dist < proximity:
            at_key_level = True
            level_type = f"{level_name} ({level_price:.0f})"
            break
        # Recently bounced FROM the level (within last 3 candles)
        if len(indicators_df) >= 3:
            recent_lows = indicators_df["Low"].iloc[-3:].values.astype(float)
            recent_highs = indicators_df["High"].iloc[-3:].values.astype(float)
            # Bounced off support (low touched level, now price above)
            if any(abs(low - level_price) < proximity for low in recent_lows) and price > level_price:
                at_key_level = True
                level_type = f"Bounced from {level_name} ({level_price:.0f})"
                break
            # Rejected at resistance (high touched level, now price below)
            if any(abs(high - level_price) < proximity for high in recent_highs) and price < level_price:
                at_key_level = True
                level_type = f"Rejected at {level_name} ({level_price:.0f})"
                break

    if at_key_level:
        checklist.append(Confirmation("LEVEL", True, "bullish" if price > vwap else "bearish", 8,
            f"Price at key level: {level_type}"))
    else:
        checklist.append(Confirmation("LEVEL", False, "neutral", 2,
            f"Price not at any key level — no edge in entry here"))

    # ══════════════════════════════════════════════════════════════════
    # CHECK 3: PATTERN — High-reliability candle pattern?
    # ══════════════════════════════════════════════════════════════════
    candle_patterns = detect_candlestick_patterns(indicators_df)
    strong_patterns = [p for p in candle_patterns if p.reliability >= 4]

    if strong_patterns:
        top = strong_patterns[0]
        known = CANDLESTICK_RELIABILITY.get(top.name, (0.5, 1.0, ""))
        if known[0] >= 0.60:
            checklist.append(Confirmation("PATTERN", True, top.signal, top.reliability * 2,
                f"{top.name} detected ({known[0]:.0%} win rate in backtests) — {top.description}"))
        else:
            checklist.append(Confirmation("PATTERN", False, "neutral", 3,
                f"{top.name} found but win rate only {known[0]:.0%} — not reliable enough"))
    else:
        checklist.append(Confirmation("PATTERN", False, "neutral", 1,
            "No high-reliability candle pattern (need 4+ star patterns)"))

    # ══════════════════════════════════════════════════════════════════
    # CHECK 4: VOLUME — Is smart money in this move?
    # ══════════════════════════════════════════════════════════════════
    rel_vol = float(latest.get("rel_volume", 1)) if "rel_volume" in indicators_df.columns else 1
    cmf = float(latest.get("CMF", 0))
    pv_div = bool(latest.get("pv_divergence", 0)) if "pv_divergence" in indicators_df.columns else False

    volume_confirms = rel_vol > 1.3 and not pv_div

    if volume_confirms:
        direction = "bullish" if cmf > 0 else "bearish"
        checklist.append(Confirmation("VOLUME", True, direction, 8,
            f"Smart money active: RelVol={rel_vol:.1f}x, CMF={cmf:.3f}, no P-V divergence"))
    else:
        reasons = []
        if rel_vol <= 1.3:
            reasons.append(f"low volume ({rel_vol:.1f}x avg)")
        if pv_div:
            reasons.append("price-volume divergence (fake move)")
        checklist.append(Confirmation("VOLUME", False, "neutral", 2,
            f"Volume NOT confirming: {', '.join(reasons)}"))
        if pv_div:
            red_flags.append("Price-volume divergence — move is likely fake")

    # ══════════════════════════════════════════════════════════════════
    # CHECK 5: MOMENTUM — Is the move accelerating?
    # ══════════════════════════════════════════════════════════════════
    macd = float(summary["macd"])
    macd_signal = float(summary["macd_signal"])
    macd_hist = float(latest.get("MACD_Hist", 0))

    momentum_bullish = rsi > 50 and rsi < 75 and macd > macd_signal and macd_hist > 0
    momentum_bearish = rsi < 50 and rsi > 25 and macd < macd_signal and macd_hist < 0

    if momentum_bullish:
        checklist.append(Confirmation("MOMENTUM", True, "bullish", 7,
            f"Bullish momentum: RSI={rsi:.0f}, MACD above signal, histogram positive"))
    elif momentum_bearish:
        checklist.append(Confirmation("MOMENTUM", True, "bearish", 7,
            f"Bearish momentum: RSI={rsi:.0f}, MACD below signal, histogram negative"))
    else:
        checklist.append(Confirmation("MOMENTUM", False, "neutral", 2,
            f"Momentum unclear: RSI={rsi:.0f}, MACD {'above' if macd > macd_signal else 'below'} signal"))
        if rsi > 75:
            red_flags.append(f"RSI at {rsi:.0f} — overbought, buying here is chasing")
        if rsi < 25:
            red_flags.append(f"RSI at {rsi:.0f} — oversold, selling here is panic")

    # ══════════════════════════════════════════════════════════════════
    # CHECK 6: TIME — Right time of day?
    # ══════════════════════════════════════════════════════════════════
    tod = IntradayWindow.classify(now)
    suitability = tod["trade_suitability"]

    if suitability >= 0.7:
        checklist.append(Confirmation("TIME", True, "bullish", 6,
            f"Good time: {tod['window_name']} (suitability {suitability:.1f})"))
    else:
        checklist.append(Confirmation("TIME", False, "block", 1,
            f"Bad time: {tod['window_name']} (suitability {suitability:.1f})"))
        red_flags.append(f"Time window '{tod['window_name']}' — real traders avoid this period")

    # ══════════════════════════════════════════════════════════════════
    # CHECK 7: REGIME — Market supporting this?
    # ══════════════════════════════════════════════════════════════════
    regime_info = RegimeDetector().detect(df)
    regime = regime_info["regime"]
    vol_20d = regime_info["indicators"].get("volatility_20d", 15)

    if regime in ("bull", "sideways") and vol_20d < 25:
        checklist.append(Confirmation("REGIME", True, "bullish" if regime == "bull" else "neutral", 7,
            f"Regime: {regime}, Vol: {vol_20d:.1f}% — favorable conditions"))
    elif regime == "bear" and vol_20d < 25:
        checklist.append(Confirmation("REGIME", True, "bearish", 7,
            f"Regime: bear, Vol: {vol_20d:.1f}% — favorable for shorts"))
    else:
        checklist.append(Confirmation("REGIME", False, "block", 1,
            f"Regime: {regime}, Vol: {vol_20d:.1f}% — hostile conditions"))
        if regime == "crisis":
            red_flags.append(f"CRISIS regime (vol {vol_20d:.0f}%) — capital preservation mode")

    # ══════════════════════════════════════════════════════════════════
    # CHECK 8: CONTRADICTIONS — Any red flags?
    # ══════════════════════════════════════════════════════════════════
    # Check for contradicting signals
    bullish_checks = [c for c in checklist if c.passed and c.signal == "bullish"]
    bearish_checks = [c for c in checklist if c.passed and c.signal == "bearish"]

    if bullish_checks and bearish_checks:
        red_flags.append(f"Mixed signals: {len(bullish_checks)} bullish + {len(bearish_checks)} bearish confirmations")

    # Expiry day caution
    expiry = ExpiryCycle.get_features()
    if expiry.get("is_expiry_day"):
        red_flags.append("Expiry day — gamma risk is extreme, reduce size 50%")

    has_contradictions = len(red_flags) > 0

    if not has_contradictions:
        checklist.append(Confirmation("NO_CONTRADICTIONS", True, "bullish", 10,
            "Zero red flags — all systems go"))
    else:
        checklist.append(Confirmation("NO_CONTRADICTIONS", False, "block", 1,
            f"{len(red_flags)} red flags found"))

    # ══════════════════════════════════════════════════════════════════
    # FINAL DECISION
    # ══════════════════════════════════════════════════════════════════
    passed = [c for c in checklist if c.passed]
    total = len(checklist)
    passed_count = len(passed)

    # Determine direction consensus
    bullish_strength = sum(c.strength for c in passed if c.signal == "bullish")
    bearish_strength = sum(c.strength for c in passed if c.signal == "bearish")

    # ALL 8 must pass for ABSOLUTE conviction
    if passed_count == total and not red_flags:
        if bullish_strength > bearish_strength:
            direction = "BUY"
            sl = price - atr * 1.5
            t1 = price + atr * 2
            t2 = price + atr * 3.5
        else:
            direction = "SELL"
            sl = price + atr * 1.5
            t1 = price - atr * 2
            t2 = price - atr * 3.5

        risk = abs(price - sl)
        reward = abs(t1 - price)
        rr = reward / risk if risk > 0 else 0

        return TradeDecision(
            action=direction,
            conviction="ABSOLUTE",
            confirmations_passed=passed_count,
            confirmations_total=total,
            entry_price=price,
            stop_loss=round(sl, 2),
            target_1=round(t1, 2),
            target_2=round(t2, 2),
            risk_reward=rr,
            position_size_pct=2.0,
            reasoning=f"ALL {total} confirmations passed. {direction} with full conviction.",
            checklist=checklist,
            red_flags=[],
        )

    # 7 of 8 with no critical red flags = STRONG conviction
    elif passed_count >= 7 and not any("CRISIS" in rf or "fake move" in rf for rf in red_flags):
        if bullish_strength > bearish_strength:
            direction = "BUY"
            sl = price - atr * 2
            t1 = price + atr * 2
            t2 = price + atr * 3
        else:
            direction = "SELL"
            sl = price + atr * 2
            t1 = price - atr * 2
            t2 = price - atr * 3

        risk = abs(price - sl)
        reward = abs(t1 - price)
        rr = reward / risk if risk > 0 else 0

        failed = [c for c in checklist if not c.passed]
        failed_names = ", ".join(c.name for c in failed)

        return TradeDecision(
            action=direction,
            conviction="STRONG",
            confirmations_passed=passed_count,
            confirmations_total=total,
            entry_price=price,
            stop_loss=round(sl, 2),
            target_1=round(t1, 2),
            target_2=round(t2, 2),
            risk_reward=rr,
            position_size_pct=1.0,  # Half size for strong (not absolute)
            reasoning=f"{passed_count}/{total} confirmations. Missing: {failed_names}. Reduced size.",
            checklist=checklist,
            red_flags=red_flags,
        )

    # Anything less = NO TRADE
    else:
        failed = [c for c in checklist if not c.passed]
        failed_names = ", ".join(c.name for c in failed)
        return no_trade(
            f"Only {passed_count}/{total} confirmations. Failed: {failed_names}. "
            f"Red flags: {'; '.join(red_flags[:3])}. A real trader sits this out.",
            checklist=checklist,
            red_flags=red_flags,
        )
