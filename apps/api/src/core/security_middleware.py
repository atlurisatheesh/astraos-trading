# type: ignore
"""AstraOS Core — Hardened Security Middleware.

Defence-in-depth HTTP security for a financial trading platform:
  - HTTPS enforcement with HSTS preload
  - Content Security Policy (CSP) to prevent XSS
  - Full OWASP recommended security headers
  - Request body size limiting
  - Suspicious activity detection
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse, Response, JSONResponse
from fastapi import Request
import structlog

from .config import get_settings
from .security_hardened import check_suspicious_activity, get_client_ip

logger = structlog.get_logger()

MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds OWASP-recommended security headers + HTTPS redirect + abuse detection."""

    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()

        # Suspicious activity detection (DDoS / scraping)
        client_ip = get_client_ip(request)
        if check_suspicious_activity(client_ip):
            logger.warning("Request blocked — suspicious activity", ip=client_ip)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )

        # Request body size check (prevent memory exhaustion)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )

        # HTTPS redirect in production
        if settings.enforce_https and request.url.scheme == "http":
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=301)

        response = await call_next(request)

        # ── Security Headers (OWASP Best Practices) ──
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"  # Modern recommendation: disable, rely on CSP
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=(), "
            "usb=(), magnetometer=(), gyroscope=(), accelerometer=()"
        )

        # Content Security Policy — prevents XSS and data exfiltration
        csp_parts = [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self'",
            "connect-src 'self' wss: ws:",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
            "object-src 'none'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_parts)

        # Cross-Origin policies
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # HSTS (with preload directive for production)
        if settings.enforce_https:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        # Remove server identification headers
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        return response
