"""AstraOS Core — Hardened Security Module.

Defence-in-depth security for a financial trading platform.
Covers: input sanitization, API key rotation, audit logging,
request signing, and anti-tampering for trade operations.
"""

import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable

import structlog
from fastapi import HTTPException, Request, status

logger = structlog.get_logger()


# ── Input Sanitization ─────────────────────────────────────────────────────

_SYMBOL_RE = re.compile(r"^[A-Z0-9&_.-]{1,20}$")
_SAFE_STRING_RE = re.compile(r"^[\w\s.,;:!?@#$%^&*()\-+=\[\]{}<>/\\|'\"`~]{0,500}$")
_SQL_INJECTION_PATTERNS = [
    r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|EXEC|EXECUTE)\b)",
    r"(--|;|/\*|\*/|xp_|sp_|0x)",
    r"('\s*(OR|AND)\s*'?\s*\d*\s*=)",
]
_XSS_PATTERNS = [
    r"<script",
    r"javascript:",
    r"on\w+\s*=",
    r"<iframe",
    r"<object",
    r"<embed",
    r"<form",
    r"data:text/html",
]


def sanitize_symbol(symbol: str) -> str:
    """Validate and sanitize a stock symbol."""
    cleaned = symbol.strip().upper()
    if not _SYMBOL_RE.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid symbol format",
        )
    return cleaned


def sanitize_string(value: str, field_name: str = "input", max_length: int = 500) -> str:
    """Sanitize a general string input."""
    if len(value) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} exceeds maximum length of {max_length}",
        )

    for pattern in _SQL_INJECTION_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning("SQL injection attempt blocked", field=field_name, value=value[:50])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid characters in {field_name}",
            )

    for pattern in _XSS_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            logger.warning("XSS attempt blocked", field=field_name, value=value[:50])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid characters in {field_name}",
            )

    return value.strip()


def sanitize_numeric(value: Any, field_name: str, min_val: float = 0, max_val: float = 1e12) -> float:
    """Validate and sanitize numeric input."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be a number",
        )

    if num < min_val or num > max_val:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be between {min_val} and {max_val}",
        )

    return num


# ── Trade Request Signing ──────────────────────────────────────────────────

def generate_trade_nonce() -> str:
    """Generate a cryptographically secure nonce for trade requests."""
    return secrets.token_hex(32)


def sign_trade_request(
    user_id: str,
    symbol: str,
    action: str,
    quantity: int,
    price: float,
    nonce: str,
    secret_key: str,
) -> str:
    """HMAC-sign a trade request to prevent tampering."""
    message = f"{user_id}|{symbol}|{action}|{quantity}|{price}|{nonce}"
    return hmac.new(
        secret_key.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_trade_signature(
    user_id: str,
    symbol: str,
    action: str,
    quantity: int,
    price: float,
    nonce: str,
    signature: str,
    secret_key: str,
) -> bool:
    """Verify trade request signature."""
    expected = sign_trade_request(user_id, symbol, action, quantity, price, nonce, secret_key)
    return hmac.compare_digest(signature, expected)


# ── Nonce Tracking (replay prevention) ─────────────────────────────────────

_used_nonces: dict[str, float] = {}
_NONCE_EXPIRY_SECONDS = 300  # 5 minutes


def check_and_consume_nonce(nonce: str) -> bool:
    """Check if a nonce is fresh and mark it as used. Returns True if valid."""
    now = time.time()

    # Cleanup expired nonces
    expired = [k for k, v in _used_nonces.items() if now - v > _NONCE_EXPIRY_SECONDS]
    for k in expired:
        del _used_nonces[k]

    if nonce in _used_nonces:
        logger.warning("Replay attack blocked — duplicate nonce", nonce=nonce[:16])
        return False

    _used_nonces[nonce] = now
    return True


# ── Audit Logger ───────────────────────────────────────────────────────────

class AuditEvent:
    """Structured audit event for financial compliance."""

    @staticmethod
    def log(
        action: str,
        user_id: str | None = None,
        resource: str = "",
        details: dict | None = None,
        ip_address: str = "",
        severity: str = "INFO",
    ) -> dict:
        event = {
            "audit": True,
            "action": action,
            "user_id": user_id,
            "resource": resource,
            "details": details or {},
            "ip_address": ip_address,
            "severity": severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("audit_event", **event)
        return event

    @staticmethod
    def log_trade(
        user_id: str,
        symbol: str,
        action: str,
        quantity: int,
        price: float,
        order_id: str = "",
        broker: str = "paper",
        ip_address: str = "",
    ) -> dict:
        return AuditEvent.log(
            action=f"TRADE_{action}",
            user_id=user_id,
            resource=f"order/{order_id}",
            details={
                "symbol": symbol,
                "side": action,
                "quantity": quantity,
                "price": price,
                "broker": broker,
                "order_id": order_id,
            },
            ip_address=ip_address,
            severity="CRITICAL",
        )

    @staticmethod
    def log_auth(
        action: str,
        email: str,
        success: bool,
        ip_address: str = "",
        user_agent: str = "",
    ) -> dict:
        return AuditEvent.log(
            action=f"AUTH_{action}",
            resource=f"user/{email}",
            details={
                "email": email,
                "success": success,
                "user_agent": user_agent[:200],
            },
            ip_address=ip_address,
            severity="WARNING" if not success else "INFO",
        )

    @staticmethod
    def log_risk_event(
        user_id: str,
        event_type: str,
        details: dict,
    ) -> dict:
        return AuditEvent.log(
            action=f"RISK_{event_type}",
            user_id=user_id,
            resource="risk_engine",
            details=details,
            severity="CRITICAL",
        )


# ── IP-based Suspicious Activity Detection ─────────────────────────────────

_ip_activity: dict[str, list[float]] = {}
_SUSPICIOUS_THRESHOLD = 50  # requests in 10 seconds from same IP


def check_suspicious_activity(ip: str) -> bool:
    """Returns True if activity from this IP looks suspicious."""
    now = time.time()
    if ip not in _ip_activity:
        _ip_activity[ip] = []

    # Clean old entries
    _ip_activity[ip] = [t for t in _ip_activity[ip] if now - t < 10]
    _ip_activity[ip].append(now)

    if len(_ip_activity[ip]) > _SUSPICIOUS_THRESHOLD:
        logger.warning("Suspicious activity detected", ip=ip, requests_per_10s=len(_ip_activity[ip]))
        return True

    return False


def get_client_ip(request: Request) -> str:
    """Safely extract client IP from request, handling proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
