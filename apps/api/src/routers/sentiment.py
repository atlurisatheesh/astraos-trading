"""AstraOS Routers — Sentiment Analysis API (FinBERT NLP)."""

from fastapi import APIRouter, Depends, Query, Body
from pydantic import BaseModel

from ..core.dependencies import get_current_user
from ..nlp.finbert import get_finbert

router = APIRouter(prefix="/api/v1/sentiment", tags=["Sentiment NLP"])


class TextInput(BaseModel):
    texts: list[str]


@router.post("/analyze")
async def analyze_sentiment(
    input_data: TextInput,
    user=Depends(get_current_user),
):
    """Analyze sentiment of one or more texts using FinBERT.

    Returns 3-class probabilities (positive, negative, neutral)
    for each text. Uses ProsusAI/finbert model locally.
    """
    analyzer = get_finbert()
    results = await analyzer.analyze_batch(input_data.texts)
    return {
        "model": "ProsusAI/finbert",
        "count": len(results),
        "results": [r.to_dict() for r in results],
    }


@router.get("/news")
async def analyze_news_sentiment(
    query: str = Query("India stock market"),
    limit: int = Query(10, le=30),
    user=Depends(get_current_user),
):
    """Fetch news and analyze sentiment using FinBERT.

    Combines news ingestion + NLP in a single endpoint.
    """
    from ..services.news_service import get_news_provider

    provider = get_news_provider()
    news = await provider.fetch_news(query=query, limit=limit)

    analyzer = get_finbert()
    news_dicts = [n.to_dict() for n in news]
    enriched = await analyzer.analyze_news_items(news_dicts)

    # Aggregate sentiment
    positive = sum(1 for n in enriched if n.get("sentiment", {}).get("label") == "positive")
    negative = sum(1 for n in enriched if n.get("sentiment", {}).get("label") == "negative")
    neutral = sum(1 for n in enriched if n.get("sentiment", {}).get("label") == "neutral")

    return {
        "query": query,
        "count": len(enriched),
        "aggregate": {
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "overall": "bullish" if positive > negative else "bearish" if negative > positive else "neutral",
        },
        "items": enriched,
    }
