# type: ignore
"""AstraOS Core — Account Lockout Service.

Tracks failed login attempts and temporarily locks accounts
after too many consecutive failures.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field

import structlog

from .config import get_settings

logger = structlog.get_logger()


@dataclass
class LockoutEntry:
    failed_attempts: int = 0
    locked_until: float = 0.0
    attempt_timestamps: list = field(default_factory=list)


class AccountLockout:
    """In-memory account lockout tracker (production: use Redis)."""

    def __init__(self) -> None:
        self._attempts: dict[str, LockoutEntry] = defaultdict(LockoutEntry)

    def is_locked(self, email: str) -> bool:
        """Check if an account is currently locked out."""
        entry = self._attempts.get(email)
        if not entry:
            return False
        if entry.locked_until > time.time():
            return True
        # Lock expired — reset
        if entry.locked_until > 0:
            self._reset(email)
        return False

    def remaining_lockout_seconds(self, email: str) -> int:
        """Get remaining lockout time in seconds."""
        entry = self._attempts.get(email)
        if not entry or entry.locked_until <= time.time():
            return 0
        return int(entry.locked_until - time.time()) + 1

    def record_failure(self, email: str) -> tuple[bool, int]:
        """Record a failed login attempt.
        
        Returns (is_now_locked, remaining_attempts).
        """
        settings = get_settings()
        entry = self._attempts[email]
        entry.failed_attempts += 1
        entry.attempt_timestamps.append(time.time())

        remaining = max(0, settings.login_max_attempts - entry.failed_attempts)

        if entry.failed_attempts >= settings.login_max_attempts:
            entry.locked_until = time.time() + (settings.login_lockout_minutes * 60)
            logger.warning(
                "Account locked due to too many failed attempts",
                email=email,
                lockout_minutes=settings.login_lockout_minutes,
            )
            return True, 0

        return False, remaining

    def record_success(self, email: str) -> None:
        """Reset failed attempts on successful login."""
        self._reset(email)

    def _reset(self, email: str) -> None:
        if email in self._attempts:
            del self._attempts[email]


# Singleton
lockout_service = AccountLockout()
