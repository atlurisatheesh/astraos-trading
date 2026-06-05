# type: ignore
"""AstraOS Services — Sector Rotation Model.

Tracks NIFTY sectoral index performance to identify which sectors are
gaining/losing momentum. Auto-rotates the watchlist to trending sectors.

Monitors 12 NIFTY sectoral indices:
  Auto, Bank, Energy, FMCG, IT, Media, Metal, Pharma, PSE, Realty,
  Private Bank, Infrastructure

Metrics:
  - 1-day, 5-day, 1-month relative strength vs NIFTY 50
  - Sector momentum score (composite)
  - Rotation phase: Leading / Weakening / Lagging / Improving
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger()


SECTORAL_INDICES: dict[str, str] = {
    "NIFTY AUTO": "^CNXAUTO",
    "NIFTY BANK": "^NSEBANK",
    "NIFTY ENERGY": "^CNXENERGY",
    "NIFTY FMCG": "^CNXFMCG",
    "NIFTY IT": "^CNXIT",
    "NIFTY MEDIA": "^CNXMEDIA",
    "NIFTY METAL": "^CNXMETAL",
    "NIFTY PHARMA": "^CNXPHARMA",
    "NIFTY PSE": "^CNXPSE",
    "NIFTY REALTY": "^CNXREALTY",
    "NIFTY PVT BANK": "^NIFPVTBNK",
    "NIFTY INFRA": "^CNXINFRA",
}

NIFTY_50_SYMBOL = "^NSEI"


@dataclass
class SectorMetrics:
    """Performance metrics for a single sector."""
    name: str
    symbol: str
    last_price: float = 0.0
    change_1d_pct: float = 0.0
    change_5d_pct: float = 0.0
    change_1m_pct: float = 0.0
    change_3m_pct: float = 0.0
    relative_strength_1m: float = 0.0  # vs NIFTY 50
    momentum_score: float = 0.0  # composite
    rotation_phase: str = "neutral"  # leading / weakening / lagging / improving

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "symbol": self.symbol,
            "last_price": self.last_price,
            "performance": {
                "1d": round(self.change_1d_pct, 2),
                "5d": round(self.change_5d_pct, 2),
                "1m": round(self.change_1m_pct, 2),
                "3m": round(self.change_3m_pct, 2),
            },
            "relative_strength_1m": round(self.relative_strength_1m, 2),
            "momentum_score": round(self.momentum_score, 2),
            "rotation_phase": self.rotation_phase,
        }


@dataclass
class SectorRotationAnalysis:
    """Complete sector rotation analysis."""
    sectors: list[SectorMetrics] = field(default_factory=list)
    leading_sectors: list[str] = field(default_factory=list)
    lagging_sectors: list[str] = field(default_factory=list)
    nifty_1m_change: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "sectors": [s.to_dict() for s in self.sectors],
            "leading": self.leading_sectors,
            "lagging": self.lagging_sectors,
            "nifty_benchmark": {"1m_change": round(self.nifty_1m_change, 2)},
            "recommendation": self._recommendation(),
            "timestamp": self.timestamp,
        }

    def _recommendation(self) -> str:
        if self.leading_sectors:
            return f"Rotate into: {', '.join(self.leading_sectors[:3])}"
        return "No clear sector rotation signal — stay diversified"


class SectorRotationService:
    """Analyze sector rotation using NIFTY sectoral indices."""

    async def analyze(self) -> SectorRotationAnalysis:
        """Run full sector rotation analysis."""
        analysis = SectorRotationAnalysis(timestamp=datetime.now(timezone.utc).isoformat())

        # Fetch NIFTY 50 benchmark
        nifty_data = self._fetch_returns(NIFTY_50_SYMBOL)
        analysis.nifty_1m_change = nifty_data.get("1m", 0.0)

        # Fetch all sectors
        for name, symbol in SECTORAL_INDICES.items():
            try:
                returns = self._fetch_returns(symbol)
                ticker = yf.Ticker(symbol)
                info = ticker.info
                last_price = float(info.get("regularMarketPrice", info.get("previousClose", 0)))

                rs_1m = returns.get("1m", 0) - analysis.nifty_1m_change

                # Momentum score: weighted composite
                momentum = (
                    returns.get("1d", 0) * 0.1 +
                    returns.get("5d", 0) * 0.2 +
                    returns.get("1m", 0) * 0.4 +
                    returns.get("3m", 0) * 0.3
                )

                # Rotation phase classification
                phase = self._classify_phase(
                    rs_1m=rs_1m,
                    momentum=momentum,
                    change_1m=returns.get("1m", 0),
                )

                sector = SectorMetrics(
                    name=name,
                    symbol=symbol,
                    last_price=last_price,
                    change_1d_pct=returns.get("1d", 0),
                    change_5d_pct=returns.get("5d", 0),
                    change_1m_pct=returns.get("1m", 0),
                    change_3m_pct=returns.get("3m", 0),
                    relative_strength_1m=rs_1m,
                    momentum_score=momentum,
                    rotation_phase=phase,
                )
                analysis.sectors.append(sector)

            except Exception as e:
                logger.warning("Sector analysis failed", sector=name, error=str(e))

        # Sort by momentum
        analysis.sectors.sort(key=lambda s: s.momentum_score, reverse=True)

        # Classify leading/lagging
        analysis.leading_sectors = [
            s.name for s in analysis.sectors if s.rotation_phase == "leading"
        ][:5]
        analysis.lagging_sectors = [
            s.name for s in analysis.sectors if s.rotation_phase == "lagging"
        ][:5]

        return analysis

    def _fetch_returns(self, symbol: str) -> dict[str, float]:
        """Fetch return percentages for different periods."""
        returns: dict[str, float] = {}
        try:
            df = yf.download(symbol, period="3mo", interval="1d", progress=False)
            if df.empty:
                return returns

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            close = df["Close"]
            if len(close) < 2:
                return returns

            last = float(close.iloc[-1])

            if len(close) >= 2:
                returns["1d"] = float((last / float(close.iloc[-2]) - 1) * 100)
            if len(close) >= 5:
                returns["5d"] = float((last / float(close.iloc[-5]) - 1) * 100)
            if len(close) >= 22:
                returns["1m"] = float((last / float(close.iloc[-22]) - 1) * 100)
            if len(close) >= 63:
                returns["3m"] = float((last / float(close.iloc[-63]) - 1) * 100)
            elif len(close) >= 2:
                returns["3m"] = float((last / float(close.iloc[0]) - 1) * 100)

        except Exception as e:
            logger.debug("Return calculation failed", symbol=symbol, error=str(e))

        return returns

    @staticmethod
    def _classify_phase(rs_1m: float, momentum: float, change_1m: float) -> str:
        """Classify sector rotation phase.

        - Leading: High RS + positive momentum (outperforming market, rising)
        - Weakening: High RS + negative momentum (outperforming but slowing)
        - Lagging: Low RS + negative momentum (underperforming, falling)
        - Improving: Low RS + positive momentum (underperforming but recovering)
        """
        if rs_1m > 1 and momentum > 0:
            return "leading"
        elif rs_1m > 0 and momentum <= 0:
            return "weakening"
        elif rs_1m < -1 and momentum < 0:
            return "lagging"
        elif rs_1m <= 0 and momentum > 0:
            return "improving"
        return "neutral"


# ── Factory ─────────────────────────────────────────────────

_service: Optional[SectorRotationService] = None


def get_sector_rotation_service() -> SectorRotationService:
    global _service
    if _service is None:
        _service = SectorRotationService()
    return _service
