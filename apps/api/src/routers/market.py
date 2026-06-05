"""AstraOS Routers — Market Data API (real stock data via yfinance)."""

from fastapi import APIRouter, Depends, Query, HTTPException

from ..core.dependencies import get_current_user
from ..services.market_data_service import get_market_data_provider
from ..quant.technical import compute_all_indicators, get_signal_summary
from ..quant.options_pricer import black_scholes, calculate_pcr
from ..quant.regime_detector import RegimeDetector

router = APIRouter(prefix="/api/v1/market", tags=["Market Data"])


@router.get("/quote/{symbol}")
async def get_quote(symbol: str, user=Depends(get_current_user)):
    """Get real-time (delayed) quote for a symbol."""
    provider = get_market_data_provider()
    try:
        quote = await provider.get_quote(symbol)
        return quote.to_dict()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Market data error: {str(e)}")


@router.get("/quotes")
async def get_multiple_quotes(
    symbols: str = Query(..., description="Comma-separated symbols"),
    user=Depends(get_current_user),
):
    """Get quotes for multiple symbols."""
    symbol_list = [s.strip() for s in symbols.split(",")]
    provider = get_market_data_provider()
    quotes = await provider.get_multiple_quotes(symbol_list)
    return [q.to_dict() for q in quotes]


@router.get("/ohlcv/{symbol}")
async def get_ohlcv(
    symbol: str,
    interval: str = Query("1d", description="1m,5m,15m,1h,1d,1wk,1mo"),
    period: str = Query("1y", description="1d,5d,1mo,3mo,6mo,1y,2y,5y,max"),
    user=Depends(get_current_user),
):
    """Get historical OHLCV data."""
    provider = get_market_data_provider()
    df = await provider.get_ohlcv(symbol, interval=interval, period=period)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    return {
        "symbol": symbol,
        "interval": interval,
        "period": period,
        "count": len(df),
        "data": df.reset_index().to_dict(orient="records"),
    }


@router.get("/indicators/{symbol}")
async def get_indicators(
    symbol: str,
    period: str = Query("1y"),
    user=Depends(get_current_user),
):
    """Get 60+ technical indicators for a symbol."""
    provider = get_market_data_provider()
    df = await provider.get_ohlcv(symbol, period=period)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    indicators = compute_all_indicators(df)
    summary = get_signal_summary(indicators)

    return {
        "symbol": symbol,
        "summary": summary,
        "indicator_count": len([c for c in indicators.columns if c not in ["Open", "High", "Low", "Close", "Volume"]]),
        "latest": {k: (None if str(v) == "nan" else v) for k, v in indicators.iloc[-1].to_dict().items()},
    }


@router.get("/regime/{symbol}")
async def get_regime(symbol: str, user=Depends(get_current_user)):
    """Detect market regime: bull / bear / sideways / crisis."""
    provider = get_market_data_provider()
    df = await provider.get_ohlcv(symbol, period="6mo")
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")

    detector = RegimeDetector()
    return detector.detect(df)


@router.get("/greeks")
async def calculate_greeks(
    spot: float = Query(...), strike: float = Query(...),
    days_to_expiry: int = Query(...), iv: float = Query(...),
    option_type: str = Query("CE"),
    user=Depends(get_current_user),
):
    """Calculate option Greeks using Black-Scholes."""
    result = black_scholes(
        spot=spot, strike=strike,
        time_to_expiry=days_to_expiry / 365,
        risk_free_rate=0.065,  # RBI repo rate
        volatility=iv / 100,
        option_type=option_type,
    )
    return result.to_dict()


@router.get("/options-chain/{symbol}")
async def get_options_chain(symbol: str, user=Depends(get_current_user)):
    """Get options chain from yfinance."""
    provider = get_market_data_provider()
    return await provider.get_options_chain(symbol)
