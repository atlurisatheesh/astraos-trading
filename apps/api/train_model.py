"""Standalone NIFTY Training Script — delegates to the API ML stack.

Run from apps/api/:
    python train_model.py
    python train_model.py --symbols RELIANCE,TCS,INFY --period 3y
"""
import sys
import os
import json
import time
import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# ── Make sure the src package is importable ──────────────────────────────────
# train_model.py lives at  apps/api/train_model.py
# src package lives at     apps/api/src/
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger()
IST = ZoneInfo("Asia/Kolkata")

# ── Import the canonical ML stack (same code used by the API) ────────────────
from src.ml.feature_builder import build_features, get_feature_columns, LABEL_NAMES
from src.core.config import ML_MODEL_DIR

MODEL_DIR = ML_MODEL_DIR
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "signal_model.pkl"
METRICS_PATH = MODEL_DIR / "training_metrics.json"

# ── Default training universe: full NIFTY 50 ────────────────────────────────
from src.ml.training_scheduler import NIFTY_50

DEFAULT_SYMBOLS = NIFTY_50
DEFAULT_PERIOD = "3y"


def fetch_ohlcv(symbol: str, period: str) -> pd.DataFrame:
    """Download OHLCV from yfinance and clean column names."""
    yf_sym = f"{symbol}.NS" if not symbol.endswith(".NS") and not symbol.startswith("^") else symbol
    df = yf.download(yf_sym, period=period, interval="1d", progress=False)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    for col in df.columns:
        if hasattr(df[col], "ndim") and df[col].ndim > 1:
            df[col] = df[col].iloc[:, 0]
    return df


def compute_class_weights(y: np.ndarray) -> dict:
    """Compute inverse-frequency class weights for XGBoost sample_weight."""
    classes, counts = np.unique(y, return_counts=True)
    total = len(y)
    weights = {int(c): total / (len(classes) * cnt) for c, cnt in zip(classes, counts)}
    # Always ensure all 3 classes are present
    for c in (0, 1, 2):
        weights.setdefault(c, 1.0)
    return weights


