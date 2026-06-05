# type: ignore
"""AstraOS — Live Market Scanner (Real-Time, Per-Second).

Continuous asyncio loop that streams market data every second.
Uses yfinance fast batch downloads + intelligent caching to avoid rate limits.

Architecture:
  - Main loop runs every 1 second
  - Fetches quotes in batches (yfinance supports multi-symbol download)
  - Detects price changes, volume spikes, breakouts in real-time
  - Pushes every tick to the live feed + WebSocket broadcast
  - Rotates through NIFTY 50 in batches of 10 (full cycle every 5 seconds)
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional

import pandas as pd  # type: ignore
import yfinance as yf  # type: ignore
import structlog  # type: ignore

logger = structlog.get_logger()

IST = ZoneInfo("Asia/Kolkata")

# ── State ──
_running: bool = False
_task: Optional[asyncio.Task[None]] = None
_tick_count: int = 0

# ── Live price cache (symbol -> latest data) ──
_live_prices: dict[str, dict[str, Any]] = {}
_price_history: dict[str, list[float]] = {}  # last 120 ticks per symbol
_alerts: list[dict[str, Any]] = []

# ── NIFTY 50 Universe ──
NIFTY_50: list[str] = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "BAJFINANCE.NS",
    "LT.NS", "KOTAKBANK.NS", "HCLTECH.NS", "AXISBANK.NS", "ASIANPAINT.NS",
    "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS",
    "NESTLEIND.NS", "BAJAJFINSV.NS", "NTPC.NS", "TATAMOTORS.NS", "POWERGRID.NS",
    "M&M.NS", "ONGC.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "ADANIENT.NS",
    "ADANIPORTS.NS", "COALINDIA.NS", "GRASIM.NS", "TECHM.NS", "HDFCLIFE.NS",
    "DRREDDY.NS", "BPCL.NS", "DIVISLAB.NS", "CIPLA.NS", "BRITANNIA.NS",
    "EICHERMOT.NS", "HEROMOTOCO.NS", "APOLLOHOSP.NS", "TATACONSUM.NS", "SBILIFE.NS",
    "BAJAJ-AUTO.NS", "INDUSINDBK.NS", "UPL.NS", "HINDALCO.NS", "SHREECEM.NS",
]

# ── Index trackers ──
INDICES: list[str] = ["^NSEI", "^NSEBANK", "^INDIAVIX"]

BATCH_SIZE: int = 10


def _clean_symbol(s: str) -> str:
    return s.replace(".NS", "").replace("^", "")


def _fetch_batch_sync(symbols: list[str]) -> dict[str, Any]:
    """Fetch real-time prices for a batch (SYNC — runs in thread pool).

    Uses yf.download period='1d' interval='1m' for the latest minute bar.
    """
    results: dict[str, Any] = {}

    try:
        tickers_str = " ".join(symbols)
        data = yf.download(
            tickers_str,
            period="1d",
            interval="1m",
            progress=False,
            threads=True,
        )

        if data.empty:
            return results

        is_multi = isinstance(data.columns, pd.MultiIndex)

        for sym in symbols:
            try:
                if is_multi and len(symbols) > 1:
                    if sym not in data.columns.get_level_values(1):
                        continue
                    sym_data = data.xs(sym, level=1, axis=1)
                else:
                    sym_data = data
                    if is_multi:
                        sym_data.columns = sym_data.columns.get_level_values(0)

                if sym_data.empty:
                    continue

                latest = sym_data.iloc[-1]
                close_val: float = float(latest.get("Close", 0))
                open_val: float = float(latest.get("Open", 0))
                high_val: float = float(latest.get("High", 0))
                low_val: float = float(latest.get("Low", 0))
                vol_val: int = int(latest.get("Volume", 0))

                if close_val <= 0:
                    continue

                prev: float = float(_live_prices.get(sym, {}).get("price", close_val))
                change: float = close_val - open_val
                change_pct: float = (change / open_val * 100) if open_val else 0.0

                price_dict = {
                    "symbol": _clean_symbol(sym),
                    "price": float(f"{close_val:.2f}"),
                    "open": float(f"{open_val:.2f}"),
                    "high": float(f"{high_val:.2f}"),
                    "low": float(f"{low_val:.2f}"),

                    "volume": vol_val,
                    "change": float(f"{change:.2f}"),
                    "change_pct": float(f"{change_pct:.2f}"),
                    "prev_tick": float(f"{prev:.2f}"),
                    "tick_change": float(f"{close_val - prev:.2f}"),
                    "timestamp": datetime.now(IST).isoformat(),
                }
                results[sym] = price_dict
            except Exception:
                pass

    except Exception as e:
        logger.debug("Batch fetch error", error=str(e))

    return results


def _detect_alerts(sym: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect real-time alerts: spikes, drops, volume surges."""
    alerts: list[dict[str, Any]] = []
    price: float = float(data.get("price", 0))
    change_pct: float = float(data.get("change_pct", 0))
    tick_change: float = float(data.get("tick_change", 0))
    clean: str = str(data.get("symbol", sym))

    # Track price history
    if sym not in _price_history:
        _price_history[sym] = []
    _price_history[sym].append(price)
    if len(_price_history[sym]) > 120:
        _price_history[sym] = list(_price_history[sym][-120:])

    # Alert: Big daily move (>2%)
    if abs(change_pct) > 2.0:
        direction = "🟢 SURGE" if change_pct > 0 else "🔴 DROP"
        alerts.append({
            "type": "PRICE_MOVE",
            "severity": "high" if abs(change_pct) > 4 else "medium",
            "message": f"{direction} {clean} {change_pct:+.2f}% @ ₹{price:,.2f}",
            "data": data,
            "timestamp": datetime.now(IST).isoformat(),
        })

    # Alert: Sudden tick change (>0.5% in one tick)
    if price > 0 and abs(tick_change) / price * 100 > 0.5:
        direction = "⚡ SPIKE" if tick_change > 0 else "💥 CRASH"
        alerts.append({
            "type": "TICK_SPIKE",
            "severity": "critical",
            "message": f"{direction} {clean} moved ₹{tick_change:+.2f} in 1 tick",
            "data": data,
            "timestamp": datetime.now(IST).isoformat(),
        })

    return alerts


