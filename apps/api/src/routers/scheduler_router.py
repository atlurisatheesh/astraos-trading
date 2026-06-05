"""AstraOS Router — Scheduler Control, Live Feed & Real-Time Scanner."""

from fastapi import APIRouter, Depends

from ..core.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/api/v1/scheduler", tags=["Scheduler"])


@router.get("/status")
async def scheduler_status(user=Depends(get_current_user)):
    """Get scheduler status, jobs, live scanner stats, and market hours info."""
    from ..scheduler.engine import get_scheduler_status
    return get_scheduler_status()


@router.post("/pause")
async def pause(admin=Depends(require_admin)):
    """Pause all scheduler jobs."""
    from ..scheduler.engine import pause_scheduler
    pause_scheduler()
    return {"status": "paused"}


@router.post("/resume")
async def resume(admin=Depends(require_admin)):
    """Resume all scheduler jobs."""
    from ..scheduler.engine import resume_scheduler
    resume_scheduler()
    return {"status": "resumed"}


@router.get("/feed")
async def live_feed(limit: int = 50, user=Depends(get_current_user)):
    """Get the live intelligence feed (recent events)."""
    from ..scheduler.engine import get_feed
    return {"feed": get_feed(limit)}


# ── Live Scanner (per-second) ──

@router.get("/live/prices")
async def live_prices(user=Depends(get_current_user)):
    """Get all live prices (updated every second)."""
    from ..scheduler.live_scanner import get_live_prices, get_scanner_stats
    return {
        "prices": get_live_prices(),
        "scanner": get_scanner_stats(),
    }


@router.get("/live/price/{symbol}")
async def live_price(symbol: str, user=Depends(get_current_user)):
    """Get live price for a specific symbol."""
    from ..scheduler.live_scanner import get_live_price
    data = get_live_price(symbol)
    if data is None:
        return {"error": f"No live data for {symbol}", "symbol": symbol}
    return data


@router.get("/live/alerts")
async def live_alerts(limit: int = 50, user=Depends(get_current_user)):
    """Get real-time price alerts (spikes, drops, breakouts)."""
    from ..scheduler.live_scanner import get_alerts
    return {"alerts": get_alerts(limit)}


# ── AI Signals ──

@router.get("/signals")
async def latest_signals(user=Depends(get_current_user)):
    """Get latest AI signals for all monitored stocks."""
    from ..scheduler.jobs import get_signals
    return {"signals": get_signals()}


@router.get("/signals/history")
async def signal_history(user=Depends(get_current_user)):
    """Get signal history (last 100 signals)."""
    from ..scheduler.jobs import get_signal_history
    return {"history": get_signal_history()}


# ── News & Sentiment ──

@router.get("/news")
async def news_with_sentiment(user=Depends(get_current_user)):
    """Get recent news with FinBERT sentiment scores."""
    from ..scheduler.jobs import get_news_sentiments
    return {"news": get_news_sentiments()}


# ── Auto-Trade ──

@router.get("/trades")
async def auto_trades(user=Depends(get_current_user)):
    """Get today's auto-executed trades."""
    from ..scheduler.auto_trader import get_daily_trades, get_daily_pnl
    return {
        "trades": get_daily_trades(),
        "daily_pnl": get_daily_pnl(),
    }


@router.post("/auto-trade/toggle")
async def toggle_auto_trade(enabled: bool = True, admin=Depends(require_admin)):
    """Enable or disable auto-trading."""
    from ..scheduler.jobs import set_auto_trade
    set_auto_trade(enabled)
    return {"auto_trade": enabled}


@router.get("/auto-trade/config")
async def auto_trade_config(user=Depends(get_current_user)):
    """Get current auto-trade configuration."""
    from ..scheduler.jobs import get_auto_trade_config
    return get_auto_trade_config()
