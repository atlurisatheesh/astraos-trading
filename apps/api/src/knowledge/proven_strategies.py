"""AstraOS Knowledge — Proven Trading Strategies (Research-Backed).

Strategies sourced from:
  - Backtested candlestick patterns (56,680 trades study)
  - Bank Nifty ORB backtest results
  - Institutional smart money concepts
  - FII/DII flow analysis
  - Iron Condor/Straddle premium decay research
  - Supply/Demand zone studies (TrendSpider 2024)

Every strategy here has statistical evidence behind it.
"""

# ── Candlestick Pattern Reliability (from 56,680 trade backtest) ──────

CANDLESTICK_RELIABILITY = {
    # Pattern: (win_rate, profit_factor, best_context)
    # Source: QuantifiedStrategies.com + LiberatedStockTrader 56K trade study
    "Morning Star":          (0.75, 2.1, "after downtrend at support"),
    "Evening Star":          (0.75, 2.0, "after uptrend at resistance"),
    "Three White Soldiers":  (0.75, 1.9, "trend continuation bullish"),
    "Three Black Crows":     (0.75, 1.9, "trend continuation bearish"),
    "Bullish Engulfing":     (0.63, 1.7, "at support with volume > 1.5x"),
    "Bearish Engulfing":     (0.62, 1.6, "at resistance with volume"),
    "Inverted Hammer":       (0.60, 1.5, "after downtrend"),
    "Piercing Line":         (0.58, 1.4, "at support"),
    "Dark Cloud Cover":      (0.57, 1.4, "at resistance"),
    "Gravestone Doji":       (0.57, 1.3, "at resistance"),
    "Bearish Marubozu":      (0.56, 1.3, "strong selling conviction"),
    "Bullish Marubozu":      (0.55, 1.3, "strong buying conviction"),
    "Hammer":                (0.52, 1.2, "at support only — useless alone"),
    "Shooting Star":         (0.52, 1.2, "at resistance only"),
    "Doji":                  (0.50, 1.0, "indecision — needs confirmation"),
    "Spinning Top":          (0.48, 0.9, "weak signal — avoid trading"),
}

# Key finding: Patterns ALONE are barely above random (50-55%)
# They become 65-75% accurate ONLY with:
#   1. Trend context (pattern at end of trend)
#   2. Volume confirmation (>1.5x average)
#   3. Support/Resistance level confluence
#   4. Multi-timeframe agreement


# ── Bank Nifty Specific Strategies ────────────────────────────────────

BANK_NIFTY_STRATEGIES = {
    "ORB_15min": {
        "name": "Opening Range Breakout (15-min)",
        "description": "Mark first 15-min candle (9:15-9:30), trade breakout of high/low",
        "rules": {
            "entry": "Break above 9:30 high = BUY CE | Break below 9:30 low = BUY PE",
            "stop_loss": "Opposite side of Opening Range",
            "target": "1.5x to 2x the Opening Range height",
            "time_exit": "Close at 3:15 PM if neither hit",
            "max_trades_per_day": 1,
        },
        "filters": {
            "skip_if_range_too_narrow": "Range < 100 points = skip (false breakouts)",
            "skip_if_range_too_wide": "Range > 400 points = skip (SL too large)",
            "skip_if_gap_too_large": "Gap > 200 points = wait for fill first",
            "volume_confirmation": "Breakout candle volume > average",
        },
        "best_days": "Tuesday, Wednesday (most trending days)",
        "avoid_days": "Thursday (expiry), Friday (weekend risk)",
        "estimated_win_rate": 0.55,
        "estimated_rr": 1.8,
    },

    "VWAP_RSI": {
        "name": "VWAP + RSI Confluence",
        "description": "Trade when price crosses VWAP with RSI confirmation",
        "rules": {
            "buy_entry": "Price crosses above VWAP + RSI > 60 on 15-min chart",
            "sell_entry": "Price crosses below VWAP + RSI < 40",
            "stop_loss": "20 points below VWAP (for buy) / above (for sell)",
            "target": "Next resistance (buy) / support (sell)",
            "time_exit": "Exit when RSI crosses 50 from opposite side",
        },
        "estimated_win_rate": 0.58,
        "estimated_rr": 1.5,
    },

    "IRON_CONDOR_WEEKLY": {
        "name": "Weekly Iron Condor (Theta Decay)",
        "description": "Sell OTM options on both sides, profit from time decay",
        "rules": {
            "entry": "Sell 300+ point OTM CE + PE, buy 100-point further OTM for protection",
            "entry_time": "Monday/Tuesday (5-4 days to expiry)",
            "target": "50% of premium received (exit early, don't wait for full decay)",
            "stop_loss": "2x premium received OR spot within 100 points of sold strike",
            "adjustment": "If spot moves 200+ points, close losing side and roll",
        },
        "filters": {
            "vix_range": "12-18 (avoid if VIX > 20)",
            "skip_events": "RBI policy, budget, major bank results",
            "max_capital_deployed": "30% of total capital",
        },
        "estimated_win_rate": 0.72,
        "estimated_rr": 0.8,  # Low RR but high win rate
        "capital_required": "Rs 3-5 lakh per lot",
    },

    "EXPIRY_SCALP": {
        "name": "Thursday Expiry Day Scalp",
        "description": "Directional play using high gamma on expiry day",
        "rules": {
            "entry": "After 9:30 AM, trade in direction of first 15-min trend",
            "option_selection": "ATM or 1 strike OTM (highest gamma)",
            "stop_loss": "15-20% of premium",
            "target": "30-50% profit on premium",
            "time_exit": "Close by 3:00 PM regardless",
            "max_trades": 2,
        },
        "filters": {
            "skip_if_flat": "If first 15-min range < 50 points, skip",
            "skip_if_vix_high": "VIX > 20 = too unpredictable",
        },
        "estimated_win_rate": 0.50,  # Coin flip but high RR
        "estimated_rr": 2.5,
    },
}


