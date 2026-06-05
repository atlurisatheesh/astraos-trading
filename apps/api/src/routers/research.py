"""AstraOS Routers — AI Research API (multi-agent analysis)."""

from fastapi import APIRouter, Depends, Query

from ..core.dependencies import get_current_user
from ..agents.orchestrator import run_research_pipeline

router = APIRouter(prefix="/api/v1/research", tags=["AI Research"])


@router.get("/analyze/{symbol}")
async def analyze_stock(symbol: str, user=Depends(get_current_user)):
    """Run full multi-agent research pipeline on a symbol.

    Executes 5 AI agents in parallel (Technical, Derivatives, Sentiment,
    Macro, Sector), then synthesizes a final BUY/SELL/HOLD signal with
    entry, target, and stop-loss levels.
    """
    signal = await run_research_pipeline(symbol)
    return signal.to_dict()


@router.get("/batch")
async def batch_analyze(
    symbols: str = Query(..., description="Comma-separated symbols"),
    user=Depends(get_current_user),
):
    """Run research pipeline on multiple symbols."""
    import asyncio
    symbol_list = [s.strip() for s in symbols.split(",")][:10]  # Max 10

    results = await asyncio.gather(
        *[run_research_pipeline(s) for s in symbol_list],
        return_exceptions=True,
    )

    output = []
    for s, r in zip(symbol_list, results):
        if isinstance(r, Exception):
            output.append({"symbol": s, "error": str(r)})
        else:
            output.append(r.to_dict())

    return {"count": len(output), "signals": output}


@router.post("/chat")
async def chat_with_analyst(
    data: dict,
    user=Depends(get_current_user),
):
    """Interactive AI analyst chat — answers questions about stocks/strategies."""
    from ..agents.gpt_agent import analyst_chat

    message = data.get("message", "")
    if not message:
        return {"reply": "Please provide a message."}

    history = data.get("history", [])
    try:
        reply = await analyst_chat(message, history)
    except Exception:
        reply = (
            "I'm currently unable to process your request with the AI model. "
            "Please check that OPENAI_API_KEY or GEMINI_API_KEY is configured.\n\n"
            "In the meantime, you can use the /api/v1/research/analyze/{symbol} "
            "endpoint for automated multi-agent analysis."
        )
    return {"reply": reply}


@router.get("/patterns/{symbol}")
async def detect_chart_patterns(symbol: str, user=Depends(get_current_user)):
    """Use AI to detect chart patterns from OHLCV data."""
    from ..agents.gpt_agent import detect_patterns
    from ..services.market_data_service import MarketDataService

    svc = MarketDataService()
    try:
        ohlcv = await svc.get_ohlcv(symbol)
        patterns = await detect_patterns(symbol, ohlcv)
        return {"symbol": symbol, "patterns": patterns}
    except Exception as exc:
        return {"symbol": symbol, "patterns": [], "error": str(exc)}
