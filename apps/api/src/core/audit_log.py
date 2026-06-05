# type: ignore
"""AstraOS Core — Audit Log.

Tracks every significant action: trades, alerts, settings changes,
API key operations, and system events.

Stores in-memory with periodic DB flush support.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from enum import Enum

import structlog

logger = structlog.get_logger()


class AuditAction(str, Enum):
    """Types of auditable actions."""
    TRADE_PLACED = "trade_placed"
    TRADE_EXECUTED = "trade_executed"
    TRADE_CANCELLED = "trade_cancelled"
    ALERT_CREATED = "alert_created"
    ALERT_TRIGGERED = "alert_triggered"
    ALERT_DELETED = "alert_deleted"
    WEBHOOK_RECEIVED = "webhook_received"
    SETTINGS_UPDATED = "settings_updated"
    API_KEY_ADDED = "api_key_added"
    API_KEY_REMOVED = "api_key_removed"
    LOGIN = "login"
    LOGOUT = "logout"
    BROKER_CONNECTED = "broker_connected"
    KILL_SWITCH = "kill_switch"
    SYSTEM_ERROR = "system_error"
    SCANNER_SIGNAL = "scanner_signal"


@dataclass
class AuditEntry:
    """A single audit log entry."""
    action: str
    user_id: Optional[str]
    timestamp: str
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    severity: str = "info"  # info, warning, critical

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "details": self.details,
            "ip_address": self.ip_address,
            "severity": self.severity,
        }


class AuditLogService:
    """In-memory audit log with query capabilities."""

    def __init__(self, max_entries: int = 10000) -> None:
        self._entries: list[AuditEntry] = []
        self._max = max_entries

    def log(
        self,
        action: str,
        user_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        ip_address: str = "",
        severity: str = "info",
    ) -> AuditEntry:
        """Record an audit event."""
        entry = AuditEntry(
            action=action,
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=details or {},
            ip_address=ip_address,
            severity=severity,
        )
        self._entries.append(entry)
        if len(self._entries) > self._max:
            self._entries = self._entries[-self._max:]

        logger.info("audit", action=action, user=user_id, severity=severity)
        return entry

    def query(
        self,
        action: Optional[str] = None,
        user_id: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query audit entries with filters."""
        results = self._entries
        if action:
            results = [e for e in results if e.action == action]
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if severity:
            results = [e for e in results if e.severity == severity]
        return list(reversed(results[-limit:]))

    def get_summary(self) -> dict[str, Any]:
        """Get audit log summary."""
        action_counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {"info": 0, "warning": 0, "critical": 0}
        for e in self._entries:
            action_counts[e.action] = action_counts.get(e.action, 0) + 1
            severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1

        return {
            "total_entries": len(self._entries),
            "action_counts": action_counts,
            "severity_counts": severity_counts,
            "oldest": self._entries[0].timestamp if self._entries else None,
            "newest": self._entries[-1].timestamp if self._entries else None,
        }


_service: Optional[AuditLogService] = None

def get_audit_service() -> AuditLogService:
    global _service
    if _service is None:
        _service = AuditLogService()
    return _service
