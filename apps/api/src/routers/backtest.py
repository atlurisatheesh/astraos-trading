"""AstraOS Routers — Backtesting API."""

from fastapi import APIRouter, Depends, Query, HTTPException

from ..core.dependencies import get_current_user
from ..services.market_data_service import get_market_data_provider
from ..knowledge.veteran_intraday_playbook import (
    baseline_intraday_orb_strategy,
    is_veteran_scalp_symbol,
    veteran_intraday_orb_strategy,
)
from ..quant.backtester import compare_backtests, simple_momentum_strategy, walk_forward_backtest
from ..quant.regime_detector import PositionSizer

router = APIRouter(prefix="/api/v1/backtest", tags=["Backtest"])


@router.get("/{symbol}")
async def run_backtest(
    symbol: str,
    strategy: str = Query("momentum", description="momentum | veteran_intraday | veteran_intraday_compare"),
    period: str = Query("2y"),
    user=Depends(get_current_user),
):
    """Run Walk-Forward + Monte Carlo backtest on a symbol."""
    provider = get_market_data_provider()
    train_window = 252
    test_window = 63
    step = 21

    if strategy in {"veteran_intraday", "veteran_intraday_compare"}:
        if not is_veteran_scalp_symbol(symbol):
            raise HTTPException(status_code=400, detail="Veteran intraday strategy supports only NIFTY and BANKNIFTY")
        intraday_period = period if period != "2y" else "60d"
        df = await provider.get_ohlcv(symbol, interval="5m", period=intraday_period)
        train_window = 300
        test_window = 120
        step = 60
        if df.empty or len(df) < 450:
            raise HTTPException(status_code=400, detail=f"Need 450+ intraday bars. Got {len(df)}")

        if strategy == "veteran_intraday_compare":
            comparison = compare_backtests(
                df,
                baseline_intraday_orb_strategy,
                veteran_intraday_orb_strategy,
                train_window=train_window,
                test_window=test_window,
                step=step,
            )
            return {
                "symbol": symbol,
                "strategy": strategy,
                "interval": "5m",
                "playbook": "veteran_intraday_orb",
                **comparison["filtered"],
                "comparison": comparison,
            }

        result = walk_forward_backtest(
            df,
            veteran_intraday_orb_strategy,
            train_window=train_window,
            test_window=test_window,
            step=step,
        )
        return {
            "symbol": symbol,
            "strategy": strategy,
            "interval": "5m",
            "playbook": "veteran_intraday_orb",
            **result.to_dict(),
        }

    df = await provider.get_ohlcv(symbol, period=period)
    if df.empty or len(df) < 300:
        raise HTTPException(status_code=400, detail=f"Need 300+ days of data. Got {len(df)}")

    strategies = {"momentum": simple_momentum_strategy}
    strategy_fn = strategies.get(strategy, simple_momentum_strategy)

    result = walk_forward_backtest(df, strategy_fn)
    return {"symbol": symbol, "strategy": strategy, **result.to_dict()}


@router.get("/position-size")
async def get_position_size(
    win_rate: float = Query(..., ge=0, le=1),
    avg_win: float = Query(...), avg_loss: float = Query(...),
    capital: float = Query(...),
    user=Depends(get_current_user),
):
    """Calculate optimal position size using Kelly Criterion."""
    sizer = PositionSizer()
    return sizer.calculate(win_rate, avg_win, avg_loss, capital)
