"""AstraOS Scheduler — APScheduler-based continuous monitoring engine.

Runs background jobs during market hours (IST 09:15–15:30):
  - Market scan every 5 minutes on the NIFTY 50 universe
  - News ingestion + FinBERT scoring every 15 minutes
  - Signal generation for the user's watchlist every 10 minutes
  - Auto-trade execution check every 5 minutes (when enabled)
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
from apscheduler.triggers.interval import IntervalTrigger  # type: ignore
from apscheduler.triggers.cron import CronTrigger  # type: ignore
import structlog  # type: ignore

logger = structlog.get_logger()

IST = ZoneInfo("Asia/Kolkata")

# ── Singleton Scheduler ──
_scheduler: AsyncIOScheduler | None = None

# ── Live Feed (in-memory ring buffer, last 200 events) ──
_feed: list[dict] = []
_MAX_FEED = 200


def push_feed(event_type: str, message: str, data: dict | None = None) -> None:
    """Push an event to the live intelligence feed."""
    entry = {
        "type": event_type,
        "message": message,
        "data": data or {},
        "timestamp": datetime.now(IST).isoformat(),
    }
    _feed.insert(0, entry)
    if len(_feed) > _MAX_FEED:
        _feed.pop()
    logger.info("feed_event", type=event_type, message=message)


def get_feed(limit: int = 50) -> list[dict]:
    """Get recent feed entries."""
    return _feed[:limit]


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


def is_market_hours() -> bool:
    """Check if current time is within NSE trading hours."""
    now = datetime.now(IST)
    # Weekdays only (Mon=0 .. Fri=4)
    if now.weekday() > 4:
        return False
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


async def start_scheduler() -> None:
    """Start the background scheduler with all monitoring jobs."""
    global _scheduler

    if _scheduler is not None:
        logger.warning("Scheduler already running")
        return

    _scheduler = AsyncIOScheduler(timezone=IST)

    # Import jobs (lazy to avoid circular imports)
    from .jobs import (  # type: ignore
        job_market_scan,
        job_ingest_news,
        job_generate_signals,
        job_auto_trade_check,
        job_check_position_exits,
        job_daily_email_report,
        job_weekly_digest,
    )

    # ── Market Scan: every 5 min during market hours ──
    _scheduler.add_job(
        job_market_scan,
        trigger=IntervalTrigger(minutes=5, timezone=IST),
        id="market_scan",
        name="Market Scan (NIFTY 50)",
        max_instances=1,
        replace_existing=True,
    )

    # ── News Ingestion + FinBERT: every 15 min (24/7, global news matters) ──
    _scheduler.add_job(
        job_ingest_news,
        trigger=IntervalTrigger(minutes=15, timezone=IST),
        id="news_ingest",
        name="News Ingestion + FinBERT",
        max_instances=1,
        replace_existing=True,
    )

    # ── Signal Generation: every 10 min during market hours ──
    _scheduler.add_job(
        job_generate_signals,
        trigger=IntervalTrigger(minutes=10, timezone=IST),
        id="signal_gen",
        name="AI Signal Generation",
        max_instances=1,
        replace_existing=True,
    )

    # ── Auto-Trade Check: every 5 min during market hours ──
    _scheduler.add_job(
        job_auto_trade_check,
        trigger=IntervalTrigger(minutes=5, timezone=IST),
        id="auto_trade",
        name="Auto-Trade Execution Check",
        max_instances=1,
        replace_existing=True,
    )

    # ── Position Exit Manager: every 2 min (trailing stops, target/SL) ──
    _scheduler.add_job(
        job_check_position_exits,
        trigger=IntervalTrigger(minutes=2, timezone=IST),
        id="position_exits",
        name="Position Exit Manager (Trailing Stops)",
        max_instances=1,
        replace_existing=True,
    )

    # ── Daily Email Report: 3:35 PM IST (after market close) ──
    _scheduler.add_job(
        job_daily_email_report,
        trigger=CronTrigger(hour=15, minute=35, timezone=IST),
        id="daily_email",
        name="Daily P&L Email Report",
        max_instances=1,
        replace_existing=True,
    )

    # ── Weekly Digest: Saturday 10 AM IST ──
    _scheduler.add_job(
        job_weekly_digest,
        trigger=CronTrigger(day_of_week="sat", hour=10, minute=0, timezone=IST),
        id="weekly_digest",
        name="Weekly Market Digest Email",
        max_instances=1,
        replace_existing=True,
    )

    # ── ML Model Re-Training: Saturday 11 PM IST ──
    from ..ml.training_scheduler import job_weekly_retrain  # type: ignore
    _scheduler.add_job(
        job_weekly_retrain,
        trigger=CronTrigger(day_of_week="sat", hour=23, minute=0, timezone=IST),
        id="ml_retrain",
        name="Weekly ML Model Re-Training (NIFTY 50)",
        max_instances=1,
        replace_existing=True,
    )

    _scheduler.start()

    # Start the continuous live scanner (per-second market monitoring)
    from .live_scanner import start_live_scanner  # type: ignore
    await start_live_scanner()

    push_feed("SYSTEM", "🤖 QUANTUS AI Started — live scanning every second + scheduled analysis")
    logger.info("Scheduler started", jobs=len(_scheduler.get_jobs()))


async def stop_scheduler() -> None:
    """Gracefully stop the scheduler and live scanner."""
    global _scheduler

    # Stop live scanner first
    try:
        from .live_scanner import stop_live_scanner  # type: ignore
        await stop_live_scanner()
    except Exception:
        pass

    if _scheduler:
        _scheduler.shutdown(wait=False)
        push_feed("SYSTEM", "🛑 Scheduler stopped")
        logger.info("Scheduler stopped")
        _scheduler = None


def pause_scheduler() -> None:
    """Pause all jobs without shutting down."""
    if _scheduler:
        _scheduler.pause()
        push_feed("SYSTEM", "⏸ Scheduler paused — all jobs on hold")
        logger.info("Scheduler paused")


def resume_scheduler() -> None:
    """Resume all paused jobs."""
    if _scheduler:
        _scheduler.resume()
        push_feed("SYSTEM", "▶️ Scheduler resumed — monitoring active")
        logger.info("Scheduler resumed")


def get_scheduler_status() -> dict:
    """Get current scheduler status."""
    if not _scheduler:
        return {"status": "stopped", "jobs": [], "market_hours": is_market_hours()}

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "pending": job.pending,
        })

    # Include live scanner stats
    scanner_stats = {}
    try:
        from .live_scanner import get_scanner_stats  # type: ignore
        scanner_stats = get_scanner_stats()
    except Exception:
        pass

    return {
        "status": "running" if _scheduler.running else "paused",
        "jobs": jobs,
        "market_hours": is_market_hours(),
        "feed_count": len(_feed),
        "live_scanner": scanner_stats,
    }
