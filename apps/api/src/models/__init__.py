"""AstraOS Models package — import all models for Alembic discovery."""

from .user import User
from .instrument import Instrument
from .broker import BrokerCredential
from .ml_artifact import MLModelArtifact
from .state import SchedulerState
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
    "BrokerCredential",
    "Instrument",
    "MLModelArtifact",
    "KillSwitchState",
    "NewsArchive",
    "Order",
    "PortfolioSnapshot",
    "Position",
    "RiskEvent",
    "SchedulerState",
    "Signal",
    "Strategy",
    "TradeJournal",
    "User",
    "UserSettings",
    "Watchlist",
]
