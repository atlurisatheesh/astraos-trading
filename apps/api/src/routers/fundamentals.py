"""AstraOS Routers — Deep Fundamentals & Corporate Actions API."""

from fastapi import APIRouter, Depends, Query, HTTPException

from ..core.dependencies import get_current_user
from ..services.fundamentals_service import get_fundamentals_service

router = APIRouter(prefix="/api/v1/fundamentals", tags=["Fundamentals"])


@router.get("/ratios/{symbol}")
async def get_ratios(symbol: str, user=Depends(get_current_user)):
    """Get key financial ratios: P/E, EPS, P/B, PEG, D/E, ROE, margins, etc."""
    svc = get_fundamentals_service()
    try:
        ratios = await svc.get_ratios(symbol)
        return ratios.to_dict()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch ratios: {str(e)}")


@router.get("/profile/{symbol}")
async def get_profile(symbol: str, user=Depends(get_current_user)):
    """Get company profile: sector, industry, description, employees, etc."""
    svc = get_fundamentals_service()
    try:
        profile = await svc.get_profile(symbol)
        return profile.to_dict()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch profile: {str(e)}")


@router.get("/income-statement/{symbol}")
async def get_income_statement(
    symbol: str,
    quarterly: bool = Query(False, description="Quarterly (True) or Annual (False)"),
    user=Depends(get_current_user),
):
    """Get income statement (quarterly or annual)."""
    svc = get_fundamentals_service()
    try:
        data = await svc.get_income_statement(symbol, quarterly=quarterly)
        return {"symbol": symbol, "quarterly": quarterly, "periods": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch income statement: {str(e)}")


@router.get("/balance-sheet/{symbol}")
async def get_balance_sheet(
    symbol: str,
    quarterly: bool = Query(False),
    user=Depends(get_current_user),
):
    """Get balance sheet (quarterly or annual)."""
    svc = get_fundamentals_service()
    try:
        data = await svc.get_balance_sheet(symbol, quarterly=quarterly)
        return {"symbol": symbol, "quarterly": quarterly, "periods": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch balance sheet: {str(e)}")


@router.get("/cash-flow/{symbol}")
async def get_cash_flow(
    symbol: str,
    quarterly: bool = Query(False),
    user=Depends(get_current_user),
):
    """Get cash flow statement (quarterly or annual)."""
    svc = get_fundamentals_service()
    try:
        data = await svc.get_cash_flow(symbol, quarterly=quarterly)
        return {"symbol": symbol, "quarterly": quarterly, "periods": len(data), "data": data}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch cash flow: {str(e)}")


@router.get("/corporate-actions/{symbol}")
async def get_corporate_actions(symbol: str, user=Depends(get_current_user)):
    """Get corporate actions: dividends, splits, earnings dates."""
    svc = get_fundamentals_service()
    try:
        actions = await svc.get_corporate_actions(symbol)
        return {
            "symbol": symbol,
            "count": len(actions),
            "actions": [a.to_dict() for a in actions],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch corporate actions: {str(e)}")


@router.get("/analyst/{symbol}")
async def get_analyst_recommendations(symbol: str, user=Depends(get_current_user)):
    """Get analyst recommendations and target prices."""
    svc = get_fundamentals_service()
    try:
        recs = await svc.get_analyst_recommendations(symbol)
        return {"symbol": symbol, "count": len(recs), "recommendations": recs}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch recommendations: {str(e)}")


@router.get("/snapshot/{symbol}")
async def get_fundamentals_snapshot(symbol: str, user=Depends(get_current_user)):
    """Get a complete fundamental snapshot: profile + ratios + corporate actions."""
    svc = get_fundamentals_service()
    try:
        ratios = await svc.get_ratios(symbol)
        profile = await svc.get_profile(symbol)
        actions = await svc.get_corporate_actions(symbol)

        return {
            "symbol": symbol,
            "profile": profile.to_dict(),
            "ratios": ratios.to_dict(),
            "corporate_actions": [a.to_dict() for a in actions],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch snapshot: {str(e)}")
