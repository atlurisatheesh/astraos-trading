"""AstraOS Knowledge — Creator Strategy Engine.

Encodes trading strategies from followed educators (StockVid Telugu, etc.)
as executable trade gates and filters in the signal pipeline.

These are NOT theoretical rules — they are specific conditions that must
be met before the system takes a trade, learned from educators who've
been in the markets for years.
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import structlog

logger = structlog.get_logger()
IST = ZoneInfo("Asia/Kolkata")


def load_creator_strategies() -> dict:
    """Load all creator strategy files."""
    data_dir = Path(__file__).parent.parent.parent / "data" / "creator_lessons"
    strategies = {}

    for f in data_dir.glob("*_complete.json"):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
                creator = data.get("creator", f.stem)
                strategies[creator] = data
        except Exception as e:
            logger.error("Failed to load creator strategies", file=str(f), error=str(e))

    return strategies


def evaluate_creator_gates(
    signal: dict,
    now: datetime | None = None,
    vix: float = 15.0,
    rsi: float = 50.0,
    volume_ratio: float = 1.0,
    above_vwap: bool = True,
    candle_patterns: list | None = None,
    regime: str = "normal",
) -> dict:
    """Evaluate all creator-taught rules against a signal.

    Returns:
        {
            "allowed": True/False,
            "reasons": [...],
            "matching_strategies": [...],
            "quality_score": 0-100  (how well the signal matches known setups)
        }
    """
    if now is None:
        now = datetime.now(IST)

    reasons = []
    matching_strategies = []
    quality_score = 50  # Start neutral

    action = signal.get("action", "HOLD")
    confidence = signal.get("confidence", 0)

    # ── General Rules (from StockVid Telugu) ──────────────────────────

    # Rule: No trading in first 15 minutes
    if now.hour == 9 and now.minute < 30:
        reasons.append("StockVid Rule: No trading in first 15 min (9:15-9:30)")
        quality_score -= 30

    # Rule: No new entries after 2 PM (except scalps)
    if now.hour >= 14:
        reasons.append("StockVid Rule: Avoid new entries after 2:00 PM")
        quality_score -= 15

    # Rule: Volume confirmation mandatory
    if volume_ratio < 1.0:
        reasons.append("StockVid Rule: Volume below average — no volume = no trade")
        quality_score -= 20

    if action == "HOLD":
        return {
            "allowed": True,
            "reasons": [],
            "matching_strategies": [],
            "quality_score": 0,
        }

    # ── Candlestick Pattern Matching ─────────────────────────────────

    if candle_patterns:
        for cp in candle_patterns:
            name = cp.get("name", "") if isinstance(cp, dict) else getattr(cp, "name", "")
            cp_signal = cp.get("signal", "") if isinstance(cp, dict) else getattr(cp, "signal", "")
            reliability = cp.get("reliability", 0) if isinstance(cp, dict) else getattr(cp, "reliability", 0)

            # Bullish Engulfing at oversold = strong buy (StockVid strategy)
            if name == "Bullish Engulfing" and action == "BUY" and rsi < 40:
                matching_strategies.append("StockVid: Bullish Engulfing Reversal")
                quality_score += 25

            # Shooting Star at overbought = strong sell
            if name == "Shooting Star" and action == "SELL" and rsi > 65:
                matching_strategies.append("StockVid: Shooting Star Short")
                quality_score += 25

            # Bullish Marubozu with volume = strong buy
            if "Marubozu" in name and "Bullish" in name and volume_ratio > 1.5:
                matching_strategies.append("StockVid: Bullish Marubozu Entry")
                quality_score += 20

            # Doji at key level
            if "Doji" in name:
                matching_strategies.append("StockVid: Doji at S/R — wait for confirmation")
                quality_score += 5  # Small bonus, needs confirmation

            # Pattern agrees with signal direction
            if (action == "BUY" and cp_signal == "bullish") or (action == "SELL" and cp_signal == "bearish"):
                quality_score += reliability * 3

            # Pattern disagrees with signal direction (warning)
            if (action == "BUY" and cp_signal == "bearish") or (action == "SELL" and cp_signal == "bullish"):
                reasons.append(f"Warning: {name} pattern contradicts {action} signal")
                quality_score -= reliability * 5

    # ── VWAP Rule ────────────────────────────────────────────────────
    if action == "BUY" and not above_vwap:
        reasons.append("StockVid Rule: Buying below VWAP is risky — price below institutional avg")
        quality_score -= 15

    if action == "SELL" and above_vwap:
        reasons.append("StockVid Rule: Selling above VWAP is risky — institutions are buyers here")
        quality_score -= 15

    # ── VIX Rule ─────────────────────────────────────────────────────
    if vix > 20:
        reasons.append(f"StockVid Rule: VIX at {vix:.1f} — high volatility, reduce position size")
        quality_score -= 10

    if vix > 25 and regime == "crisis":
        reasons.append("StockVid Rule: Crisis regime + high VIX — skip trade entirely")
        quality_score -= 30

    # ── BTST Check (if it's late afternoon buy) ──────────────────────
    if action == "BUY" and now.hour >= 14 and now.minute >= 30:
        if above_vwap and volume_ratio > 1.2:
            matching_strategies.append("StockVid: BTST Setup (end-of-day breakout)")
            quality_score += 15
        else:
            reasons.append("Late buy but doesn't meet BTST criteria (need above VWAP + volume)")

    # ── Expiry Day Rules ─────────────────────────────────────────────
    if now.weekday() == 3:  # Thursday
        reasons.append("StockVid Rule: Expiry day — avoid directional bets, prefer theta plays")
        quality_score -= 10

    # ── Quality Assessment ───────────────────────────────────────────
    quality_score = max(0, min(100, quality_score))

    allowed = quality_score >= 30  # Block trades with very low quality

    if not allowed:
        reasons.append(f"Trade quality score too low ({quality_score}/100) — blocked by creator rules")

    return {
        "allowed": allowed,
        "reasons": reasons,
        "matching_strategies": matching_strategies,
        "quality_score": quality_score,
    }
