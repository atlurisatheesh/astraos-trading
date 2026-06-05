"""AstraOS Models package — import all models for Alembic discovery."""

from .user import User
from .instrument import Instrument
from .trading import (
    Alert,
    AuditLog,
    KillSwitchState,
    NewsArchive,
    Order,
    PortfolioSnapshot,
    Position,
    RiskEvent,
    Signal,
    Strategy,
    TradeJournal,
    UserSettings,
    Watchlist,
)

__all__ = [
    "Alert",
    "AuditLog",
    "Instrument",
    "KillSwitchState",
    "NewsArchive",
    "Order",
    "PortfolioSnapshot",
    "Position",
    "RiskEvent",
    "Signal",
    "Strategy",
    "TradeJournal",
    "User",
    "UserSettings",
    "Watchlist",
]
