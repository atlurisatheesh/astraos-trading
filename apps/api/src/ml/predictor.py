"""AstraOS ML — Signal Predictor.

Loads the trained XGBoost model and predicts BUY/SELL/HOLD
with class probabilities for a given stock symbol.

Key design rules:
- Feature pipeline at inference MUST match the pipeline used during training.
  Both use feature_builder.build_features with the same forward_days/threshold
  values that were persisted inside the model artefact.
- Confidence thresholds are regime-aware: high-VIX markets require stronger
  conviction before emitting a directional signal.
"""

import pickle
from pathlib import Path  # noqa: F401

import numpy as np
import structlog

from .feature_builder import LABEL_NAMES
from ..core.config import ML_MODEL_DIR

logger = structlog.get_logger()

MODEL_DIR = ML_MODEL_DIR
MODEL_PATH = MODEL_DIR / "signal_model.pkl"

# Confidence threshold below which we default to HOLD (fallback defaults).
# When the model provides learned thresholds in its metrics, we use those.
_BASE_CONFIDENCE_THRESHOLD = 52.0
_HIGH_VOL_CONFIDENCE_THRESHOLD = 65.0

# ── Cached model ──────────────────────────────────────────────────────────────
_model_cache: dict | None = None


def _load_model() -> dict | None:
    """Load serialized model from disk (with process-level caching)."""
    global _model_cache

    if _model_cache is not None:
        return _model_cache

    if not MODEL_PATH.exists():
        logger.warning("No trained model found", path=str(MODEL_PATH))
        return None

    try:
        with open(MODEL_PATH, "rb") as f:
            _model_cache = pickle.load(f)
        logger.info(
            "Model loaded",
            trained_at=_model_cache.get("trained_at"),
            symbols=len(_model_cache.get("symbols", [])),
        )
        return _model_cache
    except Exception as e:
        logger.error("Failed to load model", error=str(e))
        return None


