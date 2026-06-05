# type: ignore
"""AstraOS Routers — Phase 11 Pro Trading Features.

Endpoints for:
  - Options Strategy Builder
  - Earnings Calendar & Reaction Predictor
  - Market Breadth & Heatmap
  - Multi-Timeframe Analysis
  - Portfolio Correlation Matrix
  - TradingView Webhook Receiver
  - Audit Log
"""

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.dependencies import get_current_user
from ..services.strategy_builder import get_strategy_builder
from ..services.earnings_calendar import get_earnings_service
from ..services.market_breadth import get_market_breadth_service
from ..services.multi_timeframe import get_multi_timeframe_service
from ..services.portfolio_correlation import get_correlation_service
from ..services.tradingview_webhook import get_webhook_service
from ..core.audit_log import get_audit_service

router = APIRouter(prefix="/api/v1/pro", tags=["Pro Trading"])


# ── Options Strategy Builder ────────────────────────────────

@router.get("/strategies/list")
async def list_strategies(user=Depends(get_current_user)):
    """List all available options strategies."""
    builder = get_strategy_builder()
    return {"strategies": builder.get_available_strategies()}


@router.get("/strategies/build/{symbol}")
async def build_strategy(
    symbol: str,
    strategy: str = Query(..., description="Strategy name (e.g. iron_condor, long_straddle)"),
    width: float = Query(100, description="Strike width for multi-leg strategies"),
    user=Depends(get_current_user),
):
    """Build an options strategy with payoff analysis.

    Returns legs, payoff curve, max P/L, breakevens, and risk/reward.
    """
    builder = get_strategy_builder()
    try:
        result = builder.build_strategy(symbol, strategy, width=width)
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Strategy build failed: {str(e)}")


# ── Earnings Calendar ───────────────────────────────────────

@router.get("/earnings/upcoming")
async def upcoming_earnings(
    days: int = Query(30, le=90),
    user=Depends(get_current_user),
):
    """Get upcoming earnings dates for NIFTY 50 stocks."""
    svc = get_earnings_service()
    try:
        events = await svc.get_upcoming_earnings(days=days)
        return {"count": len(events), "events": [e.to_dict() for e in events]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Earnings error: {str(e)}")


@router.get("/earnings/reaction/{symbol}")
async def earnings_reaction(symbol: str, user=Depends(get_current_user)):
    """Predict post-earnings price reaction based on historical patterns."""
    svc = get_earnings_service()
    try:
        result = await svc.get_earnings_reaction(symbol)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Earnings reaction error: {str(e)}")


# ── Market Breadth & Heatmap ────────────────────────────────

@router.get("/breadth")
async def market_breadth(user=Depends(get_current_user)):
    """Get market breadth: A/D ratio, 52W highs/lows, sentiment, heatmap."""
    svc = get_market_breadth_service()
    try:
        result = await svc.get_breadth()
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market breadth error: {str(e)}")


# ── Multi-Timeframe Analysis ───────────────────────────────

@router.get("/multi-timeframe/{symbol}")
async def multi_timeframe_analysis(symbol: str, user=Depends(get_current_user)):
    """Analyze a stock across 5m, 15m, 1h, 1d timeframes.

    Returns confluence score, individual timeframe signals, and overall recommendation.
    """
    svc = get_multi_timeframe_service()
    try:
        result = await svc.analyze(symbol)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Multi-TF error: {str(e)}")


# ── Portfolio Correlation ───────────────────────────────────

class CorrelationRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=2, max_length=20)
    period: str = Field("6mo", pattern="^(3mo|6mo|1y|2y)$")


@router.post("/correlation")
async def portfolio_correlation(request: CorrelationRequest, user=Depends(get_current_user)):
    """Compute correlation matrix for a portfolio.

    Returns NxN matrix, high-correlation pairs, and diversification score.
    """
    svc = get_correlation_service()
    try:
        result = await svc.analyze(request.symbols, period=request.period)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Correlation error: {str(e)}")


# ── TradingView Webhook ─────────────────────────────────────

class WebhookPayload(BaseModel):
    action: str = Field(..., pattern="^(BUY|SELL|CLOSE)$")
    symbol: str
    price: float = 0.0
    quantity: int = 1
    strategy: str = "tradingview_alert"
    timeframe: str = ""
    message: str = ""


@router.post("/webhook/tradingview")
async def tradingview_webhook(
    payload: WebhookPayload,
    request: Request,
    auto_execute: bool = Query(False, description="Auto-execute trade"),
    user=Depends(get_current_user),
):
    """Receive TradingView webhook alerts and optionally auto-execute trades."""
    svc = get_webhook_service()
    audit = get_audit_service()

    signal = svc.parse_webhook(payload.model_dump(), auto_execute=auto_execute)
    audit.log("webhook_received", details=signal.to_dict())

    result = {"signal": signal.to_dict(), "executed": False}

    if auto_execute:
        exec_result = await svc.execute_signal(signal)
        result["execution"] = exec_result
        result["executed"] = exec_result.get("status") == "executed"
        audit.log("trade_placed", details=exec_result)

    return result


@router.get("/webhook/history")
async def webhook_history(
    limit: int = Query(50, le=200),
    user=Depends(get_current_user),
):
    """Get recent TradingView webhook signals."""
    svc = get_webhook_service()
    signals = svc.get_recent_signals(limit)
    return {"count": len(signals), "signals": [s.to_dict() for s in signals]}


# ── Audit Log ───────────────────────────────────────────────

@router.get("/audit")
async def get_audit_log(
    action: str = Query(None, description="Filter by action type"),
    severity: str = Query(None, pattern="^(info|warning|critical)$"),
    limit: int = Query(100, le=500),
    user=Depends(get_current_user),
):
    """Query the audit log with optional filters."""
    audit = get_audit_service()
    entries = audit.query(action=action, severity=severity, limit=limit)
    return {"count": len(entries), "entries": [e.to_dict() for e in entries]}


@router.get("/audit/summary")
async def audit_summary(user=Depends(get_current_user)):
    """Get audit log summary with action counts."""
    audit = get_audit_service()
    return audit.get_summary()
