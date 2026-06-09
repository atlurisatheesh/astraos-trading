"""AstraOS Risk — Earnings Calendar Guard.

Prevents trading in stocks that have earnings announcement within N days.
Trading into earnings is gambling, not investing. The model can't predict
whether a company will beat or miss expectations.

Uses yfinance earnings calendar (free).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

logger = structlog.get_logger()

# Cache earnings dates to avoid repeated API calls
_earnings_cache: dict[str, dict] = {}
_CACHE_TTL = 3600 * 6  # 6 hours


def get_next_earnings(symbol: str) -> Optional[datetime]:
    """Get next earnings date for a symbol. Returns None if unknown."""
    import time

    cached = _earnings_cache.get(symbol)
    if cached and time.time() - cached["fetched_at"] < _CACHE_TTL:
        return cached.get("date")

    try:
        import yfinance as yf

        yf_sym = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
        ticker = yf.Ticker(yf_sym)
        cal = ticker.calendar

        if cal is not None and not (hasattr(cal, "empty") and cal.empty):
            # calendar can be a DataFrame or dict depending on yfinance version
            if hasattr(cal, "iloc"):
                # DataFrame format
                if "Earnings Date" in cal.index:
                    date_val = cal.loc["Earnings Date"].iloc[0]
                    if hasattr(date_val, "to_pydatetime"):
                        earnings_date = date_val.to_pydatetime()
                    else:
                        earnings_date = datetime.fromisoformat(str(date_val))
                else:
                    earnings_date = None
            elif isinstance(cal, dict):
                dates = cal.get("Earnings Date", [])
                if dates:
                    earnings_date = dates[0] if isinstance(dates[0], datetime) else None
                else:
                    earnings_date = None
            else:
                earnings_date = None

            _earnings_cache[symbol] = {
                "date": earnings_date,
                "fetched_at": time.time(),
            }
            return earnings_date

    except Exception as e:
        logger.debug("Earnings calendar fetch failed", symbol=symbol, error=str(e))

    _earnings_cache[symbol] = {"date": None, "fetched_at": time.time()}
    return None


def is_earnings_blackout(symbol: str, blackout_days: int = 3) -> tuple[bool, str]:
    """Check if a stock is in earnings blackout period.

    Returns (is_blackout, reason).
    Blackout = earnings within N trading days.
    """
    earnings_date = get_next_earnings(symbol)

    if earnings_date is None:
        return False, "Earnings date unknown — proceed with caution"

    now = datetime.now(timezone.utc)
    if hasattr(earnings_date, "tzinfo") and earnings_date.tzinfo is None:
        from zoneinfo import ZoneInfo
        earnings_date = earnings_date.replace(tzinfo=ZoneInfo("Asia/Kolkata"))

    days_until = (earnings_date - now).days

    if 0 <= days_until <= blackout_days:
        return True, (
            f"EARNINGS BLACKOUT: {symbol} reports in {days_until} days "
            f"({earnings_date.strftime('%Y-%m-%d')}). Trading suspended — "
            f"model cannot predict earnings surprises."
        )

    if days_until < 0 and days_until >= -1:
        return True, (
            f"EARNINGS JUST REPORTED: {symbol} reported yesterday. "
            f"Wait for post-earnings volatility to settle."
        )

    return False, f"Next earnings: {earnings_date.strftime('%Y-%m-%d')} ({days_until} days away)"
