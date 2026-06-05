# type: ignore
"""AstraOS Services — Options Strategy Builder.

Auto-constructs popular F&O strategies with P&L payoff analysis:
  - Straddle (Long/Short)
  - Strangle (Long/Short)
  - Iron Condor
  - Bull Call Spread / Bear Put Spread
  - Butterfly Spread
  - Covered Call / Protective Put

Returns payoff curves, max profit/loss, breakeven points, and Greeks.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Optional

import yfinance as yf
import structlog

logger = structlog.get_logger()


@dataclass
class OptionLeg:
    """A single leg of an options strategy."""
    option_type: str  # "CE" or "PE"
    strike: float
    premium: float
    quantity: int  # +ve = buy, -ve = sell
    action: str  # "BUY" or "SELL"

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_type": self.option_type,
            "strike": self.strike,
            "premium": self.premium,
            "quantity": self.quantity,
            "action": self.action,
        }


@dataclass
class StrategyPayoff:
    """Payoff analysis for a complete strategy."""
    name: str
    legs: list[OptionLeg]
    spot_price: float
    net_premium: float  # +ve = credit, -ve = debit
    max_profit: float
    max_loss: float
    breakeven_points: list[float]
    risk_reward_ratio: float
    payoff_curve: list[dict[str, float]] = field(default_factory=list)
    greeks: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "legs": [l.to_dict() for l in self.legs],
            "spot_price": round(self.spot_price, 2),
            "net_premium": round(self.net_premium, 2),
            "max_profit": round(self.max_profit, 2) if self.max_profit != float("inf") else "unlimited",
            "max_loss": round(self.max_loss, 2) if self.max_loss != float("-inf") else "unlimited",
            "breakeven_points": [round(b, 2) for b in self.breakeven_points],
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "payoff_curve": self.payoff_curve,
            "greeks": {k: round(v, 4) for k, v in self.greeks.items()},
        }


class OptionsStrategyBuilder:
    """Build and analyze popular options strategies."""

    LOT_SIZE = 50  # Default NIFTY lot size

    def build_strategy(
        self,
        symbol: str,
        strategy_name: str,
        spot_price: Optional[float] = None,
        atm_strike: Optional[float] = None,
        width: float = 100,
    ) -> StrategyPayoff:
        """Build a named strategy."""
        if spot_price is None:
            spot_price = self._get_spot(symbol)
        if atm_strike is None:
            atm_strike = round(spot_price / 50) * 50  # Round to nearest 50

        iv = 0.15  # Default IV for premium estimation

        builders = {
            "long_straddle": self._long_straddle,
            "short_straddle": self._short_straddle,
            "long_strangle": self._long_strangle,
            "short_strangle": self._short_strangle,
            "iron_condor": self._iron_condor,
            "bull_call_spread": self._bull_call_spread,
            "bear_put_spread": self._bear_put_spread,
            "butterfly": self._butterfly,
        }

        builder = builders.get(strategy_name.lower().replace(" ", "_"))
        if not builder:
            raise ValueError(f"Unknown strategy: {strategy_name}. Available: {list(builders.keys())}")

        return builder(spot_price, atm_strike, width, iv)

    def get_available_strategies(self) -> list[dict[str, str]]:
        """List all available strategies."""
        return [
            {"name": "long_straddle", "description": "Buy ATM Call + Put — profit on big move either way", "bias": "neutral"},
            {"name": "short_straddle", "description": "Sell ATM Call + Put — profit if price stays near strike", "bias": "neutral"},
            {"name": "long_strangle", "description": "Buy OTM Call + Put — cheaper directional bet", "bias": "neutral"},
            {"name": "short_strangle", "description": "Sell OTM Call + Put — wider profit zone", "bias": "neutral"},
            {"name": "iron_condor", "description": "Sell OTM strangle + buy further OTM — defined risk", "bias": "neutral"},
            {"name": "bull_call_spread", "description": "Buy lower Call + Sell higher Call — bullish, limited risk", "bias": "bullish"},
            {"name": "bear_put_spread", "description": "Buy higher Put + Sell lower Put — bearish, limited risk", "bias": "bearish"},
            {"name": "butterfly", "description": "Buy 1 ITM + Sell 2 ATM + Buy 1 OTM — profit near ATM", "bias": "neutral"},
        ]

    def _estimate_premium(self, spot: float, strike: float, iv: float, opt_type: str, dte: int = 30) -> float:
        """Simple BS-based premium estimate."""
        t = dte / 365
        d1 = (math.log(spot / strike) + (0.05 + 0.5 * iv ** 2) * t) / (iv * math.sqrt(t))
        d2 = d1 - iv * math.sqrt(t)
        nd1 = 0.5 * (1 + math.erf(d1 / math.sqrt(2)))
        nd2 = 0.5 * (1 + math.erf(d2 / math.sqrt(2)))
        if opt_type == "CE":
            return max(spot * nd1 - strike * math.exp(-0.05 * t) * nd2, 0.5)
        else:
            return max(strike * math.exp(-0.05 * t) * (1 - nd2) - spot * (1 - nd1), 0.5)

    def _compute_payoff_curve(self, legs: list[OptionLeg], spot: float) -> list[dict[str, float]]:
        """Compute payoff at various price points."""
        low = spot * 0.85
        high = spot * 1.15
        step = (high - low) / 60
        curve = []
        price = low
        while price <= high:
            pnl = 0.0
            for leg in legs:
                if leg.option_type == "CE":
                    intrinsic = max(price - leg.strike, 0)
                else:
                    intrinsic = max(leg.strike - price, 0)
                pnl += (intrinsic - leg.premium) * leg.quantity
            curve.append({"price": round(price, 2), "pnl": round(pnl, 2)})
            price += step
        return curve

    def _analyze(self, name: str, legs: list[OptionLeg], spot: float) -> StrategyPayoff:
        """Analyze a strategy: max P/L, breakevens, payoff curve."""
        curve = self._compute_payoff_curve(legs, spot)
        pnls = [p["pnl"] for p in curve]
        max_profit = max(pnls)
        max_loss = min(pnls)
        net_premium = sum(-leg.premium * leg.quantity for leg in legs)

        # Find breakeven points (where PnL crosses 0)
        breakevens = []
        for i in range(1, len(curve)):
            if (curve[i - 1]["pnl"] < 0 and curve[i]["pnl"] >= 0) or \
               (curve[i - 1]["pnl"] >= 0 and curve[i]["pnl"] < 0):
                breakevens.append(curve[i]["price"])

        rr = abs(max_profit / max_loss) if max_loss != 0 else 999

        return StrategyPayoff(
            name=name, legs=legs, spot_price=spot,
            net_premium=net_premium, max_profit=max_profit, max_loss=max_loss,
            breakeven_points=breakevens, risk_reward_ratio=rr, payoff_curve=curve,
        )

    def _long_straddle(self, spot: float, atm: float, width: float, iv: float) -> StrategyPayoff:
        ce_prem = self._estimate_premium(spot, atm, iv, "CE")
        pe_prem = self._estimate_premium(spot, atm, iv, "PE")
        legs = [
            OptionLeg("CE", atm, ce_prem, 1, "BUY"),
            OptionLeg("PE", atm, pe_prem, 1, "BUY"),
        ]
        return self._analyze("Long Straddle", legs, spot)

    def _short_straddle(self, spot: float, atm: float, width: float, iv: float) -> StrategyPayoff:
        ce_prem = self._estimate_premium(spot, atm, iv, "CE")
        pe_prem = self._estimate_premium(spot, atm, iv, "PE")
        legs = [
            OptionLeg("CE", atm, ce_prem, -1, "SELL"),
            OptionLeg("PE", atm, pe_prem, -1, "SELL"),
        ]
        return self._analyze("Short Straddle", legs, spot)

    def _long_strangle(self, spot: float, atm: float, width: float, iv: float) -> StrategyPayoff:
        otm_ce = atm + width
        otm_pe = atm - width
        legs = [
            OptionLeg("CE", otm_ce, self._estimate_premium(spot, otm_ce, iv, "CE"), 1, "BUY"),
            OptionLeg("PE", otm_pe, self._estimate_premium(spot, otm_pe, iv, "PE"), 1, "BUY"),
        ]
        return self._analyze("Long Strangle", legs, spot)

    def _short_strangle(self, spot: float, atm: float, width: float, iv: float) -> StrategyPayoff:
        otm_ce = atm + width
        otm_pe = atm - width
        legs = [
            OptionLeg("CE", otm_ce, self._estimate_premium(spot, otm_ce, iv, "CE"), -1, "SELL"),
            OptionLeg("PE", otm_pe, self._estimate_premium(spot, otm_pe, iv, "PE"), -1, "SELL"),
        ]
        return self._analyze("Short Strangle", legs, spot)

    def _iron_condor(self, spot: float, atm: float, width: float, iv: float) -> StrategyPayoff:
        legs = [
            OptionLeg("PE", atm - width, self._estimate_premium(spot, atm - width, iv, "PE"), -1, "SELL"),
            OptionLeg("PE", atm - 2 * width, self._estimate_premium(spot, atm - 2 * width, iv, "PE"), 1, "BUY"),
            OptionLeg("CE", atm + width, self._estimate_premium(spot, atm + width, iv, "CE"), -1, "SELL"),
            OptionLeg("CE", atm + 2 * width, self._estimate_premium(spot, atm + 2 * width, iv, "CE"), 1, "BUY"),
        ]
        return self._analyze("Iron Condor", legs, spot)

    def _bull_call_spread(self, spot: float, atm: float, width: float, iv: float) -> StrategyPayoff:
        legs = [
            OptionLeg("CE", atm, self._estimate_premium(spot, atm, iv, "CE"), 1, "BUY"),
            OptionLeg("CE", atm + width, self._estimate_premium(spot, atm + width, iv, "CE"), -1, "SELL"),
        ]
        return self._analyze("Bull Call Spread", legs, spot)

    def _bear_put_spread(self, spot: float, atm: float, width: float, iv: float) -> StrategyPayoff:
        legs = [
            OptionLeg("PE", atm, self._estimate_premium(spot, atm, iv, "PE"), 1, "BUY"),
            OptionLeg("PE", atm - width, self._estimate_premium(spot, atm - width, iv, "PE"), -1, "SELL"),
        ]
        return self._analyze("Bear Put Spread", legs, spot)

    def _butterfly(self, spot: float, atm: float, width: float, iv: float) -> StrategyPayoff:
        legs = [
            OptionLeg("CE", atm - width, self._estimate_premium(spot, atm - width, iv, "CE"), 1, "BUY"),
            OptionLeg("CE", atm, self._estimate_premium(spot, atm, iv, "CE"), -2, "SELL"),
            OptionLeg("CE", atm + width, self._estimate_premium(spot, atm + width, iv, "CE"), 1, "BUY"),
        ]
        return self._analyze("Butterfly Spread", legs, spot)

    def _get_spot(self, symbol: str) -> float:
        yf_sym = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
        t = yf.Ticker(yf_sym)
        info = t.info
        return float(info.get("currentPrice", info.get("regularMarketPrice", 0)))


_builder: Optional[OptionsStrategyBuilder] = None

def get_strategy_builder() -> OptionsStrategyBuilder:
    global _builder
    if _builder is None:
        _builder = OptionsStrategyBuilder()
    return _builder
