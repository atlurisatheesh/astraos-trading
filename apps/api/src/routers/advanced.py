# type: ignore
"""AstraOS Routers — Institutional Flows, Bulk Deals, Sector Rotation, Chart Patterns."""

from fastapi import APIRouter, Depends, Query, HTTPException

from ..core.dependencies import get_current_user
from ..services.institutional_flows import get_institutional_flow_service
from ..services.bulk_deals import get_bulk_deal_service
from ..services.sector_rotation import get_sector_rotation_service
from ..ml.pattern_detector import get_pattern_detector

router = APIRouter(prefix="/api/v1/advanced", tags=["Advanced Analytics"])


# ── FII/DII Institutional Flows ─────────────────────────────

@router.get("/fii-dii")
async def get_fii_dii_flows(
    days: int = Query(20, le=60),
    user=Depends(get_current_user),
):
    """Get FII/DII institutional flow data with trend analysis.

    Returns net buy/sell values, 5-day/20-day rolling trends,
    and flow reversal alerts.
    """
    svc = get_institutional_flow_service()
    try:
        analysis = await svc.get_flows(days=days)
        return analysis.to_dict()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"FII/DII data error: {str(e)}")


@router.get("/fii-dii/today")
async def get_fii_dii_today(user=Depends(get_current_user)):
    """Get today's FII/DII buy/sell data."""
    svc = get_institutional_flow_service()
    try:
        return await svc.get_today()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"FII/DII data error: {str(e)}")


# ── Bulk / Block Deals ──────────────────────────────────────

@router.get("/bulk-deals")
async def get_bulk_deals(
    deal_type: str = Query("all", pattern="^(all|bulk|block)$"),
    limit: int = Query(50, le=200),
    user=Depends(get_current_user),
):
    """Get recent bulk and block deals from NSE.

    Bulk deals: >0.5% of shares traded in single order.
    Block deals: Large off-market negotiated trades.
    """
    svc = get_bulk_deal_service()
    try:
        deals = await svc.get_deals(deal_type=deal_type, limit=limit)
        return {"count": len(deals), "deals": [d.to_dict() for d in deals]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Bulk deal error: {str(e)}")


@router.get("/bulk-deals/symbol/{symbol}")
async def get_bulk_deals_by_symbol(
    symbol: str,
    user=Depends(get_current_user),
):
    """Get bulk/block deals for a specific symbol."""
    svc = get_bulk_deal_service()
    try:
        deals = await svc.get_deals_by_symbol(symbol)
        return {"symbol": symbol, "count": len(deals), "deals": [d.to_dict() for d in deals]}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Bulk deal error: {str(e)}")


@router.get("/bulk-deals/smart-money")
async def get_smart_money_signals(user=Depends(get_current_user)):
    """Get smart money signals derived from bulk/block deal patterns.

    Detects accumulation (multiple buys) and distribution (multiple sells).
    """
    svc = get_bulk_deal_service()
    try:
        signals = await svc.get_smart_money_signals()
        return {"count": len(signals), "signals": signals}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Smart money error: {str(e)}")


# ── Sector Rotation ─────────────────────────────────────────

@router.get("/sector-rotation")
async def get_sector_rotation(user=Depends(get_current_user)):
    """Get sector rotation analysis across 12 NIFTY sectoral indices.

    Returns momentum scores, relative strength vs NIFTY 50,
    rotation phase (leading/weakening/lagging/improving),
    and sector rotation recommendations.
    """
    svc = get_sector_rotation_service()
    try:
        analysis = await svc.analyze()
        return analysis.to_dict()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Sector rotation error: {str(e)}")


# ── Chart Pattern Recognition ───────────────────────────────

@router.get("/patterns/{symbol}")
async def detect_chart_patterns(
    symbol: str,
    period: str = Query("6mo", pattern="^(3mo|6mo|1y|2y)$"),
    user=Depends(get_current_user),
):
    """Detect chart patterns in a stock's price history.

    Detects: Double Top/Bottom, Head & Shoulders, Ascending/Descending Triangle,
    Bull/Bear Flag, Rising/Falling Wedge.

    Returns patterns sorted by confidence with target prices and stop losses.
    """
    detector = get_pattern_detector()
    try:
        patterns = detector.detect_all(symbol, period=period)
        return {
            "symbol": symbol,
            "period": period,
            "patterns_found": len(patterns),
            "patterns": [p.to_dict() for p in patterns],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Pattern detection error: {str(e)}")
