# type: ignore
"""AstraOS Services — Market Breadth & Heatmap.

Market health indicators:
  - Advance/Decline ratio
  - New 52-week Highs vs Lows
  - Sector heatmap (NIFTY 50 by sector)
  - Market sentiment score
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger()


NIFTY_50_MAP: dict[str, str] = {
    "RELIANCE": "Energy", "TCS": "IT", "HDFCBANK": "Banking", "INFY": "IT",
    "ICICIBANK": "Banking", "HINDUNILVR": "FMCG", "SBIN": "Banking",
    "BHARTIARTL": "Telecom", "ITC": "FMCG", "KOTAKBANK": "Banking",
    "LT": "Infrastructure", "AXISBANK": "Banking", "BAJFINANCE": "Finance",
    "ASIANPAINT": "Consumer", "MARUTI": "Auto", "TATAMOTORS": "Auto",
    "SUNPHARMA": "Pharma", "HCLTECH": "IT", "WIPRO": "IT",
    "ULTRACEMCO": "Cement", "NTPC": "Energy", "POWERGRID": "Energy",
    "TATASTEEL": "Metal", "ONGC": "Energy", "JSWSTEEL": "Metal",
    "TECHM": "IT", "TITAN": "Consumer", "NESTLEIND": "FMCG",
    "COALINDIA": "Mining", "BAJAJ-AUTO": "Auto", "BRITANNIA": "FMCG",
    "CIPLA": "Pharma", "DRREDDY": "Pharma", "APOLLOHOSP": "Healthcare",
    "SBILIFE": "Insurance", "HINDALCO": "Metal", "M&M": "Auto",
    "ADANIPORTS": "Infrastructure", "BPCL": "Energy", "HDFCLIFE": "Insurance",
}


@dataclass
class StockHeatPoint:
    """A single stock in the heatmap."""
    symbol: str
    sector: str
    change_pct: float
    market_cap: float
    last_price: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "sector": self.sector,
            "change_pct": round(self.change_pct, 2),
            "market_cap_cr": round(self.market_cap / 1e7, 0),
            "last_price": round(self.last_price, 2),
            "color": self._color(),
        }

    def _color(self) -> str:
        if self.change_pct > 3:
            return "#00c853"
        elif self.change_pct > 1:
            return "#66bb6a"
        elif self.change_pct > 0:
            return "#a5d6a7"
        elif self.change_pct > -1:
            return "#ef9a9a"
        elif self.change_pct > -3:
            return "#e53935"
        return "#b71c1c"


@dataclass
class MarketBreadth:
    """Market breadth indicators."""
    advances: int = 0
    declines: int = 0
    unchanged: int = 0
    ad_ratio: float = 0.0
    new_highs: int = 0
    new_lows: int = 0
    market_sentiment: str = "neutral"
    sentiment_score: float = 0.0  # -100 to +100
    heatmap: list[StockHeatPoint] = field(default_factory=list)
    sector_performance: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "breadth": {
                "advances": self.advances,
                "declines": self.declines,
                "unchanged": self.unchanged,
                "ad_ratio": round(self.ad_ratio, 2),
                "new_52w_highs": self.new_highs,
                "new_52w_lows": self.new_lows,
            },
            "sentiment": {
                "label": self.market_sentiment,
                "score": round(self.sentiment_score, 1),
            },
            "sector_performance": {k: round(v, 2) for k, v in self.sector_performance.items()},
            "heatmap": [h.to_dict() for h in self.heatmap],
        }


class MarketBreadthService:
    """Compute market breadth and heatmap data."""

    async def get_breadth(self) -> MarketBreadth:
        """Get full market breadth analysis."""
        result = MarketBreadth()
        sector_changes: dict[str, list[float]] = {}

        for symbol, sector in list(NIFTY_50_MAP.items())[:40]:
            try:
                yf_sym = f"{symbol}.NS"
                t = yf.Ticker(yf_sym)
                info = t.info
                price = float(info.get("currentPrice", info.get("regularMarketPrice", 0)))
                prev = float(info.get("previousClose", price))
                mcap = float(info.get("marketCap", 0))
                high52 = float(info.get("fiftyTwoWeekHigh", 0))
                low52 = float(info.get("fiftyTwoWeekLow", 0))

                change = ((price - prev) / prev * 100) if prev > 0 else 0
                if change > 0.05:
                    result.advances += 1
                elif change < -0.05:
                    result.declines += 1
                else:
                    result.unchanged += 1

                if price >= high52 * 0.98:
                    result.new_highs += 1
                if price <= low52 * 1.02:
                    result.new_lows += 1

                result.heatmap.append(StockHeatPoint(
                    symbol=symbol, sector=sector,
                    change_pct=change, market_cap=mcap, last_price=price,
                ))
                sector_changes.setdefault(sector, []).append(change)

            except Exception as e:
                logger.debug("Breadth stock failed", symbol=symbol, error=str(e))

        # A/D ratio
        if result.declines > 0:
            result.ad_ratio = result.advances / result.declines
        else:
            result.ad_ratio = result.advances or 0

        # Sector averages
        for sector, changes in sector_changes.items():
            result.sector_performance[sector] = sum(changes) / len(changes)

        # Sentiment calculation
        total = result.advances + result.declines + result.unchanged
        if total > 0:
            result.sentiment_score = ((result.advances - result.declines) / total) * 100
        if result.sentiment_score > 30:
            result.market_sentiment = "strongly_bullish"
        elif result.sentiment_score > 10:
            result.market_sentiment = "bullish"
        elif result.sentiment_score > -10:
            result.market_sentiment = "neutral"
        elif result.sentiment_score > -30:
            result.market_sentiment = "bearish"
        else:
            result.market_sentiment = "strongly_bearish"

        # Sort heatmap by market cap
        result.heatmap.sort(key=lambda h: h.market_cap, reverse=True)

        return result


_service: Optional[MarketBreadthService] = None

def get_market_breadth_service() -> MarketBreadthService:
    global _service
    if _service is None:
        _service = MarketBreadthService()
    return _service
