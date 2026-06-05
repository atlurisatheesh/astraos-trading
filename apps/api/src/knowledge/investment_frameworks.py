"""AstraOS Knowledge — Investment Strategy Knowledge Base.

Encodes frameworks from 30+ institutional-grade books into
deterministic rules that AI agents use for analysis and signals.

Sources:
- Graham, Dodd, Klarman (Security Analysis)
- Damodaran (Investment Valuation)
- Penman (Financial Statement Analysis)
- Fisher (Common Stocks & Uncommon Profits)
- Schilit (Financial Shenanigans)
- Ilmanen (Expected Returns)
- Natenberg (Option Volatility & Pricing)
- Dalton (Mind Over Markets - Market Profile)
"""

from dataclasses import dataclass, field
from typing import Any


# ── Graham-Dodd Value Screen ──

@dataclass
class GrahamScreen:
    """Benjamin Graham defensive investor criteria (Security Analysis)."""

    pe_ratio: float = 0
    pb_ratio: float = 0
    current_ratio: float = 0
    debt_to_equity: float = 0
    earnings_growth_10y: float = 0
    dividend_years: int = 0
    market_cap_cr: float = 0

    def score(self) -> dict:
        """Score stock against Graham criteria. Returns pass/fail for each."""
        checks = {
            "pe_under_15": self.pe_ratio < 15 and self.pe_ratio > 0,
            "pb_under_1_5": self.pb_ratio < 1.5 and self.pb_ratio > 0,
            "graham_number": (self.pe_ratio * self.pb_ratio) < 22.5 if self.pe_ratio > 0 and self.pb_ratio > 0 else False,
            "current_ratio_above_2": self.current_ratio >= 2.0,
            "low_debt": self.debt_to_equity < 0.5,
            "earnings_growth": self.earnings_growth_10y > 0,
            "dividend_history": self.dividend_years >= 5,
            "adequate_size": self.market_cap_cr >= 500,  # ₹500 Cr minimum
        }
        passed = sum(1 for v in checks.values() if v)
        return {
            "checks": checks,
            "passed": passed,
            "total": len(checks),
            "score": round(passed / len(checks) * 100),
            "verdict": "STRONG_VALUE" if passed >= 6 else "MODERATE_VALUE" if passed >= 4 else "FAIL",
        }


# ── Fisher Quality Screen ──

@dataclass
class FisherScreen:
    """Philip Fisher business quality criteria (Common Stocks & Uncommon Profits)."""

    revenue_growth_3y: float = 0       # CAGR %
    profit_margin: float = 0           # %
    roe: float = 0                     # %
    rd_to_revenue: float = 0           # %
    management_integrity: int = 5      # 1-10 score
    competitive_moat: int = 5          # 1-10 score
    market_potential: int = 5          # 1-10 score

    def score(self) -> dict:
        checks = {
            "strong_revenue_growth": self.revenue_growth_3y > 15,
            "healthy_margins": self.profit_margin > 10,
            "high_roe": self.roe > 15,
            "rd_investment": self.rd_to_revenue > 3,
            "management_quality": self.management_integrity >= 7,
            "durable_moat": self.competitive_moat >= 7,
            "large_addressable_market": self.market_potential >= 7,
        }
        passed = sum(1 for v in checks.values() if v)
        return {
            "checks": checks,
            "passed": passed,
            "total": len(checks),
            "score": round(passed / len(checks) * 100),
            "verdict": "OUTSTANDING" if passed >= 6 else "GOOD" if passed >= 4 else "AVERAGE",
        }


# ── Financial Shenanigans Detector ──

@dataclass
class ShenanigansDetector:
    """Howard Schilit accounting fraud red flags (Financial Shenanigans, 4th Ed)."""

    revenue_growth: float = 0          # %
    cfo_growth: float = 0              # % (cash from operations)
    dso_change: float = 0              # days sales outstanding change
    capex_to_revenue_change: float = 0 # capitalization aggressiveness
    other_income_pct: float = 0        # % of total income
    related_party_pct: float = 0       # % of revenue
    auditor_changed: bool = False
    accounting_policy_changed: bool = False
    inventory_growth_vs_revenue: float = 0  # if inventory grows >> revenue

    def detect(self) -> dict:
        """Detect potential accounting manipulation."""
        red_flags = {
            "revenue_outpacing_cash": self.revenue_growth > self.cfo_growth * 1.5 and self.revenue_growth > 20,
            "rising_dso": self.dso_change > 15,  # 15+ days increase
            "aggressive_capitalization": self.capex_to_revenue_change > 3,
            "suspicious_other_income": self.other_income_pct > 15,
            "related_party_risk": self.related_party_pct > 5,
            "auditor_red_flag": self.auditor_changed,
            "policy_changes": self.accounting_policy_changed,
            "inventory_divergence": self.inventory_growth_vs_revenue > 20,
        }
        flagged = sum(1 for v in red_flags.values() if v)
        return {
            "red_flags": red_flags,
            "flagged": flagged,
            "total_checks": len(red_flags),
            "risk_level": "HIGH" if flagged >= 4 else "MEDIUM" if flagged >= 2 else "LOW",
            "recommendation": "AVOID" if flagged >= 4 else "INVESTIGATE" if flagged >= 2 else "CLEAR",
        }


