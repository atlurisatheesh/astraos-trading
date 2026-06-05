# type: ignore
"""AstraOS ML — Automated Re-Training Scheduler.

Handles weekly model re-training on the full NIFTY 50 universe:
  - Trains XGBoost on 2 years of fresh data every Saturday night
  - Compares new model vs active model (A/B accuracy check)
  - Only promotes if new model is better
  - Sends alerts via Telegram/Email on training completion
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import structlog

logger = structlog.get_logger()

IST = ZoneInfo("Asia/Kolkata")

# ── NIFTY 50 Universe ──
NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
    "TITAN", "BAJFINANCE", "WIPRO", "ULTRACEMCO", "NESTLEIND",
    "NTPC", "POWERGRID", "ONGC", "JSWSTEEL", "TATASTEEL",
    "ADANIENT", "ADANIPORTS", "COALINDIA", "GRASIM", "HCLTECH",
    "BPCL", "TECHM", "INDUSINDBK", "DIVISLAB", "EICHERMOT",
    "HEROMOTOCO", "DRREDDY", "CIPLA", "BRITANNIA", "APOLLOHOSP",
    "TATACONSUM", "BAJAJ-AUTO", "BAJAJFINSV", "M&M", "SBILIFE",
    "HDFCLIFE", "TATAMOTORS", "UPL", "HINDALCO", "LTIM",
]

# ── Broader Universe (NIFTY 100 additions for deeper training) ──
NIFTY_NEXT_50 = [
    "DABUR", "GODREJCP", "HAVELLS", "PIDILITIND", "SIEMENS",
    "BERGEPAINT", "COLPAL", "MARICO", "MCDOWELL-N", "SRF",
    "NAUKRI", "DMART", "ZOMATO", "PAYTM", "IRCTC",
    "TRENT", "LICI", "LODHA", "MANKIND", "JIOFINANCE",
]


async def job_weekly_retrain() -> None:
    """Scheduled job: Re-train the ML model weekly with latest data.
    
    This runs every Saturday night at 11 PM IST (post-market).
    """
    logger.info("🧠 Starting weekly model re-training on NIFTY 50")
    
    try:
        import asyncio
        from ..ml.trainer import train_signal_model_sync, get_training_status
        from ..ml.model_registry import register_model, CURRENT_MODEL, get_active_model_info
        from ..scheduler.engine import push_feed
        
        push_feed("ML_TRAIN", "🧠 Weekly re-training started — NIFTY 50 universe (3y data)")

        # Train on NIFTY 50 with 3 years of data (matches standalone train_model.py defaults)
        await asyncio.to_thread(
            train_signal_model_sync, NIFTY_50, "3y",
            forward_days=5, threshold=1.5,
        )
        
        # Check if training succeeded
        status = get_training_status()
        
        if status.get("status") != "completed":
            error_msg = status.get("error", "Unknown training error")
            push_feed("ML_TRAIN", f"❌ Weekly re-training failed: {error_msg}")
            logger.error("Weekly re-training failed", error=error_msg)
            await _send_training_alert(False, error_msg)
            return
        
        metrics = status.get("metrics", {})
        
        # Register in model registry (auto-promotes if better)
        result = register_model(CURRENT_MODEL, metrics)
        
        version = result["version"]
        accuracy = result["accuracy"]
        promoted = result["promoted"]
        reason = result["promotion_reason"]
        
        if promoted:
            push_feed(
                "ML_TRAIN",
                f"🎯 Model v{version} promoted — accuracy {accuracy}% | {reason}",
                {"version": version, "accuracy": accuracy},
            )
        else:
            push_feed(
                "ML_TRAIN",
                f"⚠️ Model v{version} trained but NOT promoted — {reason}",
                {"version": version, "accuracy": accuracy},
            )
        
        logger.info(
            "Weekly re-training complete",
            version=version,
            accuracy=accuracy,
            promoted=promoted,
            reason=reason,
        )
        
        # Send notification
        await _send_training_alert(True, f"v{version} — {accuracy}% accuracy. {reason}")
        
    except Exception as e:
        logger.error("Weekly re-training crashed", error=str(e))
        try:
            from ..scheduler.engine import push_feed
            push_feed("ML_TRAIN", f"💀 Re-training crashed: {str(e)[:100]}")
        except Exception:
            pass
        await _send_training_alert(False, str(e))


async def train_on_demand(
    symbols: list[str] | None = None,
    period: str = "2y",
) -> dict:
    """Manually trigger a training run (used by API endpoint).
    
    Args:
        symbols: Override stock list (defaults to NIFTY 50)
        period: Historical lookback period
        
    Returns:
        Training result with model version and promotion info
    """
    import asyncio
    from ..ml.trainer import train_signal_model_sync, get_training_status
    from ..ml.model_registry import register_model, CURRENT_MODEL
    
    stock_list = symbols or NIFTY_50
    
    # Run training in background thread (non-blocking)
    await asyncio.to_thread(train_signal_model_sync, stock_list, period)
    
    status = get_training_status()
    
    if status.get("status") != "completed":
        return {
            "status": "failed",
            "error": status.get("error", "Training did not complete"),
        }
    
    metrics = status.get("metrics", {})
    
    # Register and potentially promote
    result = register_model(CURRENT_MODEL, metrics)
    
    return {
        "status": "completed",
        "version": result["version"],
        "accuracy": result["accuracy"],
        "promoted": result["promoted"],
        "promotion_reason": result["promotion_reason"],
        "metrics": metrics,
    }


async def _send_training_alert(success: bool, message: str) -> None:
    """Send training completion alert via all configured channels."""
    try:
        from ..services.telegram_service import send_telegram_message
        
        icon = "✅" if success else "❌"
        text = f"{icon} QUANTUS AI Model Training\n\n{message}\n\n⏰ {datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')}"
        
        await send_telegram_message(text)
    except Exception as e:
        logger.debug("Telegram alert failed", error=str(e))
    
    try:
        from ..services.email_service import send_email_alert
        
        subject = f"{'✅' if success else '❌'} Model Training {'Complete' if success else 'Failed'}"
        await send_email_alert(subject, message)
    except Exception as e:
        logger.debug("Email alert failed", error=str(e))