async def predict_signal(symbol: str) -> dict:
    """Predict BUY/SELL/HOLD for a symbol using the trained XGBoost model.

    Returns a standardised response envelope:
    {
        "symbol": "RELIANCE",
        "signal": "BUY",          # canonical field (action is an alias)
        "action": "BUY",          # kept for backward compatibility
        "confidence": 78.5,        # 0-100 scale
        "probabilities": {"SELL": 5.2, "HOLD": 16.3, "BUY": 78.5},
        "regime": "normal",        # bull | bear | sideways | crisis | unknown
        "model_accuracy": 72.3,
        "trained_at": "2026-...",
    }
    """
    model_data = _load_model()

    if model_data is None:
        return {
            "symbol": symbol,
            "signal": "HOLD",
            "action": "HOLD",
            "confidence": 0,
            "error": "No trained model. Train via POST /api/v1/ml/train/nifty50",
        }

    model = model_data["model"]
    feature_columns: list[str] = model_data["feature_columns"]

    # Use the same forward_days/threshold that were used during training.
    # Fall back to defaults if the model was created by the legacy script.
    forward_days: int = model_data.get("forward_days", 5)
    threshold: float = model_data.get("threshold", 1.5)

    try:
        from ..services.market_data_service import get_market_data_provider
        from .feature_builder import build_features
        from ..quant.regime_detector import RegimeDetector

        provider = get_market_data_provider()
        # Fetch 2 years so SMA_200 warmup is always satisfied
        df = await provider.get_ohlcv(symbol, period="2y")

        if df.empty:
            return {
                "symbol": symbol,
                "signal": "HOLD",
                "action": "HOLD",
                "confidence": 0,
                "error": "No market data available",
            }

        metrics = model_data.get("metrics", {}) or {}

        # ── Detect regime BEFORE feature building (uses same df) ────────────
        regime_info = RegimeDetector().detect(df)
        regime: str = regime_info.get("regime", "unknown")
        # Prefer the regime_crisis proxy from the feature pipeline, because
        # it matches training label logic.
        is_high_vol_by_detector = regime in ("crisis", "bear") or (
            regime_info.get("indicators", {}).get("volatility_20d", 0) > 28
        )

        # ── Build features for the current candle (no label computation) ──
        # This avoids using future prices in the feature pipeline.
        features = build_features(
            df,
            forward_days=forward_days,
            threshold=threshold,
            include_labels=False,
        )

        if features.empty:
            return {
                "symbol": symbol,
                "signal": "HOLD",
                "action": "HOLD",
                "confidence": 0,
                "error": "Insufficient data for features",
            }

        # Take the latest row (no label needed at inference)
        latest = features.iloc[-1:].copy()

        try:
            is_crisis = float(latest.get("regime_crisis", 0).iloc[0]) >= 0.5
        except Exception:
            is_crisis = False

        # Align columns with training feature set
        for col in set(feature_columns) - set(latest.columns):
            latest[col] = 0.0
        extra = set(latest.columns) - set(feature_columns) - {"label"}
        latest = latest.drop(columns=list(extra) + ["label"], errors="ignore")
        latest = latest[feature_columns]

        # ── Predict ──────────────────────────────────────────────────────────
        X = latest.values
        probabilities = model.predict_proba(X)[0]
        is_binary = metrics.get("binary", False) or len(probabilities) == 2

        if is_binary:
            # Binary model: class 0=DOWN(SELL), class 1=UP(BUY)
            prob_down = float(probabilities[0]) * 100
            prob_up = float(probabilities[1]) * 100
            prob_dict = {"SELL": round(prob_down, 1), "BUY": round(prob_up, 1)}

            if prob_up > prob_down:
                action = "BUY"
                raw_confidence = prob_up
            else:
                action = "SELL"
                raw_confidence = prob_down

        else:
            # 3-class model: 0=SELL, 1=HOLD, 2=BUY
            prob_dict = {
                LABEL_NAMES[i]: round(float(p) * 100, 1)
                for i, p in enumerate(probabilities)
            }
            predicted_class = int(np.argmax(probabilities))
            raw_confidence = float(probabilities[predicted_class]) * 100
            action = LABEL_NAMES.get(predicted_class, "HOLD")

        # Confidence threshold (regime-aware)
        thr_normal = float(metrics.get("trade_confidence_threshold_best_normal_pct", _BASE_CONFIDENCE_THRESHOLD) or _BASE_CONFIDENCE_THRESHOLD)
        thr_crisis = float(metrics.get("trade_confidence_threshold_best_crisis_pct", _HIGH_VOL_CONFIDENCE_THRESHOLD) or _HIGH_VOL_CONFIDENCE_THRESHOLD)
        min_conf = thr_crisis if is_crisis else thr_normal

        if action in ("BUY", "SELL") and raw_confidence < min_conf:
            action = "HOLD"

        result = {
            "symbol": symbol,
            "signal": action,
            "action": action,
            "confidence": round(raw_confidence, 1),
            "probabilities": prob_dict,
            "binary": is_binary,
            "regime": regime,
            "regime_indicators": regime_info.get("indicators", {}),
            "trade_hit_rate_best_overall_pct": metrics.get("trade_hit_rate_best_overall_pct"),
            "model_accuracy": model_data.get("metrics", {}).get("accuracy", 0),
            "cv_accuracy": model_data.get("metrics", {}).get("cv_accuracy_mean"),
            "trained_at": model_data.get("trained_at"),
            "forward_days": forward_days,
            "threshold_pct": threshold,
        }

        logger.info(
            "Prediction made",
            symbol=symbol,
            action=action,
            confidence=round(raw_confidence, 1),
            regime=regime,
        )
        return result

    except Exception as e:
        logger.error("Prediction failed", symbol=symbol, error=str(e))
        return {
            "symbol": symbol,
            "signal": "HOLD",
            "action": "HOLD",
            "confidence": 0,
            "error": str(e),
        }


def invalidate_model_cache() -> None:
    """Invalidate cached model (called automatically after retraining)."""
    global _model_cache
    _model_cache = None