def main():
    parser = argparse.ArgumentParser(description="Train AstraOS XGBoost signal model")
    parser.add_argument(
        "--symbols", default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated NSE symbols (default: 25-stock NIFTY universe)"
    )
    parser.add_argument("--period", default=DEFAULT_PERIOD, help="yfinance period: 1y, 2y, 3y, 5y")
    parser.add_argument("--forward-days", type=int, default=5,
                        help="Forward days for labelling (default: 5)")
    parser.add_argument("--threshold", type=float, default=1.5,
                        help="Percentage threshold for BUY/SELL (default: 1.5)")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    period = args.period
    forward_days = args.forward_days
    threshold = args.threshold

    start = time.time()
    # Windows consoles can still run with cp1252; avoid emojis to prevent UnicodeEncodeError.
    print("\nAstraOS — Training XGBoost signal model")
    print(f"   Symbols   : {len(symbols)}")
    print(f"   Period    : {period}")
    print(f"   Forward   : {forward_days} days  |  Threshold: +/-{threshold}%")
    print("=" * 60)

    # ── Step 1: Build feature matrix from each symbol ────────────────────────
    all_features: list[pd.DataFrame] = []
    for i, symbol in enumerate(symbols):
        try:
            df = fetch_ohlcv(symbol, period)
            if df.empty or len(df) < 100:
                print(f"  [SKIP] {symbol}: only {len(df)} rows")
                continue
            feats = build_features(df, forward_days=forward_days, threshold=threshold)
            if not feats.empty:
                all_features.append(feats)
                print(f"  [OK]  {symbol}: {len(feats)} samples, {len(feats.columns) - 1} features")
            else:
                print(f"  [SKIP] {symbol}: empty feature set after NaN handling")
        except Exception as e:
            print(f"  [ERR] {symbol}: {e}")

    if not all_features:
        print("\n[ERR] No valid training data. Aborting.")
        sys.exit(1)

    combined = pd.concat(all_features, ignore_index=True)
    feature_cols = get_feature_columns(combined)
    X = combined[feature_cols].values
    y = combined["label"].values.astype(int)

    label_dist = {0: int((y == 0).sum()), 1: int((y == 1).sum()), 2: int((y == 2).sum())}
    print(f"\nDataset   : {len(X)} samples | {len(feature_cols)} features")
    print(f"Labels    : SELL={label_dist[0]}  HOLD={label_dist[1]}  BUY={label_dist[2]}")

    # ── Step 2: Walk-Forward Time-Series Split (3 folds) ─────────────────────
    n = len(X)
    fold_size = n // 4          # test each last quarter after 3 training windows
    folds = [
        (n - 3 * fold_size, n - 2 * fold_size),
        (n - 2 * fold_size, n - fold_size),
        (n - fold_size,      n),
    ]

    print(f"\nWalk-Forward CV ({len(folds)} folds):")
    cv_accuracies: list[float] = []

    from xgboost import XGBClassifier
    from sklearn.metrics import accuracy_score, classification_report

    for fold_idx, (test_start, test_end) in enumerate(folds):
        X_tr, y_tr = X[:test_start], y[:test_start]
        X_te, y_te = X[test_start:test_end], y[test_start:test_end]
        if len(X_tr) < 50 or len(X_te) < 10:
            continue

        cw = compute_class_weights(y_tr)
        sample_weights = np.array([cw[int(yi)] for yi in y_tr])

        fold_model = XGBClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
            reg_alpha=0.1, reg_lambda=1.0,
            objective="multi:softprob", num_class=3,
            eval_metric="mlogloss", use_label_encoder=False,
            random_state=42, n_jobs=-1,
        )
        fold_model.fit(X_tr, y_tr, sample_weight=sample_weights,
                       eval_set=[(X_te, y_te)], verbose=False)
        fold_acc = accuracy_score(y_te, fold_model.predict(X_te))
        cv_accuracies.append(fold_acc)
        print(f"   Fold {fold_idx + 1}: train={len(X_tr)}  test={len(X_te)}  acc={fold_acc * 100:.1f}%")

    if cv_accuracies:
        print(f"   CV Mean: {np.mean(cv_accuracies) * 100:.1f}%  ±{np.std(cv_accuracies) * 100:.1f}%")

    # ── Step 3: Final model — train on full data (last 20% held out for metrics)
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    cw_final = compute_class_weights(y_train)
    sw_final = np.array([cw_final[int(yi)] for yi in y_train])

    print(f"\nFinal model: train={len(X_train)}  test={len(X_test)}")

    model = XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
        reg_alpha=0.1, reg_lambda=1.0,
        objective="multi:softprob", num_class=3,
        eval_metric="mlogloss", use_label_encoder=False,
        random_state=42, n_jobs=-1,
    )
    model.fit(X_train, y_train, sample_weight=sw_final,
              eval_set=[(X_test, y_test)], verbose=False)

    # ── Step 4: Evaluate ─────────────────────────────────────────────────────
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(
        y_test, y_pred,
        target_names=["SELL", "HOLD", "BUY"],
        output_dict=True, zero_division=0,
    )

    # ── Selective trade accuracy (BUY/SELL only, confidence-filtered) ──
    # This measures "how often our directional calls are right" when we
    # only act on high-confidence predictions.
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
        for thr in range(60, 100):
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

    importance = sorted(
        zip(feature_cols, model.feature_importances_.tolist()),
        key=lambda x: -x[1],
    )[:15]

    metrics = {
        "accuracy": round(accuracy * 100, 2),
        "trade_hit_rate_best_overall_pct": round(hit_overall, 2),
        "trade_confidence_threshold_best_overall_pct": thr_overall,
        "trade_selected_trades_best_overall": n_overall,
        "trade_hit_rate_best_normal_pct": round(hit_normal, 2),
        "trade_confidence_threshold_best_normal_pct": thr_normal,
        "trade_selected_trades_best_normal": n_normal,
        "trade_hit_rate_best_crisis_pct": round(hit_crisis, 2),
        "trade_confidence_threshold_best_crisis_pct": thr_crisis,
        "trade_selected_trades_best_crisis": n_crisis,
        "cv_accuracy_mean": round(float(np.mean(cv_accuracies)) * 100, 2) if cv_accuracies else None,
        "cv_accuracy_std": round(float(np.std(cv_accuracies)) * 100, 2) if cv_accuracies else None,
        "samples_train": len(X_train),
        "samples_test": len(X_test),
        "forward_days": forward_days,
        "threshold_pct": threshold,
        "per_class": {
            k: {
                "precision": round(v["precision"] * 100, 1),
                "recall": round(v["recall"] * 100, 1),
                "f1": round(v["f1-score"] * 100, 1),
                "support": int(v["support"]),
            }
            for k, v in report.items() if k in ("SELL", "HOLD", "BUY")
        },
        "top_features": [
            {"feature": f, "importance": round(imp * 100, 2)} for f, imp in importance
        ],
        "symbols_trained": symbols,
        "period": period,
    }

    # ── Step 5: Save ─────────────────────────────────────────────────────────
    import pickle
    model_data = {
        "model": model,
        "feature_columns": feature_cols,
        "trained_at": datetime.now(IST).isoformat(),
        "symbols": symbols,
        "metrics": metrics,
        "forward_days": forward_days,
        "threshold": threshold,
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model_data, f)
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"MODEL SAVED : {MODEL_PATH}")
    print(f"Accuracy   : {metrics['accuracy']}%")
    if cv_accuracies:
        print(f"CV Mean    : {metrics['cv_accuracy_mean']}% +/- {metrics['cv_accuracy_std']}%")
    print(f"Time       : {elapsed:.1f}s")
    print(f"\nPer-class:")
    for cls in ["SELL", "HOLD", "BUY"]:
        m = metrics["per_class"][cls]
        print(f"   {cls}: P={m['precision']}%  R={m['recall']}%  F1={m['f1']}%  (n={m['support']})")
    print(f"\nTop 10 Features:")
    for feat in metrics["top_features"][:10]:
        print(f"   {feat['feature']}: {feat['importance']}%")

    # ── Step 6: Register in model registry ───────────────────────────────────
    try:
        from src.ml.model_registry import register_model
        reg = register_model(MODEL_PATH, metrics)
        print(f"\nRegistry   : v{reg['version']}  promoted={reg['promoted']}")
        print(f"Reason     : {reg['promotion_reason']}")
    except Exception as e:
        print(f"\nModel registry skipped: {e}")


if __name__ == "__main__":
    main()