# ── Smart Money / Institutional Concepts ──────────────────────────────

SMART_MONEY_RULES = {
    "fii_dii_flow": {
        "strong_bullish": "Both FII + DII net buyers for 3+ consecutive days",
        "strong_bearish": "FII heavy selling + DII buying (DII can't hold alone long-term)",
        "caution": "FII selling + building index futures shorts = real bearish signal",
        "noise": "Single day of FII selling = noise, ignore",
        "data_source": "NSE publishes daily after market close",
    },

    "oi_analysis": {
        "long_buildup": "Price UP + OI UP = strong bullish (new longs being added)",
        "short_buildup": "Price DOWN + OI UP = strong bearish (new shorts being added)",
        "long_unwinding": "Price DOWN + OI DOWN = weak bearish (longs exiting, not fresh shorts)",
        "short_covering": "Price UP + OI DOWN = weak bullish (shorts exiting, not fresh longs)",
        "max_pain_gravity": "Price tends to move toward max pain strike near expiry",
    },

    "supply_demand_zones": {
        "definition": "Price levels where institutional orders are unfilled — price revisits to fill them",
        "quality_criteria": [
            "Zone formed on 4H or daily timeframe (< 1H zones fail 60% of time)",
            "Price moved > 3% from zone within 5 candles (strong institutional move)",
            "First retest of fresh zone has 68% success rate (TrendSpider 2024 study)",
            "Second retest drops to 50% — zone weakens with each touch",
        ],
        "entry_rule": "Enter on first retest of fresh demand/supply zone",
        "stop_loss": "Below demand zone low / above supply zone high",
        "target": "Opposite zone or 2x risk",
    },

    "liquidity_sweep": {
        "definition": "Price hunts stop-losses at obvious levels then reverses",
        "identification": [
            "Price breaks below clear support (stops triggered)",
            "Within 1-5 candles, price reclaims above broken level",
            "Long lower shadow on reclaim candle (buying at swept lows)",
            "Volume spike on reclaim (institutional entry)",
        ],
        "entry": "After reclaim is confirmed (candle closes above swept level)",
        "stop_loss": "Low of the sweep candle",
        "target": "High of the range before the sweep",
    },
}


# ── Risk Management Rules (Universal) ─────────────────────────────────

RISK_RULES = {
    "position_sizing": {
        "max_risk_per_trade": "1-2% of capital",
        "half_kelly": "Use Half-Kelly criterion for optimal sizing",
        "never_risk_more_than": "5% of capital on any single position",
    },
    "stop_loss": {
        "mandatory": "Every trade MUST have a stop loss BEFORE entry",
        "types": ["Fixed (ATR-based)", "Trailing (Chandelier Exit)", "Time-based (3:15 PM)"],
        "never_move_sl_against": "Never widen your stop loss to avoid getting stopped out",
    },
    "daily_limits": {
        "max_daily_loss": "2% of capital — stop trading after this",
        "max_consecutive_losses": "2 losses in a row — take 30-minute break",
        "max_weekly_loss": "5% of capital — switch to paper trading for rest of week",
    },
    "event_calendar": {
        "no_trade_days": [
            "RBI monetary policy announcement day",
            "Union Budget day",
            "Election result day",
            "US Fed rate decision day (affects Indian markets next morning)",
        ],
        "reduce_size": [
            "F&O expiry day (Thursday)",
            "Major bank quarterly results day",
            "Global macro events (US CPI, jobs data)",
        ],
    },
}


def get_strategy_for_conditions(
    regime: str = "normal",
    vix: float = 15.0,
    is_expiry: bool = False,
    is_event_day: bool = False,
    time_hour: int = 10,
) -> dict:
    """Recommend the best strategy based on current market conditions."""

    if is_event_day:
        return {
            "strategy": "NO_TRADE",
            "reason": "Event day — sit out entirely or reduce to 25% size",
        }

    if vix > 25:
        return {
            "strategy": "HEDGE_ONLY",
            "reason": f"VIX at {vix:.1f} — crisis mode. Only hedge existing positions.",
        }

    if is_expiry and vix < 18:
        return {
            "strategy": "EXPIRY_SCALP",
            "details": BANK_NIFTY_STRATEGIES["EXPIRY_SCALP"],
            "reason": "Expiry day + low VIX = directional scalp with tight SL",
        }

    if 12 <= vix <= 18 and regime in ("sideways", "normal"):
        return {
            "strategy": "IRON_CONDOR_WEEKLY",
            "details": BANK_NIFTY_STRATEGIES["IRON_CONDOR_WEEKLY"],
            "reason": "Low-moderate VIX + sideways = premium selling sweet spot (72% win rate)",
        }

    if regime == "bull" and vix < 20:
        if 9 <= time_hour < 10:
            return {
                "strategy": "ORB_15min",
                "details": BANK_NIFTY_STRATEGIES["ORB_15min"],
                "reason": "Bullish regime + morning session = ORB breakout",
            }
        return {
            "strategy": "VWAP_RSI",
            "details": BANK_NIFTY_STRATEGIES["VWAP_RSI"],
            "reason": "Bullish regime = buy above VWAP with RSI confirmation",
        }

    if regime == "bear":
        return {
            "strategy": "VWAP_RSI",
            "details": BANK_NIFTY_STRATEGIES["VWAP_RSI"],
            "reason": "Bearish regime = sell below VWAP with RSI confirmation",
        }

    return {
        "strategy": "WAIT",
        "reason": "No clear edge in current conditions. Wait for better setup.",
    }
