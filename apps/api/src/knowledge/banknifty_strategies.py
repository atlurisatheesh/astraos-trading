"""AstraOS Knowledge — Bank Nifty & F&O Strategy Engine.

Encodes trading strategies from:
- Natenberg (Option Volatility & Pricing)
- McMillan (Options as a Strategic Investment)
- Passarelli (Trading Options Greeks)
- Sinclair (Volatility Trading)
- Dalton (Mind Over Markets)
- Murphy (Technical Analysis)
- Miner (High Probability Trading)
- Nison (Candlestick Charting)
- Douglas (Trading in the Zone)

Provides:
1. Regime detection → strategy selection
2. Options strategy recommender
3. Bank Nifty-specific playbooks
4. Position sizing with Greek-aware risk
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, timezone
from enum import Enum
from typing import Any


# ── Market Regime (Dalton + Sinclair) ──

class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    BREAKOUT = "breakout"
    RANGE = "range"
    HIGH_VOL = "high_vol"
    EXPIRY = "expiry"
    CRISIS = "crisis"


@dataclass
class RegimeContext:
    """Current market regime context for strategy selection."""
    regime: MarketRegime
    vix: float
    atr: float
    adx: float
    bank_nifty_level: float
    days_to_expiry: int
    pcr: float
    max_pain: float
    opening_range_high: float = 0
    opening_range_low: float = 0

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "vix": round(self.vix, 2),
            "atr": round(self.atr, 2),
            "adx": round(self.adx, 2),
            "level": round(self.bank_nifty_level, 2),
            "dte": self.days_to_expiry,
            "pcr": round(self.pcr, 2),
            "max_pain": round(self.max_pain, 2),
        }


def classify_regime(
    vix: float,
    adx: float,
    atr_pct: float,
    days_to_expiry: int,
    trend_direction: str = "neutral",
) -> MarketRegime:
    """Classify market regime (Dalton + Sinclair framework).

    Uses VIX, ADX, ATR%, and days-to-expiry.
    """
    if vix > 30:
        return MarketRegime.CRISIS
    if days_to_expiry <= 1:
        return MarketRegime.EXPIRY
    if vix > 22:
        return MarketRegime.HIGH_VOL
    if adx > 25 and atr_pct > 1.5:
        return MarketRegime.BREAKOUT
    if adx > 25:
        return MarketRegime.TRENDING_UP if trend_direction == "up" else MarketRegime.TRENDING_DOWN
    return MarketRegime.RANGE


# ── Options Strategy Selector (Natenberg + McMillan) ──

@dataclass
class OptionsStrategy:
    """Recommended options strategy with full parameters."""
    name: str
    structure: str         # e.g. "Buy ATM CE" or "Sell OTM Strangle"
    legs: list[dict]       # Strike, type, side, qty
    max_profit: str        # "Unlimited" or fixed amount
    max_loss: str
    breakeven: str
    ideal_regime: str
    greeks_profile: str    # e.g. "Long gamma, negative theta"
    risk_reward: float
    confidence: float      # 0-100
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "name": self.name, "structure": self.structure,
            "legs": self.legs, "max_profit": self.max_profit,
            "max_loss": self.max_loss, "breakeven": self.breakeven,
            "regime": self.ideal_regime, "greeks": self.greeks_profile,
            "risk_reward": round(self.risk_reward, 2),
            "confidence": round(self.confidence),
            "reasoning": self.reasoning,
        }


# Strategy library (top strategies from Natenberg + McMillan)
STRATEGY_LIBRARY = {
    # ── Bullish Strategies ──
    "long_call": {
        "name": "Long Call",
        "structure": "Buy 1 ATM/slightly ITM Call",
        "ideal_regime": ["trending_up", "breakout"],
        "vix_preference": "low_to_medium",  # Buy when IV is low
        "greeks": "Long delta, long gamma, negative theta, long vega",
        "risk_reward": 3.0,
        "notes": "Natenberg: buy calls when IV is below historical mean",
    },
    "bull_call_spread": {
        "name": "Bull Call Spread",
        "structure": "Buy ATM Call + Sell OTM Call",
        "ideal_regime": ["trending_up"],
        "vix_preference": "medium",
        "greeks": "Long delta (reduced), limited gamma/vega exposure",
        "risk_reward": 2.0,
        "notes": "McMillan: cheaper than long call, capped upside but defined risk",
    },
    "bull_put_spread": {
        "name": "Bull Put Spread (Credit)",
        "structure": "Sell ATM Put + Buy OTM Put",
        "ideal_regime": ["range", "trending_up"],
        "vix_preference": "high",  # Sell when IV is high
        "greeks": "Short delta (put side), positive theta",
        "risk_reward": 1.5,
        "notes": "Natenberg: sell high IV, collect premium in supportive trend",
    },

    # ── Bearish Strategies ──
    "long_put": {
        "name": "Long Put",
        "structure": "Buy 1 ATM/slightly ITM Put",
        "ideal_regime": ["trending_down", "crisis"],
        "vix_preference": "low_to_medium",
        "greeks": "Short delta, long gamma, negative theta, long vega",
        "risk_reward": 3.0,
        "notes": "Sinclair: puts are expensive in high vol; prefer bear spreads then",
    },
    "bear_put_spread": {
        "name": "Bear Put Spread",
        "structure": "Buy ATM Put + Sell OTM Put",
        "ideal_regime": ["trending_down"],
        "vix_preference": "medium_to_high",
        "greeks": "Short delta, limited vega exposure",
        "risk_reward": 2.0,
        "notes": "McMillan: defined risk bearish play",
    },

    # ── Neutral / Range Strategies ──
    "short_strangle": {
        "name": "Short Strangle",
        "structure": "Sell OTM Call + Sell OTM Put",
        "ideal_regime": ["range"],
        "vix_preference": "high",
        "greeks": "Near-zero delta, positive theta, short gamma, short vega",
        "risk_reward": 0.5,
        "notes": "Natenberg: best when IV > realized vol; requires active management",
    },
    "iron_condor": {
        "name": "Iron Condor",
        "structure": "Sell OTM Call + Buy far OTM Call + Sell OTM Put + Buy far OTM Put",
        "ideal_regime": ["range"],
        "vix_preference": "high",
        "greeks": "Near-zero delta, positive theta, defined risk",
        "risk_reward": 0.7,
        "notes": "McMillan: safer than strangle; wings provide protection",
    },
    "iron_butterfly": {
        "name": "Iron Butterfly",
        "structure": "Sell ATM Call + Sell ATM Put + Buy OTM Call + Buy OTM Put",
        "ideal_regime": ["range", "expiry"],
        "vix_preference": "high",
        "greeks": "Zero delta at center, max theta at ATM",
        "risk_reward": 1.0,
        "notes": "Best when expecting pin near a specific level (max pain on expiry)",
    },

    # ── Volatility Strategies ──
    "long_straddle": {
        "name": "Long Straddle",
        "structure": "Buy ATM Call + Buy ATM Put",
        "ideal_regime": ["breakout", "high_vol"],
        "vix_preference": "low",  # Buy when IV is low before expected move
        "greeks": "Zero delta, long gamma, negative theta, long vega",
        "risk_reward": 2.5,
        "notes": "Sinclair: only when IV < realized vol forecast; time decay is enemy",
    },
    "calendar_spread": {
        "name": "Calendar Spread",
        "structure": "Sell near-month ATM + Buy far-month ATM (same strike)",
        "ideal_regime": ["range"],
        "vix_preference": "medium",
        "greeks": "Long vega, positive theta (from near-expiry decay)",
        "risk_reward": 1.5,
        "notes": "Natenberg: profits from time decay differential; best near support/resistance",
    },
}


def recommend_strategy(
    regime: MarketRegime,
    vix: float,
    spot: float,
    days_to_expiry: int,
    capital: float = 100000,
    risk_tolerance: str = "moderate",  # conservative, moderate, aggressive
) -> list[OptionsStrategy]:
    """Recommend options strategies based on regime and market context.

    Uses Natenberg + McMillan + Sinclair frameworks.
    """
    vix_level = "low" if vix < 14 else "high" if vix > 22 else "medium"

    recommendations = []

    for key, strat in STRATEGY_LIBRARY.items():
        if regime.value not in strat["ideal_regime"]:
            continue

        # Vix preference matching
        vix_pref = strat["vix_preference"]
        vix_match = True
        if "low" in vix_pref and vix_level == "high":
            vix_match = False
        if "high" in vix_pref and vix_level == "low":
            vix_match = False

        if not vix_match:
            confidence = 40  # Suboptimal but still possible
        else:
            confidence = 75

        # Adjust confidence by DTE
        if days_to_expiry <= 2 and "theta" in strat["greeks"].lower() and "positive" in strat["greeks"].lower():
            confidence += 10  # Theta strategies benefit from near-expiry
        if days_to_expiry <= 2 and "negative theta" in strat["greeks"].lower():
            confidence -= 15  # Theta decay hurts long premium near expiry

        # Risk tolerance adjustment
        if risk_tolerance == "conservative":
            if "strangle" in key or "straddle" in key:
                confidence -= 20
            if "spread" in key or "condor" in key:
                confidence += 10
        elif risk_tolerance == "aggressive":
            if "long_call" in key or "long_put" in key:
                confidence += 10

        # Build legs based on spot price
        legs = _build_legs(key, spot, days_to_expiry)

        recommendations.append(OptionsStrategy(
            name=strat["name"],
            structure=strat["structure"],
            legs=legs,
            max_profit="Unlimited" if "long" in key and "spread" not in key else "Limited",
            max_loss="Premium paid" if "long" in key else "Defined" if "condor" in key or "butterfly" in key or "spread" in key else "Unlimited",
            breakeven=f"Strike ± premium",
            ideal_regime=regime.value,
            greeks_profile=strat["greeks"],
            risk_reward=strat["risk_reward"],
            confidence=min(95, max(20, confidence)),
            reasoning=strat["notes"],
        ))

    # Sort by confidence
    recommendations.sort(key=lambda x: x.confidence, reverse=True)
    return recommendations[:3]  # Top 3


def _build_legs(strategy_key: str, spot: float, dte: int) -> list[dict]:
    """Build option legs based on strategy and current spot."""
    # Round to nearest 100 for Bank Nifty, 50 for Nifty
    atm = round(spot / 100) * 100

    if strategy_key == "long_call":
        return [{"strike": atm, "type": "CE", "side": "BUY", "qty": 1}]
    elif strategy_key == "long_put":
        return [{"strike": atm, "type": "PE", "side": "BUY", "qty": 1}]
    elif strategy_key == "bull_call_spread":
        return [
            {"strike": atm, "type": "CE", "side": "BUY", "qty": 1},
            {"strike": atm + 500, "type": "CE", "side": "SELL", "qty": 1},
        ]
    elif strategy_key == "bear_put_spread":
        return [
            {"strike": atm, "type": "PE", "side": "BUY", "qty": 1},
            {"strike": atm - 500, "type": "PE", "side": "SELL", "qty": 1},
        ]
    elif strategy_key == "bull_put_spread":
        return [
            {"strike": atm - 200, "type": "PE", "side": "SELL", "qty": 1},
            {"strike": atm - 700, "type": "PE", "side": "BUY", "qty": 1},
        ]
    elif strategy_key == "short_strangle":
        return [
            {"strike": atm + 500, "type": "CE", "side": "SELL", "qty": 1},
            {"strike": atm - 500, "type": "PE", "side": "SELL", "qty": 1},
        ]
    elif strategy_key == "iron_condor":
        return [
            {"strike": atm + 500, "type": "CE", "side": "SELL", "qty": 1},
            {"strike": atm + 1000, "type": "CE", "side": "BUY", "qty": 1},
            {"strike": atm - 500, "type": "PE", "side": "SELL", "qty": 1},
            {"strike": atm - 1000, "type": "PE", "side": "BUY", "qty": 1},
        ]
    elif strategy_key == "iron_butterfly":
        return [
            {"strike": atm, "type": "CE", "side": "SELL", "qty": 1},
            {"strike": atm, "type": "PE", "side": "SELL", "qty": 1},
            {"strike": atm + 500, "type": "CE", "side": "BUY", "qty": 1},
            {"strike": atm - 500, "type": "PE", "side": "BUY", "qty": 1},
        ]
    elif strategy_key == "long_straddle":
        return [
            {"strike": atm, "type": "CE", "side": "BUY", "qty": 1},
            {"strike": atm, "type": "PE", "side": "BUY", "qty": 1},
        ]
    elif strategy_key == "calendar_spread":
        return [
            {"strike": atm, "type": "CE", "side": "SELL", "qty": 1, "expiry": "weekly"},
            {"strike": atm, "type": "CE", "side": "BUY", "qty": 1, "expiry": "monthly"},
        ]
    return []


# ── Bank Nifty Playbook (3 Core Setups) ──

@dataclass
class TradeSetup:
    """Bank Nifty trade setup (Dalton + Miner + Murphy)."""
    name: str
    setup_type: str        # trend, breakout_failure, range_premium
    entry_condition: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    position_size: int     # lots
    options_strategy: str
    risk_amount: float
    reward_amount: float
    risk_reward: float
    regime: str
    confidence: float
    checklist: list[str]

    def to_dict(self) -> dict:
        return {
            "name": self.name, "type": self.setup_type,
            "entry_condition": self.entry_condition,
            "entry": round(self.entry_price, 2),
            "stop_loss": round(self.stop_loss, 2),
            "target_1": round(self.target_1, 2),
            "target_2": round(self.target_2, 2),
            "lots": self.position_size,
            "options": self.options_strategy,
            "risk": round(self.risk_amount, 2),
            "reward": round(self.reward_amount, 2),
            "rr": round(self.risk_reward, 2),
            "regime": self.regime,
            "confidence": round(self.confidence),
            "checklist": self.checklist,
        }


def generate_bank_nifty_setup(
    regime: MarketRegime,
    spot: float,
    vix: float,
    atr: float,
    opening_range_high: float = 0,
    opening_range_low: float = 0,
    capital: float = 500000,
    max_risk_pct: float = 1.0,
) -> TradeSetup | None:
    """Generate a Bank Nifty trade setup based on regime.

    Uses Dalton (Market Profile), Murphy (Technical Analysis),
    and Miner (High Probability Trading) frameworks.
    """
    lot_size = 15  # Bank Nifty
    max_risk = capital * (max_risk_pct / 100)

    if regime == MarketRegime.TRENDING_UP:
        entry = spot  # Pullback to VWAP (simplified)
        sl = spot - atr * 1.0
        t1 = spot + atr * 1.5
        t2 = spot + atr * 2.5
        risk = (entry - sl) * lot_size
        lots = max(1, int(max_risk / risk)) if risk > 0 else 1

        return TradeSetup(
            name="Bank Nifty Trend Follow — Bullish",
            setup_type="trend",
            entry_condition="Pullback to VWAP in uptrend (ADX > 25)",
            entry_price=entry, stop_loss=sl, target_1=t1, target_2=t2,
            position_size=lots,
            options_strategy="Buy ATM CE or Bull Call Spread",
            risk_amount=risk * lots, reward_amount=(t1 - entry) * lot_size * lots,
            risk_reward=round((t1 - entry) / (entry - sl), 2) if entry != sl else 0,
            regime=regime.value, confidence=72,
            checklist=[
                "✅ ADX > 25 confirming trend",
                "✅ Price above VWAP",
                "✅ OI buildup supports direction",
                "✅ VIX < 22 (not crisis)",
                "⬜ RSI not overbought (< 75)",
            ],
        )

    elif regime == MarketRegime.BREAKOUT:
        if opening_range_high == 0:
            opening_range_high = spot + atr * 0.5
        if opening_range_low == 0:
            opening_range_low = spot - atr * 0.5

        or_range = opening_range_high - opening_range_low
        entry = opening_range_high  # Breakout above OR high
        sl = opening_range_low
        t1 = entry + or_range
        t2 = entry + or_range * 2

        risk = (entry - sl) * lot_size
        lots = max(1, int(max_risk / risk)) if risk > 0 else 1

        return TradeSetup(
            name="Bank Nifty Opening Range Breakout",
            setup_type="breakout_failure",
            entry_condition=f"Break above OR high ({opening_range_high:.0f}) with volume",
            entry_price=entry, stop_loss=sl, target_1=t1, target_2=t2,
            position_size=lots,
            options_strategy="Buy ATM CE (breakout) or Debit Spread",
            risk_amount=risk * lots, reward_amount=(t1 - entry) * lot_size * lots,
            risk_reward=round((t1 - entry) / (entry - sl), 2) if entry != sl else 0,
            regime=regime.value, confidence=65,
            checklist=[
                "✅ First 15-min range defined",
                "✅ Breakout with above-average volume",
                "✅ VIX supports breakout (18-25)",
                "⬜ Not a false breakout (confirm with 5-min close)",
                "⬜ OI change supports direction",
            ],
        )

    elif regime == MarketRegime.RANGE:
        entry = spot  # Sell premium at ±2σ
        upper_strike = round((spot + atr * 2) / 100) * 100
        lower_strike = round((spot - atr * 2) / 100) * 100
        premium_collected = atr * 0.3  # Estimated premium per lot

        return TradeSetup(
            name="Bank Nifty Range Day — Iron Condor",
            setup_type="range_premium",
            entry_condition=f"Sell {upper_strike} CE + {lower_strike} PE strangle (±2σ)",
            entry_price=spot, stop_loss=0,  # Managed by adjustment
            target_1=premium_collected * 0.5 * lot_size,  # 50% of premium
            target_2=premium_collected * 0.7 * lot_size,  # 70% of premium
            position_size=1,
            options_strategy=f"Iron Condor: Sell {upper_strike}CE/{lower_strike}PE, Buy wings ±500",
            risk_amount=max_risk * 0.5,
            reward_amount=premium_collected * 0.5 * lot_size,
            risk_reward=0.7,
            regime=regime.value, confidence=68,
            checklist=[
                "✅ ADX < 20 (no trend)",
                "✅ VIX in normal range",
                "✅ Not expiry day",
                "✅ Bank Nifty within yesterday's value area",
                "⬜ Premium > 2x expected move",
            ],
        )

    elif regime in (MarketRegime.CRISIS, MarketRegime.HIGH_VOL):
        return TradeSetup(
            name="Bank Nifty — RISK OFF",
            setup_type="no_trade",
            entry_condition="VIX > 25 — reduce exposure or sit out",
            entry_price=spot, stop_loss=spot, target_1=spot, target_2=spot,
            position_size=0,
            options_strategy="Close open positions or buy protective puts",
            risk_amount=0, reward_amount=0, risk_reward=0,
            regime=regime.value, confidence=90,
            checklist=[
                "⚠️ VIX elevated — high whipsaw risk",
                "⚠️ Reduce position size by 50-75%",
                "✅ Consider hedging with OTM puts",
                "✅ Wait for VIX to settle below 22",
            ],
        )

    return None