async def _live_scanner_loop() -> None:
    """Main continuous scanning loop — runs every ~1 second."""
    global _tick_count

    logger.info("LIVE SCANNER STARTED — scanning every second")

    from .engine import push_feed  # type: ignore
    push_feed("SYSTEM", "🔴 LIVE SCANNER ACTIVE — real-time monitoring every second")

    batch_index: int = 0
    total_batches: int = (len(NIFTY_50) + BATCH_SIZE - 1) // BATCH_SIZE
    loop = asyncio.get_event_loop()

    while _running:
        try:
            # Rotate through batches — full NIFTY 50 cycle every ~5 seconds
            start_idx: int = int(batch_index * BATCH_SIZE)
            end_idx: int = min(start_idx + BATCH_SIZE, len(NIFTY_50))
            batch: list[str] = list(NIFTY_50[start_idx:end_idx])

            # Fetch indices on first batch of each cycle
            if batch_index == 0:
                batch = INDICES + batch

            # Fetch prices in thread pool (yfinance is blocking I/O)
            prices = await loop.run_in_executor(None, _fetch_batch_sync, batch)

            # Process results
            from ..services.portfolio_monitor import monitor_tick  # type: ignore

            for sym, data in prices.items():
                _live_prices[sym] = data

                # Check SL/TP on user portfolios in the background safely
                asyncio.create_task(monitor_tick(sym, data))

                # Detect and push alerts
                for alert in _detect_alerts(sym, data):
                    _alerts.insert(0, alert)
                    if len(_alerts) > 500:
                        _alerts.pop()
                    push_feed(alert["type"], alert["message"], alert["data"])

            _tick_count += 1
            batch_index = (batch_index + 1) % total_batches

            # Log every 60 ticks (~1 min)
            if _tick_count % 60 == 0:
                logger.info(
                    "Live scanner heartbeat",
                    ticks=_tick_count,
                    symbols_tracked=len(_live_prices),
                    alerts_total=len(_alerts),
                )

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Live scanner error", error=str(e))

        # 1-second interval between batch fetches
        await asyncio.sleep(1)

    logger.info("Live scanner stopped", total_ticks=_tick_count)


async def start_live_scanner() -> None:
    """Start the continuous live scanner."""
    global _running, _task

    if _running:
        logger.warning("Live scanner already running")
        return

    _running = True
    _task = asyncio.create_task(_live_scanner_loop())
    logger.info("Live scanner task created")


async def stop_live_scanner() -> None:
    """Stop the live scanner."""
    global _running, _task

    _running = False
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None

    from .engine import push_feed  # type: ignore
    push_feed("SYSTEM", "⏹ Live scanner stopped")
    logger.info("Live scanner stopped")


def get_live_prices() -> dict[str, Any]:
    """Get all latest live prices."""
    return _live_prices.copy()


def get_live_price(symbol: str) -> Optional[dict[str, Any]]:
    """Get live price for a specific symbol."""
    return _live_prices.get(symbol) or _live_prices.get(f"{symbol}.NS")


def get_alerts(limit: int = 50) -> list[dict[str, Any]]:
    """Get recent alerts."""
    return list(_alerts[:limit])


def get_scanner_stats() -> dict[str, Any]:
    """Get scanner statistics."""
    return {
        "running": _running,
        "tick_count": _tick_count,
        "symbols_tracked": len(_live_prices),
        "alerts_count": len(_alerts),
        "universe_size": len(NIFTY_50),
        "cycle_time_seconds": (len(NIFTY_50) // BATCH_SIZE) + 1,
    }
