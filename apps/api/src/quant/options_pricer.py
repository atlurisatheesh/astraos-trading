"""AstraOS Quant — Options Pricer (Black-Scholes + Greeks, free)."""

import math
from decimal import Decimal
from dataclasses import dataclass
from scipy.stats import norm


@dataclass
class GreeksResult:
    """Option Greeks calculation result."""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    price: float

    def to_dict(self) -> dict:
        return {
            "delta": round(self.delta, 4),
            "gamma": round(self.gamma, 6),
            "theta": round(self.theta, 4),
            "vega": round(self.vega, 4),
            "rho": round(self.rho, 4),
            "price": round(self.price, 2),
        }


def black_scholes(
    spot: float, strike: float, time_to_expiry: float,
    risk_free_rate: float, volatility: float, option_type: str = "CE"
) -> GreeksResult:
    """Calculate option price and Greeks using Black-Scholes model.

    Args:
        spot: Current underlying price
        strike: Option strike price
        time_to_expiry: Time to expiry in years (e.g., 7/365 for 7 days)
        risk_free_rate: Annual risk-free rate (e.g., 0.065 for 6.5%)
        volatility: Implied volatility (e.g., 0.15 for 15%)
        option_type: "CE" for Call, "PE" for Put
    """
    if time_to_expiry <= 0 or volatility <= 0:
        intrinsic = max(0, spot - strike) if option_type == "CE" else max(0, strike - spot)
        return GreeksResult(
            delta=1.0 if option_type == "CE" and spot > strike else -1.0 if option_type == "PE" and spot < strike else 0.0,
            gamma=0.0, theta=0.0, vega=0.0, rho=0.0, price=intrinsic,
        )

    S, K, T, r, sigma = spot, strike, time_to_expiry, risk_free_rate, volatility

    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "CE":
        price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
        rho = K * T * math.exp(-r * T) * norm.cdf(d2) / 100
    else:
        price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
        rho = -K * T * math.exp(-r * T) * norm.cdf(-d2) / 100

    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    theta = (-(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
             - r * K * math.exp(-r * T) * norm.cdf(d2 if option_type == "CE" else -d2)) / 365
    vega = S * norm.pdf(d1) * math.sqrt(T) / 100

    return GreeksResult(
        delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho, price=price,
    )


def calculate_max_pain(strikes: list[float], call_oi: list[int], put_oi: list[int]) -> float:
    """Calculate max pain — the strike where option writers lose least.

    Max pain = strike with minimum total value of calls + puts at expiry.
    """
    min_pain = float("inf")
    max_pain_strike = strikes[0]

    for i, settlement in enumerate(strikes):
        total_pain = 0
        for j, strike in enumerate(strikes):
            # Call pain: how much call buyers make
            if settlement > strike and j < len(call_oi):
                total_pain += call_oi[j] * (settlement - strike)
            # Put pain: how much put buyers make
            if settlement < strike and j < len(put_oi):
                total_pain += put_oi[j] * (strike - settlement)

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = settlement

    return max_pain_strike


def calculate_pcr(total_put_oi: int, total_call_oi: int) -> float:
    """Calculate Put-Call Ratio from OI data."""
    if total_call_oi == 0:
        return 0.0
    return round(total_put_oi / total_call_oi, 2)
