"""AstraOS Routers — Advanced Stock Screener API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.dependencies import get_current_user
from ..services.screener_engine import (
    ScreenerQuery,
    get_screener_engine,
    NIFTY_50_SYMBOLS,
    ALL_FIELDS,
    VALID_OPERATORS,
)

router = APIRouter(prefix="/api/v1/screener", tags=["Screener"])


class FilterItem(BaseModel):
    field: str = Field(..., description="Field to filter on")
    op: str = Field(..., description="Comparison operator: >, >=, <, <=, ==, !=")
    value: float = Field(..., description="Value to compare against")


class ScreenRequest(BaseModel):
    filters: list[FilterItem] = Field(..., min_length=1, max_length=10)
    logic: str = Field("AND", pattern="^(AND|OR)$")
    sort_by: str = Field("market_cap", description="Field to sort results by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
    limit: int = Field(50, ge=1, le=200)
    universe: list[str] | None = Field(None, description="Custom stock universe (symbols)")


@router.post("/screen")
async def screen_stocks(
    request: ScreenRequest,
    user=Depends(get_current_user),
):
    """Execute a stock screener query with fundamental + technical filters.

    Example request body:
    ```json
    {
        "filters": [
            {"field": "market_cap", "op": ">", "value": 100000000000},
            {"field": "trailing_pe", "op": "<", "value": 20},
            {"field": "rsi_14", "op": ">", "value": 60}
        ],
        "logic": "AND",
        "sort_by": "market_cap",
        "sort_order": "desc",
        "limit": 50
    }
    ```
    """
    query = ScreenerQuery.from_dict(request.model_dump())
    errors = query.validate()
    if errors:
        raise HTTPException(status_code=422, detail={"validation_errors": errors})

    engine = get_screener_engine()
    universe = request.universe or NIFTY_50_SYMBOLS

    results = await engine.screen(query, universe=universe)

    return {
        "count": len(results),
        "filters_applied": len(request.filters),
        "logic": request.logic,
        "universe_size": len(universe),
        "results": [r.to_dict() for r in results],
    }


@router.get("/fields")
async def get_available_fields(user=Depends(get_current_user)):
    """Get all available screener filter fields and operators."""
    return {
        "fields": sorted(ALL_FIELDS),
        "operators": sorted(VALID_OPERATORS),
        "logic_options": ["AND", "OR"],
        "categories": {
            "fundamental": sorted([
                "market_cap", "trailing_pe", "forward_pe", "eps", "price_to_book",
                "peg_ratio", "dividend_yield", "roe", "roa", "debt_to_equity",
                "current_ratio", "profit_margin", "operating_margin", "revenue_growth",
                "earnings_growth", "beta",
            ]),
            "technical": sorted([
                "rsi_14", "sma_20", "sma_50", "sma_200", "ema_20", "ema_50",
                "macd", "macd_signal", "macd_hist", "adx", "atr",
                "bb_upper", "bb_lower", "bb_middle", "volume_avg",
                "above_sma_50", "above_sma_200",
            ]),
            "price": sorted([
                "last_price", "change_pct", "year_high", "year_low", "volume",
            ]),
        },
    }


@router.get("/presets")
async def get_screener_presets(user=Depends(get_current_user)):
    """Get pre-built screener filters for common strategies."""
    return {
        "presets": [
            {
                "name": "Value Picks",
                "description": "Low P/E, high dividend yield stocks",
                "filters": [
                    {"field": "trailing_pe", "op": "<", "value": 15},
                    {"field": "dividend_yield", "op": ">", "value": 0.02},
                    {"field": "roe", "op": ">", "value": 0.12},
                ],
                "logic": "AND",
            },
            {
                "name": "Growth Momentum",
                "description": "High revenue growth with technical strength",
                "filters": [
                    {"field": "revenue_growth", "op": ">", "value": 0.15},
                    {"field": "rsi_14", "op": ">", "value": 50},
                    {"field": "above_sma_50", "op": "==", "value": 1},
                ],
                "logic": "AND",
            },
            {
                "name": "Large Cap Quality",
                "description": "Large cap with strong fundamentals",
                "filters": [
                    {"field": "market_cap", "op": ">", "value": 500000000000},
                    {"field": "roe", "op": ">", "value": 0.15},
                    {"field": "debt_to_equity", "op": "<", "value": 100},
                ],
                "logic": "AND",
            },
            {
                "name": "Oversold Bounce",
                "description": "Technically oversold stocks near support",
                "filters": [
                    {"field": "rsi_14", "op": "<", "value": 30},
                    {"field": "trailing_pe", "op": "<", "value": 25},
                ],
                "logic": "AND",
            },
            {
                "name": "Breakout Candidates",
                "description": "Stocks crossing key moving averages",
                "filters": [
                    {"field": "above_sma_200", "op": "==", "value": 1},
                    {"field": "rsi_14", "op": ">", "value": 55},
                    {"field": "macd_hist", "op": ">", "value": 0},
                ],
                "logic": "AND",
            },
        ],
    }
