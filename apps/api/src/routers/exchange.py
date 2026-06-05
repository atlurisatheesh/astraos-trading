"""AstraOS Routers — NSE/BSE Data Feed API."""

from fastapi import APIRouter, Depends, Query

from ..core.dependencies import get_current_user
from ..services.nse_bse_feed import get_nse_adapter, get_bse_adapter, FOCalendar

router = APIRouter(prefix="/api/v1/exchange", tags=["Exchange Data"])


# ── NSE Endpoints ──

@router.get("/nse/quote/{symbol}")
async def nse_quote(symbol: str, user=Depends(get_current_user)):
    """Get live quote from NSE official API."""
    nse = get_nse_adapter()
    quote = await nse.get_quote(symbol.upper())
    if not quote:
        return {"error": f"No NSE data for {symbol}"}
    return quote.to_dict()


@router.get("/nse/index/{index_name}")
async def nse_index(index_name: str = "NIFTY 50", user=Depends(get_current_user)):
    """Get live index data from NSE."""
    nse = get_nse_adapter()
    index = await nse.get_index(index_name)
    if not index:
        return {"error": f"No index data for {index_name}"}
    return index.to_dict()


@router.get("/nse/indices")
async def nse_all_indices(user=Depends(get_current_user)):
    """Get all NSE indices."""
    nse = get_nse_adapter()
    indices = await nse.get_all_indices()
    return {"count": len(indices), "indices": [i.to_dict() for i in indices]}


@router.get("/nse/option-chain/{symbol}")
async def nse_option_chain(symbol: str = "NIFTY", user=Depends(get_current_user)):
    """Get F&O option chain with OI and PCR from NSE."""
    nse = get_nse_adapter()
    return await nse.get_option_chain(symbol.upper())


@router.get("/nse/constituents")
async def nse_constituents(user=Depends(get_current_user)):
    """Get NIFTY 500 constituent list (instrument master)."""
    nse = get_nse_adapter()
    constituents = await nse.get_nifty500_constituents()
    return {"count": len(constituents), "constituents": constituents}


@router.get("/nse/corporate-actions/{symbol}")
async def nse_corporate_actions(symbol: str, user=Depends(get_current_user)):
    """Get upcoming corporate actions (dividends, splits, bonuses)."""
    nse = get_nse_adapter()
    actions = await nse.get_corporate_actions(symbol.upper())
    return {"symbol": symbol, "actions": actions}


# ── BSE Endpoints ──

@router.get("/bse/sensex")
async def bse_sensex(user=Depends(get_current_user)):
    """Get SENSEX index data from BSE."""
    bse = get_bse_adapter()
    return await bse.get_sensex()


@router.get("/bse/announcements")
async def bse_announcements(user=Depends(get_current_user)):
    """Get latest corporate announcements from BSE."""
    bse = get_bse_adapter()
    return await bse.get_announcements()


# ── F&O Calendar ──

@router.get("/fno/lot-sizes")
async def fno_lot_sizes(user=Depends(get_current_user)):
    """Get F&O lot sizes for all symbols."""
    return {"lot_sizes": FOCalendar.LOT_SIZES}


@router.get("/fno/lot-size/{symbol}")
async def fno_lot_size(symbol: str, user=Depends(get_current_user)):
    """Get lot size for a specific symbol."""
    return {
        "symbol": symbol.upper(),
        "lot_size": FOCalendar.get_lot_size(symbol),
    }


@router.get("/fno/expiry-calendar")
async def fno_expiry_calendar(
    months: int = Query(3, le=6),
    user=Depends(get_current_user),
):
    """Get upcoming F&O expiry dates (weekly + monthly)."""
    calendar = FOCalendar.get_expiry_calendar(months)
    return {
        "next_expiry": FOCalendar.get_next_expiry().isoformat(),
        "calendar": calendar,
    }
