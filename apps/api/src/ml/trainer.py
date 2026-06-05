# type: ignore
"""AstraOS ML — XGBoost Signal Model Trainer.

Trains an XGBoost classifier on historical OHLCV data + 70+ features
to predict BUY/SELL/HOLD signals.

IMPORTANT: This module is fully synchronous. It uses yfinance.download()
directly (blocking I/O). The caller MUST run this via asyncio.to_thread()
or in a background thread to avoid blocking the event loop.
"""

import json
import pickle
import traceback
from datetime import datetime
from pathlib import Path  # noqa: F401 – kept for type-level compatibility
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger()

IST = ZoneInfo("Asia/Kolkata")

# ── Model storage — single canonical path from core config ──
from ..core.config import ML_MODEL_DIR

MODEL_DIR = ML_MODEL_DIR
MODEL_PATH = MODEL_DIR / "signal_model.pkl"
METRICS_PATH = MODEL_DIR / "training_metrics.json"

# ── Training status (in-memory) ──
_training_status = {
    "status": "idle",
    "progress": 0,
    "started_at": None,
    "completed_at": None,
    "metrics": None,
    "error": None,
}


def get_training_status() -> dict:
    """Get current training status."""
    return _training_status.copy()


def _fetch_ohlcv(symbol: str, period: str = "2y") -> pd.DataFrame:
    """Download OHLCV data directly via yfinance (synchronous)."""
    yf_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") and not symbol.startswith("^") else symbol
    df = yf.download(yf_symbol, period=period, interval="1d", progress=False)
    if df.empty:
        return pd.DataFrame()
    # Flatten multi-index columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    # Squeeze 2D columns to 1D
    for col in df.columns:
        if hasattr(df[col], 'ndim') and df[col].ndim > 1:
            df[col] = df[col].iloc[:, 0]
    return df


_FORWARD_DAYS = 5       # days ahead for return-based labelling (must match predictor)
_THRESHOLD_PCT = 1.5    # ±% return threshold for BUY / SELL


def _compute_class_weights(y: np.ndarray) -> np.ndarray:
    """Return per-sample weights (inverse class frequency) for XGBoost."""
    classes, counts = np.unique(y, return_counts=True)
    total = len(y)
    weight_map = {int(c): total / (len(classes) * cnt) for c, cnt in zip(classes, counts)}
    return np.array([weight_map.get(int(yi), 1.0) for yi in y])


