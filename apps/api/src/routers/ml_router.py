# type: ignore
"""AstraOS Router — ML Model Training, Prediction & Registry.

Enhanced with model registry, on-demand training, and versioned management.
"""

import threading
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/ml", tags=["Machine Learning"])


# ═══════════════════════════════════════════════════════════════
# Training
# ═══════════════════════════════════════════════════════════════

def _run_training(
    symbols: list[str],
    period: str,
    forward_days: int = 5,
    threshold: float = 1.5,
):
    """Wrapper to run sync training + model registration in a thread."""
    from ..ml.trainer import train_signal_model_sync, get_training_status, MODEL_PATH
    from ..ml.model_registry import register_model

    train_signal_model_sync(symbols, period,
                            forward_days=forward_days, threshold=threshold)

    status = get_training_status()
    if status.get("status") == "completed" and status.get("metrics"):
        try:
            register_model(MODEL_PATH, status["metrics"])
        except Exception:
            pass


@router.post("/train")
async def train_model(
    symbols: str = "RELIANCE,TCS,HDFCBANK,ICICIBANK,INFY",
    period: str = "2y",
):
    """Trigger XGBoost model training on historical data.

    Args:
        symbols: Comma-separated list of NSE symbols
        period: Historical data period (1y, 2y, 5y)
    """
    symbol_list = [s.strip() for s in symbols.split(",")]

    t = threading.Thread(target=_run_training, args=(symbol_list, period), daemon=True)
    t.start()

    return {
        "status": "training_started",
        "symbols": symbol_list,
        "period": period,
        "message": "Model training started in background. Check /api/v1/ml/status for progress.",
    }


@router.post("/train/nifty50")
async def train_nifty50(period: str = "2y"):
    """Train the model on the full NIFTY 50 universe.

    This is the recommended training target for comprehensive coverage.
    """
    from ..ml.training_scheduler import NIFTY_50

    t = threading.Thread(target=_run_training, args=(NIFTY_50, period), daemon=True)
    t.start()

    return {
        "status": "training_started",
        "symbols": len(NIFTY_50),
        "period": period,
        "message": f"Training on {len(NIFTY_50)} NIFTY 50 stocks. Check /api/v1/ml/status for progress.",
    }


@router.get("/status")
async def model_status():
    """Get current model training status and metrics."""
    from ..ml.trainer import get_training_status
    return get_training_status()


# ═══════════════════════════════════════════════════════════════
# Prediction
# ═══════════════════════════════════════════════════════════════

@router.post("/predict")
async def predict_post(symbol: str = "RELIANCE"):
    """Get ML-based BUY/SELL/HOLD prediction for a symbol (POST)."""
    from ..ml.predictor import predict_signal
    return await predict_signal(symbol)


@router.get("/predict")
async def predict_get(symbol: str = "RELIANCE"):
    """Get ML-based BUY/SELL/HOLD prediction for a symbol (GET).

    The frontend calls GET /api/v1/ml/predict?symbol=RELIANCE, so we expose
    both GET and POST to be safe.
    """
    from ..ml.predictor import predict_signal
    return await predict_signal(symbol)


@router.get("/debug/features")
async def debug_features(symbol: str = "RELIANCE"):
    """Debug endpoint: test feature building for a single symbol."""
    import traceback
    try:
        from ..services.market_data_service import get_market_data_provider
        from ..ml.feature_builder import build_features

        provider = get_market_data_provider()
        df = await provider.get_ohlcv(symbol, period="1y")
        
        result = {
            "ohlcv_shape": list(df.shape),
            "ohlcv_columns": df.columns.tolist(),
            "ohlcv_rows": len(df),
        }
        
        features = build_features(df)
        result["features_shape"] = list(features.shape)
        result["features_empty"] = features.empty
        
        if not features.empty:
            result["label_distribution"] = features["label"].value_counts().to_dict()
            result["feature_count"] = len(features.columns) - 1
            result["sample_count"] = len(features)
        
        return result
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}


@router.post("/predict/batch")
async def predict_batch(symbols: str = "RELIANCE,TCS,INFY,HDFCBANK,SBIN"):
    """Get ML predictions for multiple symbols at once."""
    from ..ml.predictor import predict_signal
    
    symbol_list = [s.strip() for s in symbols.split(",")]
    results = []
    for sym in symbol_list:
        result = await predict_signal(sym)
        results.append(result)
    
    # Summary stats
    buy_count = sum(1 for r in results if r.get("action") == "BUY")
    sell_count = sum(1 for r in results if r.get("action") == "SELL")
    hold_count = sum(1 for r in results if r.get("action") == "HOLD")
    
    return {
        "predictions": results,
        "summary": {
            "total": len(results),
            "buy": buy_count,
            "sell": sell_count,
            "hold": hold_count,
            "bullish_ratio": round(buy_count / max(len(results), 1) * 100, 1),
        },
    }


# ═══════════════════════════════════════════════════════════════
# Model Registry
# ═══════════════════════════════════════════════════════════════

@router.get("/models")
async def list_all_models():
    """List all trained model versions with metrics."""
    from ..ml.model_registry import list_models, get_active_model_info
    
    models = list_models()
    active = get_active_model_info()
    
    return {
        "models": models,
        "active": active,
        "total_versions": len(models),
    }


@router.get("/models/active")
async def get_active_model():
    """Get details about the currently active (deployed) model."""
    from ..ml.model_registry import get_active_model_info
    
    info = get_active_model_info()
    if not info:
        return {"error": "No active model. Train first via POST /api/v1/ml/train/nifty50"}
    return info


@router.post("/models/{version}/rollback")
async def rollback_model(version: int):
    """Rollback to a previous model version.
    
    Use this if the latest model is underperforming.
    """
    from ..ml.model_registry import rollback_model as do_rollback
    return do_rollback(version)


@router.post("/models/{version}/promote")
async def promote_model(version: int):
    """Manually promote a specific model version to active."""
    from ..ml.model_registry import promote_model as do_promote
    
    success = do_promote(version)
    if success:
        return {"status": "promoted", "active_version": version}
    return {"status": "failed", "error": f"Version {version} not found"}
