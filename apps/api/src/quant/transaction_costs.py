"""AstraOS Quant — Indian Market Transaction Cost Model.

Accurate cost modelling for NSE/BSE trades including brokerage, taxes,
exchange fees, and realistic slippage estimation.

Sources:
  - SEBI circular on charges (updated FY2024-25)
  - Zerodha, Angel One, Upstox published fee schedules
  - Empirical slippage from Bank Nifty bid-ask spread data
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


class Segment(Enum):
    EQUITY_DELIVERY = "equity_delivery"
    EQUITY_INTRADAY = "equity_intraday"
    FUTURES = "futures"
    OPTIONS = "options"


class Broker(Enum):
    ZERODHA = "zerodha"
    ANGEL_ONE = "angel_one"
    UPSTOX = "upstox"
    FYERS = "fyers"
    GROWW = "groww"
    FIVE_PAISA = "five_paisa"
    PAPER = "paper"


@dataclass(frozen=True)
class BrokerFeeSchedule:
    flat_per_order: Decimal = Decimal("20")
    pct_of_turnover: Decimal = Decimal("0")
    max_brokerage: Decimal = Decimal("20")


BROKER_FEES: dict[Broker, dict[Segment, BrokerFeeSchedule]] = {
    Broker.ZERODHA: {
        Segment.EQUITY_DELIVERY: BrokerFeeSchedule(flat_per_order=Decimal("0"), pct_of_turnover=Decimal("0")),
        Segment.EQUITY_INTRADAY: BrokerFeeSchedule(flat_per_order=Decimal("20")),
        Segment.FUTURES: BrokerFeeSchedule(flat_per_order=Decimal("20")),
        Segment.OPTIONS: BrokerFeeSchedule(flat_per_order=Decimal("20")),
    },
    Broker.ANGEL_ONE: {
        Segment.EQUITY_DELIVERY: BrokerFeeSchedule(flat_per_order=Decimal("0")),
        Segment.EQUITY_INTRADAY: BrokerFeeSchedule(flat_per_order=Decimal("20")),
        Segment.FUTURES: BrokerFeeSchedule(flat_per_order=Decimal("20")),
        Segment.OPTIONS: BrokerFeeSchedule(flat_per_order=Decimal("20")),
    },
    Broker.UPSTOX: {
        Segment.EQUITY_DELIVERY: BrokerFeeSchedule(flat_per_order=Decimal("0")),
        Segment.EQUITY_INTRADAY: BrokerFeeSchedule(flat_per_order=Decimal("20")),
        Segment.FUTURES: BrokerFeeSchedule(flat_per_order=Decimal("20")),
        Segment.OPTIONS: BrokerFeeSchedule(flat_per_order=Decimal("20")),
    },
    Broker.PAPER: {
        Segment.EQUITY_DELIVERY: BrokerFeeSchedule(flat_per_order=Decimal("0")),
        Segment.EQUITY_INTRADAY: BrokerFeeSchedule(flat_per_order=Decimal("20")),
        Segment.FUTURES: BrokerFeeSchedule(flat_per_order=Decimal("20")),
        Segment.OPTIONS: BrokerFeeSchedule(flat_per_order=Decimal("20")),
    },
}

# Default for brokers not explicitly listed
_DEFAULT_FEE = BrokerFeeSchedule(flat_per_order=Decimal("20"))


@dataclass
class TaxBreakdown:
    brokerage: Decimal = Decimal("0")
    stt: Decimal = Decimal("0")
    exchange_txn_charge: Decimal = Decimal("0")
    sebi_fees: Decimal = Decimal("0")
    stamp_duty: Decimal = Decimal("0")
    gst: Decimal = Decimal("0")
    slippage: Decimal = Decimal("0")
    total: Decimal = Decimal("0")

    def to_dict(self) -> dict:
        return {k: float(v) for k, v in self.__dict__.items()}


def _q(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_trade_costs(
    turnover: float,
    segment: Segment,
    broker: Broker = Broker.ZERODHA,
    is_buy: bool = True,
    lots: int = 1,
    bid_ask_spread: float | None = None,
) -> TaxBreakdown:
    """Calculate all-in trade costs for a single leg (buy or sell).

    Args:
        turnover: Total trade value (price * quantity)
        segment: Market segment
        broker: Broker for fee schedule lookup
        is_buy: True for buy side, False for sell side
        lots: Number of F&O lots (for slippage scaling)
        bid_ask_spread: Observed bid-ask spread in rupees (None = estimate)
    """
    tv = Decimal(str(turnover))

    fees = BROKER_FEES.get(broker, {}).get(segment, _DEFAULT_FEE)
    brokerage = min(fees.flat_per_order, fees.max_brokerage)

    # STT (Securities Transaction Tax) — FY2024-25 rates
    if segment == Segment.EQUITY_DELIVERY:
        stt = tv * Decimal("0.001") if is_buy else tv * Decimal("0.001")
    elif segment == Segment.EQUITY_INTRADAY:
        stt = tv * Decimal("0.00025") if not is_buy else Decimal("0")
    elif segment == Segment.FUTURES:
        stt = tv * Decimal("0.000125") if not is_buy else Decimal("0")
    elif segment == Segment.OPTIONS:
        # STT on options: 0.0625% on sell side (premium * qty) as of FY2024-25
        stt = tv * Decimal("0.000625") if not is_buy else Decimal("0")
    else:
        stt = Decimal("0")

    # Exchange Transaction Charges (NSE)
    if segment == Segment.OPTIONS:
        exchange_txn = tv * Decimal("0.0000053")  # NSE options
    elif segment == Segment.FUTURES:
        exchange_txn = tv * Decimal("0.000002")
    else:
        exchange_txn = tv * Decimal("0.0000345")  # equity

    # SEBI Turnover Fees
    sebi_fees = tv * Decimal("0.000001")

    # Stamp Duty (buy side only)
    if is_buy:
        if segment in (Segment.EQUITY_DELIVERY, Segment.EQUITY_INTRADAY):
            stamp_duty = tv * Decimal("0.00015")
        elif segment == Segment.FUTURES:
            stamp_duty = tv * Decimal("0.00002")
        elif segment == Segment.OPTIONS:
            stamp_duty = tv * Decimal("0.00003")
        else:
            stamp_duty = Decimal("0")
    else:
        stamp_duty = Decimal("0")

    # GST (18% on brokerage + exchange charges)
    gst_base = brokerage + exchange_txn + sebi_fees
    gst = gst_base * Decimal("0.18")

    # Slippage Estimation
    if bid_ask_spread is not None:
        slippage_per_unit = Decimal(str(bid_ask_spread)) / 2
    else:
        if segment == Segment.OPTIONS:
            slippage_per_unit = Decimal("5")  # Bank Nifty options typical spread
        elif segment == Segment.FUTURES:
            slippage_per_unit = Decimal("2")
        else:
            slippage_per_unit = tv * Decimal("0.0005")  # 5 bps for equity

    # Slippage increases with lot count (market impact)
    impact_multiplier = Decimal("1") + Decimal(str(max(0, lots - 1))) * Decimal("0.15")
    slippage = _q(slippage_per_unit * Decimal(str(lots)) * impact_multiplier)

    total = _q(brokerage + stt + exchange_txn + sebi_fees + stamp_duty + gst + slippage)

    return TaxBreakdown(
        brokerage=_q(brokerage),
        stt=_q(stt),
        exchange_txn_charge=_q(exchange_txn),
        sebi_fees=_q(sebi_fees),
        stamp_duty=_q(stamp_duty),
        gst=_q(gst),
        slippage=slippage,
        total=total,
    )


def calculate_roundtrip_costs(
    entry_turnover: float,
    exit_turnover: float,
    segment: Segment,
    broker: Broker = Broker.ZERODHA,
    lots: int = 1,
    bid_ask_spread: float | None = None,
) -> TaxBreakdown:
    """Calculate total roundtrip (buy + sell) costs."""
    buy = calculate_trade_costs(entry_turnover, segment, broker, is_buy=True, lots=lots, bid_ask_spread=bid_ask_spread)
    sell = calculate_trade_costs(exit_turnover, segment, broker, is_buy=False, lots=lots, bid_ask_spread=bid_ask_spread)

    return TaxBreakdown(
        brokerage=buy.brokerage + sell.brokerage,
        stt=buy.stt + sell.stt,
        exchange_txn_charge=buy.exchange_txn_charge + sell.exchange_txn_charge,
        sebi_fees=buy.sebi_fees + sell.sebi_fees,
        stamp_duty=buy.stamp_duty + sell.stamp_duty,
        gst=buy.gst + sell.gst,
        slippage=buy.slippage + sell.slippage,
        total=buy.total + sell.total,
    )


def estimate_breakeven_move(
    entry_price: float,
    quantity: int,
    segment: Segment,
    broker: Broker = Broker.ZERODHA,
    lots: int = 1,
) -> float:
    """Calculate the minimum price move needed to break even after costs.

    Returns the breakeven move in rupees (per unit).
    """
    turnover = entry_price * quantity
    costs = calculate_roundtrip_costs(turnover, turnover, segment, broker, lots)
    return float(costs.total) / quantity if quantity > 0 else 0.0