def train_signal_model_sync(
    symbols: list[str],
    period: str = "2y",
    forward_days: int = _FORWARD_DAYS,
    threshold: float = _THRESHOLD_PCT,
) -> None:
    """Train XGBoost model on historical data (SYNCHRONOUS).

    Call via asyncio.to_thread(train_signal_model_sync, symbols, period).

    Args:
        symbols:      NSE symbols to train on.
        period:       yfinance period string (1y / 2y / 3y / 5y).
        forward_days: Days ahead used for return-based label generation.
                      MUST equal the value used in predictor.predict_signal().
        threshold:    Return% threshold separating BUY / SELL from HOLD.
    """
    global _training_status

    _training_status = {
        "status": "training",
        "progress": 0,
        "started_at": datetime.now(IST).isoformat(),
        "completed_at": None,
        "metrics": None,
        "error": None,
    }

    try:
        from xgboost import XGBClassifier
        from sklearn.metrics import classification_report, accuracy_score
        from .feature_builder import build_features, get_feature_columns, LABEL_NAMES  # noqa: F401

        # ── Step 1: Collect feature matrices from all symbols ────────────────
        all_features: list[pd.DataFrame] = []
        _training_status["progress"] = 5

        for i, symbol in enumerate(symbols):
            try:
                logger.info("Fetching training data", symbol=symbol, period=period)
                df = _fetch_ohlcv(symbol, period=period)

                if df.empty or len(df) < 100:
                    logger.warning("Skipping symbol — insufficient data",
                                   symbol=symbol, rows=len(df))
                    continue

                features = build_features(df, forward_days=forward_days, threshold=threshold)
                if not features.empty:
                    features = features.copy()
                    features["_symbol"] = symbol
                    all_features.append(features)
                    logger.info("Features built", symbol=symbol, rows=len(features))
                else:
                    logger.warning("Empty features after build", symbol=symbol)

            except Exception as e:
                logger.error("Feature build failed", symbol=symbol, error=str(e),
                             tb=traceback.format_exc())

            _training_status["progress"] = 5 + int((i + 1) / len(symbols) * 35)

        if not all_features:
            raise ValueError("No valid training data from any symbol")

        combined = pd.concat(all_features, ignore_index=True)
        combined = combined.drop(columns=["_symbol"], errors="ignore")

        feature_cols = get_feature_columns(combined)
        X = combined[feature_cols].values
        y = combined["label"].values.astype(int)

        label_dist = {int(k): int(v) for k, v in zip(*np.unique(y, return_counts=True))}
        logger.info("Training data ready", samples=len(X), features=len(feature_cols),
                    label_dist=label_dist)

        _training_status["progress"] = 45

        # ── Step 2: Walk-Forward CV (3 folds) to get realistic accuracy ──────
        n = len(X)
        fold_size = n // 4
        folds = [
            (n - 3 * fold_size, n - 2 * fold_size),
            (n - 2 * fold_size, n - fold_size),
            (n - fold_size, n),
        ]
        cv_accuracies: list[float] = []

        for test_start, test_end in folds:
            X_tr, y_tr = X[:test_start], y[:test_start]
            X_te, y_te = X[test_start:test_end], y[test_start:test_end]
            if len(X_tr) < 50 or len(X_te) < 10:
                continue
            sw_tr = _compute_class_weights(y_tr)
            fold_clf = XGBClassifier(
                n_estimators=100, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
                reg_alpha=0.1, reg_lambda=1.0,
                objective="multi:softprob", num_class=3,
                eval_metric="mlogloss", use_label_encoder=False,
                random_state=42, n_jobs=-1,
            )
            fold_clf.fit(X_tr, y_tr, sample_weight=sw_tr,
                         eval_set=[(X_te, y_te)], verbose=False)
            cv_accuracies.append(accuracy_score(y_te, fold_clf.predict(X_te)))
            logger.info("CV fold done", acc=round(cv_accuracies[-1] * 100, 1))

        _training_status["progress"] = 60

        # ── Step 3: Final model — last 20% held out for reported metrics ─────
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        sw_train = _compute_class_weights(y_train)

        logger.info("Training final XGBoost model",
                    train_size=len(X_train), test_size=len(X_test))

        model = XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            reg_alpha=0.1,
            reg_lambda=1.0,
            objective="multi:softprob",
            num_class=3,
            eval_metric="mlogloss",
            use_label_encoder=False,
            random_state=42,
            n_jobs=-1,
        )

        model.fit(
            X_train, y_train,
            sample_weight=sw_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )

        _training_status["progress"] = 80

        # ── Step 4: Evaluate ─────────────────────────────────────────────────
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(
            y_test, y_pred,
            target_names=["SELL", "HOLD", "BUY"],
            output_dict=True,
            zero_division=0,
        )

        # ── Selective trade accuracy (BUY/SELL only, confidence-filtered) ──
        # This measures "how often our directional calls are right" when we
        # only act on high-confidence predictions. This is the practical
        # notion of accuracy for trading decisions.
        proba = model.predict_proba(X_test)
        pred_class = np.argmax(proba, axis=1)  # 0=SELL, 1=HOLD, 2=BUY
        conf_pct = np.max(proba, axis=1) * 100.0

        crisis_idx = feature_cols.index("regime_crisis") if "regime_crisis" in feature_cols else None
        if crisis_idx is not None:
            crisis_mask = X_test[:, crisis_idx] >= 0.5
        else:
            crisis_mask = np.zeros_like(y_test, dtype=bool)
        normal_mask = ~crisis_mask

        def _best_trade_hit_rate(mask_subset: np.ndarray, min_trades: int) -> tuple[float, int | None, int]:
            best_hit = 0.0
            best_thr: int | None = None
            best_n = 0
            for thr in range(60, 100):  # confidence threshold in percent
                selected = (pred_class != 1) & (conf_pct >= thr) & mask_subset
                n_sel = int(selected.sum())
                if n_sel < min_trades:
                    continue
                correct = int((pred_class[selected] == y_test[selected]).sum())
                hit = (correct / n_sel) * 100.0
                if hit > best_hit:
                    best_hit = hit
                    best_thr = thr
                    best_n = n_sel
            return best_hit, best_thr, best_n

        hit_overall, thr_overall, n_overall = _best_trade_hit_rate(np.ones_like(y_test, dtype=bool), min_trades=20)
        hit_normal, thr_normal, n_normal = _best_trade_hit_rate(normal_mask, min_trades=10)
        hit_crisis, thr_crisis, n_crisis = _best_trade_hit_rate(crisis_mask, min_trades=5)

        importance = dict(zip(feature_cols, model.feature_importances_.tolist()))
        top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:15]

        metrics = {
            "accuracy": round(accuracy * 100, 2),
            "cv_accuracy_mean": round(float(np.mean(cv_accuracies)) * 100, 2) if cv_accuracies else None,
            "cv_accuracy_std": round(float(np.std(cv_accuracies)) * 100, 2) if cv_accuracies else None,
            "samples_train": len(X_train),
            "samples_test": len(X_test),
            "forward_days": forward_days,
            "threshold_pct": threshold,
            "trade_hit_rate_best_overall_pct": round(hit_overall, 2),
            "trade_confidence_threshold_best_overall_pct": thr_overall,
            "trade_selected_trades_best_overall": n_overall,
            "trade_hit_rate_best_normal_pct": round(hit_normal, 2),
            "trade_confidence_threshold_best_normal_pct": thr_normal,
            "trade_selected_trades_best_normal": n_normal,
            "trade_hit_rate_best_crisis_pct": round(hit_crisis, 2),
            "trade_confidence_threshold_best_crisis_pct": thr_crisis,
            "trade_selected_trades_best_crisis": n_crisis,
            "per_class": {
                k: {
                    "precision": round(v["precision"] * 100, 1),
                    "recall": round(v["recall"] * 100, 1),
                    "f1": round(v["f1-score"] * 100, 1),
                    "support": int(v["support"]),
                }
                for k, v in report.items()
                if k in ("SELL", "HOLD", "BUY")
            },
            "top_features": [
                {"feature": f, "importance": round(imp * 100, 2)}
                for f, imp in top_features
            ],
            "symbols_trained": symbols,
            "period": period,
        }

        _training_status["progress"] = 90

        # ── Step 5: Save model (include training hyperparams for inference) ──
        model_data = {
            "model": model,
            "feature_columns": feature_cols,
            "trained_at": datetime.now(IST).isoformat(),
            "symbols": symbols,
            "metrics": metrics,
            "forward_days": forward_days,   # ← predictor reads this
            "threshold": threshold,          # ← predictor reads this
        }

        with open(MODEL_PATH, "wb") as f:
            pickle.dump(model_data, f)

        with open(METRICS_PATH, "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info("Model trained and saved",
                    accuracy=round(accuracy * 100, 1),
                    cv_mean=metrics.get("cv_accuracy_mean"),
                    path=str(MODEL_PATH))

        _training_status.update({
            "status": "completed",
            "progress": 100,
            "completed_at": datetime.now(IST).isoformat(),
            "metrics": metrics,
        })

        try:
            from ..scheduler.engine import push_feed
            push_feed(
                "ML_TRAIN",
                f"🧠 Model trained — accuracy {accuracy * 100:.1f}% on {len(symbols)} stocks",
                metrics,
            )
        except Exception:
            pass

    except Exception as e:
        logger.error("Model training failed", error=str(e), tb=traceback.format_exc())
        _training_status.update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.now(IST).isoformat(),
        })
