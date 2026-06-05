# type: ignore
"""AstraOS Services — Portfolio Correlation Matrix.

Computes pairwise correlation between portfolio holdings to identify
concentration risk and diversification opportunities.
"""

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger()


@dataclass
class CorrelationResult:
    """Portfolio correlation analysis."""
    symbols: list[str]
    matrix: list[list[float]]  # NxN correlation matrix
    high_correlations: list[dict[str, Any]]  # pairs > 0.7
    diversification_score: float  # 0-100 (higher = more diversified)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbols": self.symbols,
            "matrix": self.matrix,
            "high_correlations": self.high_correlations,
            "diversification_score": round(self.diversification_score, 1),
            "assessment": self._assess(),
        }

    def _assess(self) -> str:
        if self.diversification_score > 70:
            return "Well diversified — low portfolio concentration risk"
        elif self.diversification_score > 40:
            return "Moderate diversification — consider adding uncorrelated assets"
        return "Highly concentrated — significant correlation risk"


class PortfolioCorrelationService:
    """Compute portfolio correlation analysis."""

    async def analyze(self, symbols: list[str], period: str = "6mo") -> CorrelationResult:
        """Compute correlation matrix for a list of symbols."""
        yf_symbols = [f"{s}.NS" if not s.endswith(".NS") and not s.startswith("^") else s for s in symbols]
        clean_symbols = [s.replace(".NS", "") for s in symbols]

        # Download all at once
        prices: dict[str, pd.Series] = {}
        for sym, clean in zip(yf_symbols, clean_symbols):
            try:
                df = yf.download(sym, period=period, interval="1d", progress=False)
                if not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    prices[clean] = df["Close"]
            except Exception:
                continue

        if len(prices) < 2:
            return CorrelationResult(symbols=list(prices.keys()), matrix=[], high_correlations=[], diversification_score=100)

        # Build returns DataFrame
        returns_df = pd.DataFrame({s: p.pct_change().dropna() for s, p in prices.items()})
        returns_df = returns_df.dropna()

        # Correlation matrix
        corr = returns_df.corr()
        matrix = corr.values.tolist()
        syms = list(corr.columns)

        # Find high correlations
        high_corr: list[dict[str, Any]] = []
        n = len(syms)
        for i in range(n):
            for j in range(i + 1, n):
                c = float(corr.iloc[i, j])
                if abs(c) > 0.65:
                    high_corr.append({
                        "pair": f"{syms[i]} — {syms[j]}",
                        "correlation": round(c, 3),
                        "risk": "HIGH" if abs(c) > 0.8 else "MODERATE",
                    })

        high_corr.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        # Diversification score: avg of (1 - |corr|) * 100
        upper_triangle = []
        for i in range(n):
            for j in range(i + 1, n):
                upper_triangle.append(abs(float(corr.iloc[i, j])))

        avg_corr = sum(upper_triangle) / len(upper_triangle) if upper_triangle else 0
        div_score = (1 - avg_corr) * 100

        return CorrelationResult(
            symbols=syms, matrix=[[round(v, 3) for v in row] for row in matrix],
            high_correlations=high_corr, diversification_score=div_score,
        )


_service: Optional[PortfolioCorrelationService] = None

def get_correlation_service() -> PortfolioCorrelationService:
    global _service
    if _service is None:
        _service = PortfolioCorrelationService()
    return _service
