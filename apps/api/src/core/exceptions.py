"""AstraOS API — Custom Exception Handlers."""

from fastapi import Request
from fastapi.responses import JSONResponse


class AstraOSError(Exception):
    """Base exception for AstraOS."""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class RiskLimitBreached(AstraOSError):
    """Raised when a risk limit is breached."""
    def __init__(self, limit_name: str, current_value: float, max_value: float):
        self.limit_name = limit_name
        self.current_value = current_value
        self.max_value = max_value
        super().__init__(
            f"Risk limit breached: {limit_name} "
            f"(current: {current_value}, max: {max_value})",
            status_code=422,
        )


class BrokerError(AstraOSError):
    """Raised on broker adapter failures."""
    pass


class StaleDataError(AstraOSError):
    """Raised when market data is too old."""
    pass


async def astraos_exception_handler(request: Request, exc: AstraOSError) -> JSONResponse:
    """Global handler — never leaks internal details."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message},
    )
