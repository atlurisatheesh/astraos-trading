"""AstraOS Broker — Unified Broker Interface.

All broker adapters (Angel One, Kite, Upstox, Fyers, 5Paisa, Groww)
implement this abstract interface for plug-and-play broker switching.

Usage:
    broker = get_broker("kite")   # or "angel", "upstox", "fyers", "5paisa", "groww", "paper"
    await broker.login(credentials)
    await broker.place_order(...)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class BrokerCredentials:
    """Universal credential container for all brokers."""
    api_key: str = ""
    api_secret: str = ""
    client_id: str = ""
    password: str = ""
    totp_secret: str = ""
    access_token: str = ""
    request_token: str = ""
    # Broker-specific extras
    extras: dict = None

    def __post_init__(self):
        if self.extras is None:
            self.extras = {}


@dataclass
class OrderParams:
    """Universal order parameters."""
    symbol: str
    exchange: str = "NSE"          # NSE, BSE, NFO, MCX, CDS
    side: str = "BUY"              # BUY, SELL
    order_type: str = "MARKET"     # MARKET, LIMIT, SL, SL-M
    product: str = "DELIVERY"      # DELIVERY/CNC, INTRADAY/MIS, NRML
    quantity: int = 1
    price: float = 0               # For LIMIT orders
    trigger_price: float = 0       # For SL orders
    variety: str = "NORMAL"        # NORMAL, AMO, BO, CO
    validity: str = "DAY"          # DAY, IOC, GTC
    tag: str = ""                  # Order tag for tracking
    # Broker-specific fields
    symbol_token: str = ""         # Angel One, Upstox symbol tokens
    instrument_token: str = ""     # Kite instrument token


@dataclass
class OrderResult:
    """Standardized order result across all brokers."""
    success: bool
    order_id: str = ""
    broker: str = ""
    status: str = ""
    message: str = ""
    raw: dict = None

    def __post_init__(self):
        if self.raw is None:
            self.raw = {}

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "order_id": self.order_id,
            "broker": self.broker,
            "status": self.status,
            "message": self.message,
        }


@dataclass
class Position:
    """Standardized position across all brokers."""
    symbol: str
    exchange: str
    side: str               # BUY / SELL (net direction)
    quantity: int
    avg_price: float
    ltp: float = 0
    pnl: float = 0
    product: str = ""
    broker: str = ""


@dataclass
class Holding:
    """Standardized holding (delivery stocks)."""
    symbol: str
    exchange: str
    quantity: int
    avg_price: float
    ltp: float = 0
    pnl: float = 0
    pnl_pct: float = 0
    broker: str = ""


class BrokerAdapter(ABC):
    """Abstract base class for all broker adapters.

    Every broker (Angel One, Kite, Upstox, Fyers, 5Paisa, Groww)
    must implement these methods.
    """

    name: str = "base"

    @abstractmethod
    async def login(self, credentials: BrokerCredentials) -> dict:
        """Authenticate with the broker. Returns login status + profile."""
        ...

    @abstractmethod
    async def place_order(self, params: OrderParams) -> OrderResult:
        """Place a new order. Returns standardized OrderResult."""
        ...

    @abstractmethod
    async def modify_order(self, order_id: str, params: OrderParams) -> OrderResult:
        """Modify an existing order."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel an order."""
        ...

    @abstractmethod
    async def get_order_book(self) -> list[dict]:
        """Get today's orders."""
        ...

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Get open positions."""
        ...

    @abstractmethod
    async def get_holdings(self) -> list[Holding]:
        """Get portfolio holdings."""
        ...

    @abstractmethod
    async def get_funds(self) -> dict:
        """Get available funds and margins."""
        ...

    @abstractmethod
    async def get_ltp(self, exchange: str, symbol: str) -> float:
        """Get Last Traded Price."""
        ...

    @abstractmethod
    async def get_quote(self, exchange: str, symbol: str) -> dict:
        """Get full market quote."""
        ...

    @property
    @abstractmethod
    def is_logged_in(self) -> bool:
        """Check if currently authenticated."""
        ...


# ═══════════════════════════════════════════════════════════════
# Broker Factory — Get any broker by name
# ═══════════════════════════════════════════════════════════════

_BROKER_REGISTRY: dict[str, type[BrokerAdapter]] = {}


def register_broker(name: str, adapter_class: type[BrokerAdapter]) -> None:
    """Register a broker adapter."""
    _BROKER_REGISTRY[name.lower()] = adapter_class


def get_broker(name: str = "paper") -> BrokerAdapter:
    """Get a broker adapter by name.

    Available: paper, angel, kite, upstox, fyers, 5paisa, groww
    """
    name = name.lower()

    # Lazy-load all adapters on first call
    if not _BROKER_REGISTRY:
        _load_all_adapters()

    if name not in _BROKER_REGISTRY:
        available = ", ".join(sorted(_BROKER_REGISTRY.keys()))
        raise ValueError(f"Unknown broker: '{name}'. Available: {available}")

    return _BROKER_REGISTRY[name]()


def list_brokers() -> list[dict]:
    """List all available broker adapters."""
    if not _BROKER_REGISTRY:
        _load_all_adapters()

    return [
        {"name": name, "class": cls.__name__}
        for name, cls in sorted(_BROKER_REGISTRY.items())
    ]


def _load_all_adapters() -> None:
    """Import and register all broker adapters."""
    # Paper (always available)
    from .paper_unified import PaperBrokerUnified
    register_broker("paper", PaperBrokerUnified)

    # Angel One
    try:
        from .angel_one_unified import AngelOneUnified
        register_broker("angel", AngelOneUnified)
        register_broker("angelone", AngelOneUnified)
    except Exception:
        pass

    # Zerodha Kite
    try:
        from .kite_adapter import KiteAdapter
        register_broker("kite", KiteAdapter)
        register_broker("zerodha", KiteAdapter)
    except Exception:
        pass

    # Upstox
    try:
        from .upstox_adapter import UpstoxAdapter
        register_broker("upstox", UpstoxAdapter)
    except Exception:
        pass

    # Fyers
    try:
        from .fyers_adapter import FyersAdapter
        register_broker("fyers", FyersAdapter)
    except Exception:
        pass

    # 5Paisa
    try:
        from .fivepaisa_adapter import FivePaisaAdapter
        register_broker("5paisa", FivePaisaAdapter)
        register_broker("fivepaisa", FivePaisaAdapter)
    except Exception:
        pass

    # Groww
    try:
        from .groww_adapter import GrowwAdapter
        register_broker("groww", GrowwAdapter)
    except Exception:
        pass
