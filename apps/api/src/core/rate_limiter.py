# type: ignore
"""AstraOS Core — Rate Limiting Middleware.

Per-user request throttling using in-memory sliding window.
Falls back to IP-based limiting for unauthenticated requests.
"""

import time
from collections import defaultdict
from typing import Any

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger()


class RateLimiter:
    """Sliding-window rate limiter."""

    def __init__(self, requests_per_minute: int = 60, burst: int = 20) -> None:
        self.rpm = requests_per_minute
        self.burst = burst
        self.window = 60.0  # seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> tuple[bool, dict[str, Any]]:
        """Check if request is allowed. Returns (allowed, headers)."""
        now = time.time()
        window_start = now - self.window

        # Clean old entries
        self._requests[key] = [t for t in self._requests[key] if t > window_start]

        current_count = len(self._requests[key])
        remaining = max(0, self.rpm - current_count)

        headers = {
            "X-RateLimit-Limit": str(self.rpm),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(window_start + self.window)),
        }

        if current_count >= self.rpm:
            retry_after = int(self._requests[key][0] + self.window - now) + 1
            headers["Retry-After"] = str(retry_after)
            return False, headers

        # Burst check: max N requests per second
        last_second = [t for t in self._requests[key] if t > now - 1]
        if len(last_second) >= self.burst:
            headers["Retry-After"] = "1"
            return False, headers

        self._requests[key].append(now)
        return True, headers

    def cleanup(self) -> None:
        """Remove stale entries."""
        now = time.time()
        stale_keys = [k for k, v in self._requests.items() if not v or v[-1] < now - self.window * 2]
        for k in stale_keys:
            del self._requests[k]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(self, app: Any, requests_per_minute: int = 120, burst: int = 30) -> None:
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute, burst)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Skip rate limiting for health checks and docs
        if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        # Identify user: JWT user_id > IP
        key = self._get_key(request)
        allowed, headers = self.limiter.is_allowed(key)

        if not allowed:
            logger.warning("Rate limit exceeded", key=key, path=request.url.path)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please slow down.",
                headers=headers,
            )

        response = await call_next(request)
        for k, v in headers.items():
            response.headers[k] = v
        return response

    @staticmethod
    def _get_key(request: Request) -> str:
        """Extract rate-limit key from request."""
        # Try to get user from JWT token
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            import hashlib
            return f"user:{hashlib.sha256(token.encode()).hexdigest()[:16]}"

        # Fallback to IP
        client = request.client
        ip = client.host if client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        return f"ip:{ip}"
