"""AstraOS Risk — Kelly Criterion Position Sizing.

Never risk more than Half-Kelly. The system that survives is the one that
controls losses — not the one that maximizes wins.

Kelly Criterion:  f* = (p/b) - (q/a)
  where p = win rate, q = loss rate, a = avg loss, b = avg win

Half-Kelly is used because:
  1. Full Kelly assumes perfect edge estimation (we don't have that)
  2. Drawdowns under full Kelly are psychologically unbearable
  3. Half-Kelly gives ~75% of the growth rate with ~50% of the drawdown
"""

from dataclasses import dataclass
from decimal import Decimal

import structlog

logger = structlog.get_logger()


@dataclass
class PositionSize:
    quantity: int
    position_value: float
    risk_per_trade: float
    risk_pct_of_capital: float
    kelly_fraction: float
    method: str
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "quantity": self.quantity,
            "position_value": round(self.position_value, 2),
            "risk_per_trade": round(self.risk_per_trade, 2),
            "risk_pct_of_capital": round(self.risk_pct_of_capital, 4),
            "kelly_fraction": round(self.kelly_fraction, 4),
            "method": self.method,
            "reasoning": self.reasoning,
        }


def calculate_kelly_fraction(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> float:
    """Calculate the Half-Kelly fraction.

    Returns a value between 0 and 0.25 (hard-capped for safety).
    """
    if win_rate <= 0 or win_rate >= 1 or avg_win <= 0 or avg_loss <= 0:
        return 0.0

    p = win_rate
    q = 1 - win_rate

    # Kelly formula: f* = p/loss - q/win = (p*win - q*loss) / (win*loss)
    kelly = (p * avg_win - q * avg_loss) / (avg_win * avg_loss) if avg_win * avg_loss > 0 else 0

    if kelly <= 0:
        return 0.0

    half_kelly = kelly / 2
    # Hard cap at 25% of capital (even if Kelly says more)
    return min(half_kelly, 0.25)


def calculate_position_size(
    capital: float,
    entry_price: float,
    stop_loss: float,
    confidence: float,
    win_rate: float = 0.55,
    avg_win: float = 1500.0,
    avg_loss: float = 800.0,
    max_risk_pct: float = 2.0,
    lot_size: int = 1,
) -> PositionSize:
    """Calculate optimal position size using Half-Kelly with ATR-based risk.

    Args:
        capital: Total trading capital
        entry_price: Planned entry price
        stop_loss: Stop-loss price
        confidence: Signal confidence (0-100)
        win_rate: Historical win rate (0-1)
        avg_win: Average winning trade P&L
        avg_loss: Average losing trade P&L
        max_risk_pct: Maximum risk per trade as % of capital
        lot_size: Minimum lot size (for F&O instruments)
    """
    if entry_price <= 0 or capital <= 0:
        return PositionSize(0, 0, 0, 0, 0, "rejected", "Invalid entry price or capital")

    risk_per_unit = abs(entry_price - stop_loss)
    if risk_per_unit <= 0:
        return PositionSize(0, 0, 0, 0, 0, "rejected", "Stop loss equals entry price")

    kelly = calculate_kelly_fraction(win_rate, avg_win, avg_loss)

    if kelly <= 0:
        return PositionSize(0, 0, 0, 0, 0, "no_edge", "Negative edge — Kelly says do not trade")

    # Scale Kelly by confidence (higher confidence → closer to full Half-Kelly)
    confidence_scalar = min(confidence / 100, 1.0)
    adjusted_kelly = kelly * confidence_scalar

    # Capital at risk
    risk_capital = capital * adjusted_kelly

    # Hard cap: never risk more than max_risk_pct of capital
    max_risk = capital * max_risk_pct / 100
    risk_capital = min(risk_capital, max_risk)

    # Calculate quantity from risk
    quantity = int(risk_capital / risk_per_unit)

    # Round to lot size
    if lot_size > 1:
        quantity = (quantity // lot_size) * lot_size

    if quantity <= 0:
        return PositionSize(0, 0, 0, 0, kelly, "too_small", "Position size too small for lot size")

    position_value = quantity * entry_price
    actual_risk = quantity * risk_per_unit
    risk_pct = actual_risk / capital * 100

    method = "half_kelly_atr"
    reasoning = (
        f"Half-Kelly={kelly:.4f}, confidence-adjusted={adjusted_kelly:.4f}, "
        f"risk/unit={risk_per_unit:.2f}, qty={quantity}"
    )

    return PositionSize(
        quantity=quantity,
        position_value=position_value,
        risk_per_trade=actual_risk,
        risk_pct_of_capital=risk_pct,
        kelly_fraction=kelly,
        method=method,
        reasoning=reasoning,
    )


def check_correlation_limit(
    new_symbol: str,
    new_sector: str,
    existing_positions: list[dict],
    max_sector_pct: float = 30.0,
    capital: float = 1_000_000.0,
) -> tuple[bool, str]:
    """Check if adding a position would breach sector concentration limits.

    Returns (allowed, reason).
    """
    sector_exposure: dict[str, float] = {}
    for pos in existing_positions:
        sector = pos.get("sector", "unknown")
        value = pos.get("position_value", 0)
        sector_exposure[sector] = sector_exposure.get(sector, 0) + value

    current_sector_value = sector_exposure.get(new_sector, 0)
    current_pct = (current_sector_value / capital * 100) if capital > 0 else 0

    if current_pct >= max_sector_pct:
        return False, (
            f"Sector '{new_sector}' already at {current_pct:.1f}% of capital "
            f"(limit: {max_sector_pct:.0f}%)"
        )

    # Check for identical symbol
    same_symbol = [p for p in existing_positions if p.get("symbol") == new_symbol]
    if same_symbol:
        return False, f"Already have an open position in {new_symbol}"

    # Check total number of correlated positions (same sector)
    same_sector = [p for p in existing_positions if p.get("sector") == new_sector]
    if len(same_sector) >= 2:
        return False, (
            f"Already have {len(same_sector)} positions in '{new_sector}' sector — "
            f"adding more increases correlation risk"
        )

    return True, "OK"
