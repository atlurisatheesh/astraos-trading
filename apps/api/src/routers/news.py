"""AstraOS Routers — News & Research API (Multi-Source).

Supports both the original RSS+GDELT provider and the new aggregated
multi-source provider (ET, Mint, MC, GDELT) with symbol tagging.
"""

from fastapi import APIRouter, Depends, Query

from ..core.dependencies import get_current_user
from ..services.news_service import get_news_provider
from ..services.news_providers import get_aggregated_news_provider, get_news_provider_by_name

router = APIRouter(prefix="/api/v1/news", tags=["News"])


@router.get("/")
async def get_news(
    query: str = Query("India stock market NSE BSE"),
    limit: int = Query(20, le=50),
    source: str = Query("aggregated", description="Provider: aggregated, economic_times, livemint, moneycontrol, gdelt, legacy"),
    user=Depends(get_current_user),
):
    """Fetch latest market news from multiple sources.

    Sources: Economic Times, LiveMint, Moneycontrol, GDELT.
    Use source=aggregated (default) for merged, deduplicated feed with symbol tagging.
    Use source=legacy for original RSS+GDELT provider.
    """
    if source == "legacy":
        provider = get_news_provider()
    else:
        provider = get_news_provider_by_name(source)

    items = await provider.fetch_news(query=query, limit=limit)
    return {"count": len(items), "source": source, "items": [i.to_dict() for i in items]}


@router.get("/symbol/{symbol}")
async def get_news_for_symbol(
    symbol: str,
    limit: int = Query(20, le=50),
    user=Depends(get_current_user),
):
    """Fetch news specifically related to a stock symbol.

    Uses the aggregated provider with symbol-aware filtering.
    Example: GET /api/v1/news/symbol/RELIANCE
    """
    provider = get_aggregated_news_provider()
    items = await provider.fetch_for_symbol(symbol, limit=limit)
    return {"symbol": symbol, "count": len(items), "items": [i.to_dict() for i in items]}


@router.get("/search")
async def search_news(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, le=30),
    user=Depends(get_current_user),
):
    """Search news by keyword across all sources."""
    provider = get_aggregated_news_provider()
    items = await provider.fetch_news(query=query, limit=limit)
    return {"query": query, "count": len(items), "items": [i.to_dict() for i in items]}


@router.get("/sources")
async def get_news_sources(user=Depends(get_current_user)):
    """List available news sources."""
    return {
        "sources": [
            {"id": "aggregated", "name": "All Sources (Aggregated)", "description": "Merged feed from ET, Mint, MC, GDELT with dedup and symbol tagging"},
            {"id": "economic_times", "name": "Economic Times", "description": "ET Markets, Economy, and Stocks RSS feeds"},
            {"id": "livemint", "name": "LiveMint", "description": "Mint Markets and Money RSS feeds"},
            {"id": "moneycontrol", "name": "Moneycontrol", "description": "MC Market Reports and Latest News RSS"},
            {"id": "gdelt", "name": "GDELT", "description": "Global structured news API (English)"},
            {"id": "legacy", "name": "Legacy (RSS+GDELT)", "description": "Original single-provider implementation"},
        ],
    }
