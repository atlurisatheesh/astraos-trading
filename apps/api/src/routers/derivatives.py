"""AstraOS Routers — F&O Options Chain & Derivatives API."""

from fastapi import APIRouter, Depends, Query, HTTPException

from ..core.dependencies import get_current_user
from ..services.derivatives_service import get_derivatives_service

router = APIRouter(prefix="/api/v1/derivatives", tags=["Derivatives F&O"])


@router.get("/options-chain/{symbol}")
async def get_options_chain(
    symbol: str,
    expiry: str | None = Query(None, description="Specific expiry date (e.g. 2026-03-26)"),
    greeks: bool = Query(True, description="Compute Greeks for each contract"),
    user=Depends(get_current_user),
):
    """Get full options chain with OI, IV, LTP, and computed Greeks.

    Returns calls and puts for all strikes, plus analytics:
    PCR, max pain, total OI, and sentiment interpretation.
    """
    svc = get_derivatives_service()
    try:
        chain = await svc.get_options_chain(symbol, expiry=expiry, compute_greeks=greeks)
        return chain.to_dict()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Derivatives data error: {str(e)}")


@router.get("/pcr/{symbol}")
async def get_pcr(symbol: str, user=Depends(get_current_user)):
    """Get Put-Call Ratio analysis with sentiment interpretation.

    PCR > 1.2 = Bullish (put writers confident)
    PCR 0.8-1.2 = Neutral
    PCR < 0.8 = Bearish (call writers dominating)
    """
    svc = get_derivatives_service()
    try:
        return await svc.get_pcr(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"PCR calculation error: {str(e)}")


@router.get("/max-pain/{symbol}")
async def get_max_pain(
    symbol: str,
    expiry: str | None = Query(None),
    user=Depends(get_current_user),
):
    """Calculate max pain — the strike where option writers lose least.

    Max pain theory: price tends to converge toward this strike at expiry.
    """
    svc = get_derivatives_service()
    try:
        return await svc.get_max_pain(symbol, expiry=expiry)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Max pain calculation error: {str(e)}")


@router.get("/iv-surface/{symbol}")
async def get_iv_surface(symbol: str, user=Depends(get_current_user)):
    """Get implied volatility surface across strikes.

    Returns IV data points with moneyness for visualization.
    """
    svc = get_derivatives_service()
    try:
        points = await svc.get_iv_surface(symbol)
        return {
            "symbol": symbol,
            "count": len(points),
            "surface": [p.to_dict() for p in points],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"IV surface error: {str(e)}")


@router.get("/oi-analysis/{symbol}")
async def get_oi_analysis(symbol: str, user=Depends(get_current_user)):
    """Get Open Interest analysis for support/resistance levels.

    Identifies:
    - Max call OI strike → resistance
    - Max put OI strike → support
    - Top 5 strikes by OI for calls and puts
    """
    svc = get_derivatives_service()
    try:
        return await svc.get_oi_analysis(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OI analysis error: {str(e)}")