# ── Damodaran DCF Valuation ──

def damodaran_dcf(
    fcf: float,               # Current Free Cash Flow (₹ Cr)
    growth_rate: float,        # Expected growth rate (decimal, e.g. 0.12)
    terminal_growth: float,    # Terminal growth rate (decimal, e.g. 0.04)
    wacc: float,               # Weighted avg cost of capital (decimal)
    projection_years: int = 10,
    shares_outstanding: float = 1,  # in Cr
) -> dict:
    """Damodaran-style DCF valuation (Investment Valuation, 4th Ed).

    Returns intrinsic value per share + margin-of-safety prices.
    """
    projected_fcf = []
    cf = fcf
    total_pv = 0

    for year in range(1, projection_years + 1):
        cf = cf * (1 + growth_rate)
        pv = cf / ((1 + wacc) ** year)
        projected_fcf.append({"year": year, "fcf": round(cf, 2), "pv": round(pv, 2)})
        total_pv += pv

    # Terminal value (Gordon Growth Model)
    terminal_fcf = cf * (1 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    terminal_pv = terminal_value / ((1 + wacc) ** projection_years)

    enterprise_value = total_pv + terminal_pv
    equity_value = enterprise_value  # Simplified; subtract net debt in production
    intrinsic_per_share = equity_value / shares_outstanding if shares_outstanding > 0 else 0

    return {
        "projected_fcf": projected_fcf,
        "terminal_value": round(terminal_value, 2),
        "terminal_pv": round(terminal_pv, 2),
        "enterprise_value": round(enterprise_value, 2),
        "intrinsic_per_share": round(intrinsic_per_share, 2),
        "buy_price_25_mos": round(intrinsic_per_share * 0.75, 2),  # 25% margin of safety
        "buy_price_40_mos": round(intrinsic_per_share * 0.60, 2),  # 40% margin of safety
        "inputs": {
            "fcf": fcf, "growth": growth_rate, "terminal_growth": terminal_growth,
            "wacc": wacc, "years": projection_years,
        },
    }


# ── Ilmanen Expected Returns Framework ──

@dataclass
class ExpectedReturnDecomposition:
    """Antti Ilmanen factor decomposition (Expected Returns)."""

    # Factor premiums (annualized %)
    equity_risk_premium: float = 6.0
    value_premium: float = 3.0
    momentum_premium: float = 4.0
    size_premium: float = 2.0
    quality_premium: float = 3.0
    low_vol_premium: float = 2.0

    # Portfolio exposures (beta-like loadings)
    market_beta: float = 1.0
    value_loading: float = 0.0
    momentum_loading: float = 0.0
    size_loading: float = 0.0
    quality_loading: float = 0.0
    low_vol_loading: float = 0.0

    def expected_return(self) -> dict:
        """Calculate expected return from factor exposures."""
        risk_free = 6.5  # India 10Y govt bond

        factor_return = (
            self.market_beta * self.equity_risk_premium +
            self.value_loading * self.value_premium +
            self.momentum_loading * self.momentum_premium +
            self.size_loading * self.size_premium +
            self.quality_loading * self.quality_premium +
            self.low_vol_loading * self.low_vol_premium
        )

        total = risk_free + factor_return

        return {
            "risk_free": risk_free,
            "factor_return": round(factor_return, 2),
            "expected_return": round(total, 2),
            "factors": {
                "market": round(self.market_beta * self.equity_risk_premium, 2),
                "value": round(self.value_loading * self.value_premium, 2),
                "momentum": round(self.momentum_loading * self.momentum_premium, 2),
                "size": round(self.size_loading * self.size_premium, 2),
                "quality": round(self.quality_loading * self.quality_premium, 2),
                "low_vol": round(self.low_vol_loading * self.low_vol_premium, 2),
            },
        }
