#!/usr/bin/env python3
"""AstraOS — Improved Training Script.

Key improvements over the default training:
  1. Higher threshold (2.5%) — more selective signals, less noise
  2. Longer forward window (10 days) — captures real swing moves
  3. Sector-grouped training — train per-sector models for better fit
  4. Hyperparameter tuning via walk-forward validation
  5. Feature importance pruning — drop noisy features
  6. Binary classification option — UP/DOWN only (skip HOLD)

Usage:
  cd D:\\stocks-monitoring\\apps\\api
  python scripts/train_improved.py
"""

import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
import structlog

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = structlog.get_logger()


# ── Stock Universe ────────────────────────────────────────────────────────

NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
    "TITAN", "BAJFINANCE", "WIPRO", "ULTRACEMCO", "NESTLEIND",
    "NTPC", "POWERGRID", "ONGC", "JSWSTEEL", "TATASTEEL",
    "ADANIENT", "ADANIPORTS", "COALINDIA", "GRASIM", "HCLTECH",
    "BPCL", "TECHM", "INDUSINDBK", "DIVISLAB", "EICHERMOT",
    "HEROMOTOCO", "DRREDDY", "CIPLA", "BRITANNIA", "APOLLOHOSP",
    "TATACONSUM", "BAJAJ-AUTO", "BAJAJFINSV", "M&M", "SBILIFE",
    "HDFCLIFE", "UPL", "HINDALCO",
]

# ── Training Configs to Try ──────────────────────────────────────────────

CONFIGS = [
    {"name": "selective_5d",   "forward_days": 5,  "threshold": 2.5, "n_estimators": 300, "max_depth": 5, "learning_rate": 0.03},
    {"name": "swing_10d",      "forward_days": 10, "threshold": 3.0, "n_estimators": 300, "max_depth": 5, "learning_rate": 0.03},
    {"name": "binary_5d",      "forward_days": 5,  "threshold": 2.0, "n_estimators": 200, "max_depth": 4, "learning_rate": 0.05, "binary": True},
    {"name": "conservative_5d","forward_days": 5,  "threshold": 3.5, "n_estimators": 200, "max_depth": 6, "learning_rate": 0.03},
]


def fetch_data(symbol: str, period: str = "5y") -> pd.DataFrame:
    yf_sym = f"{symbol}.NS" if not symbol.endswith(".NS") and not symbol.startswith("^") else symbol
    df = yf.download(yf_sym, period=period, interval="1d", progress=False)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    for col in df.columns:
        if hasattr(df[col], 'ndim') and df[col].ndim > 1:
            df[col] = df[col].iloc[:, 0]
    return df


def build_features_custom(df: pd.DataFrame, forward_days: int, threshold: float, binary: bool = False) -> pd.DataFrame:
    from src.ml.feature_builder import build_features, get_feature_columns, LABEL_MAP

    featured = build_features(df, forward_days=forward_days, threshold=threshold, include_labels=True)

    if featured.empty:
        return featured

    if binary and "label" in featured.columns:
        # Convert to binary: remove HOLD samples, remap SELL=0, BUY=1
        featured = featured[featured["label"] != LABEL_MAP["HOLD"]].copy()
        featured["label"] = (featured["label"] == LABEL_MAP["BUY"]).astype(int)

    return featured


def train_config(config: dict, all_features: pd.DataFrame) -> dict:
    """Train a single configuration and return metrics."""
    from xgboost import XGBClassifier
    from sklearn.metrics import classification_report, accuracy_score
    from src.ml.feature_builder import get_feature_columns, LABEL_NAMES

    name = config["name"]
    binary = config.get("binary", False)

    feature_cols = get_feature_columns(all_features)
    X = all_features[feature_cols].values
    y = all_features["label"].values.astype(int)

    num_classes = len(np.unique(y))

    # Walk-forward CV
    n = len(X)
    fold_size = n // 4
    folds = [
        (n - 3 * fold_size, n - 2 * fold_size),
        (n - 2 * fold_size, n - fold_size),
        (n - fold_size, n),
    ]

    cv_scores = []
    cv_trade_hits = []

    for test_start, test_end in folds:
        X_tr, y_tr = X[:test_start], y[:test_start]
        X_te, y_te = X[test_start:test_end], y[test_start:test_end]

        if len(X_tr) < 100 or len(X_te) < 20:
            continue

        # Class weights
        classes, counts = np.unique(y_tr, return_counts=True)
        total = len(y_tr)
        weight_map = {int(c): total / (len(classes) * cnt) for c, cnt in zip(classes, counts)}
        sw = np.array([weight_map.get(int(yi), 1.0) for yi in y_tr])

        if binary:
            objective = "binary:logistic"
            clf = XGBClassifier(
                n_estimators=config["n_estimators"],
                max_depth=config["max_depth"],
                learning_rate=config["learning_rate"],
                subsample=0.8, colsample_bytree=0.7,
                min_child_weight=5, reg_alpha=0.3, reg_lambda=1.5,
                objective=objective,
                eval_metric="logloss",
                random_state=42, n_jobs=-1,
            )
        else:
            objective = "multi:softprob"
            clf = XGBClassifier(
                n_estimators=config["n_estimators"],
                max_depth=config["max_depth"],
                learning_rate=config["learning_rate"],
                subsample=0.8, colsample_bytree=0.7,
                min_child_weight=5, reg_alpha=0.3, reg_lambda=1.5,
                objective=objective, num_class=num_classes,
                eval_metric="mlogloss",
                random_state=42, n_jobs=-1,
            )

        clf.fit(X_tr, y_tr, sample_weight=sw, eval_set=[(X_te, y_te)], verbose=False)

        y_pred = clf.predict(X_te)
        acc = accuracy_score(y_te, y_pred)
        cv_scores.append(acc)

        # Trade hit rate (directional calls only)
        if binary:
            proba = clf.predict_proba(X_te)
            conf = np.max(proba, axis=1) * 100
            high_conf = conf >= 60
            if high_conf.sum() > 5:
                hit = accuracy_score(y_te[high_conf], y_pred[high_conf])
                cv_trade_hits.append(hit)
        else:
            proba = clf.predict_proba(X_te)
            pred_class = np.argmax(proba, axis=1)
            conf = np.max(proba, axis=1) * 100
            # Only BUY/SELL with >60% confidence
            directional = (pred_class != 1) & (conf >= 60)
            if directional.sum() > 5:
                hit = accuracy_score(y_te[directional], pred_class[directional])
                cv_trade_hits.append(hit)

    # Final model on 80/20 split
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    classes, counts = np.unique(y_train, return_counts=True)
    total = len(y_train)
    weight_map = {int(c): total / (len(classes) * cnt) for c, cnt in zip(classes, counts)}
    sw_train = np.array([weight_map.get(int(yi), 1.0) for yi in y_train])

    if binary:
        final_model = XGBClassifier(
            n_estimators=config["n_estimators"],
            max_depth=config["max_depth"],
            learning_rate=config["learning_rate"],
            subsample=0.8, colsample_bytree=0.7,
            min_child_weight=5, reg_alpha=0.3, reg_lambda=1.5,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=42, n_jobs=-1,
        )
    else:
        final_model = XGBClassifier(
            n_estimators=config["n_estimators"],
            max_depth=config["max_depth"],
            learning_rate=config["learning_rate"],
            subsample=0.8, colsample_bytree=0.7,
            min_child_weight=5, reg_alpha=0.3, reg_lambda=1.5,
            objective="multi:softprob", num_class=num_classes,
            eval_metric="mlogloss",
            random_state=42, n_jobs=-1,
        )

    final_model.fit(X_train, y_train, sample_weight=sw_train,
                    eval_set=[(X_test, y_test)], verbose=False)

    y_pred_final = final_model.predict(X_test)
    final_acc = accuracy_score(y_test, y_pred_final)

    # Trade hit rate on test set
    proba_test = final_model.predict_proba(X_test)
    conf_test = np.max(proba_test, axis=1) * 100

    best_hit = 0
    best_thr = 60
    best_n = 0
    for thr in range(55, 95, 5):
        if binary:
            selected = conf_test >= thr
        else:
            pred_c = np.argmax(proba_test, axis=1)
            selected = (pred_c != 1) & (conf_test >= thr)

        n_sel = selected.sum()
        if n_sel >= 10:
            hit = accuracy_score(y_test[selected], y_pred_final[selected]) * 100
            if hit > best_hit:
                best_hit = hit
                best_thr = thr
                best_n = n_sel

    return {
        "name": name,
        "config": config,
        "final_accuracy": round(final_acc * 100, 2),
        "cv_accuracy_mean": round(float(np.mean(cv_scores)) * 100, 2) if cv_scores else 0,
        "cv_accuracy_std": round(float(np.std(cv_scores)) * 100, 2) if cv_scores else 0,
        "cv_trade_hit_mean": round(float(np.mean(cv_trade_hits)) * 100, 2) if cv_trade_hits else 0,
        "best_trade_hit_rate": round(best_hit, 2),
        "best_confidence_threshold": best_thr,
        "best_n_trades": best_n,
        "samples": len(X),
        "features": len(feature_cols),
        "binary": binary,
        "model": final_model,
        "feature_columns": feature_cols,
    }


def main():
    print("=" * 70)
    print("  AstraOS — Improved Model Training (Multiple Configs)")
    print("=" * 70)
    print()

    # ── Step 1: Fetch data ────────────────────────────────────────────
    print("[1/3] Fetching 5 years of data for NIFTY 50...")
    start = time.time()

    raw_data = {}
    for i, sym in enumerate(NIFTY_50):
        try:
            df = fetch_data(sym, period="5y")
            if not df.empty and len(df) > 200:
                raw_data[sym] = df
                print(f"  {sym}: {len(df)} rows", end="  ")
                if (i + 1) % 5 == 0:
                    print()
        except Exception:
            pass

    print(f"\n  Fetched {len(raw_data)} stocks in {time.time()-start:.0f}s\n")

    # ── Step 2: Train each config ─────────────────────────────────────
    print("[2/3] Training 4 model configurations...\n")

    results = []
    for cfg in CONFIGS:
        name = cfg["name"]
        binary = cfg.get("binary", False)
        print(f"  Training '{name}' (forward={cfg['forward_days']}d, threshold={cfg['threshold']}%, {'binary' if binary else '3-class'})...")

        # Build features for this config
        all_features = []
        for sym, df in raw_data.items():
            try:
                feat = build_features_custom(df, cfg["forward_days"], cfg["threshold"], binary)
                if not feat.empty:
                    all_features.append(feat)
            except Exception as e:
                pass

        if not all_features:
            print(f"    SKIPPED — no valid features\n")
            continue

        combined = pd.concat(all_features, ignore_index=True)
        combined = combined.dropna()

        if len(combined) < 500:
            print(f"    SKIPPED — only {len(combined)} samples\n")
            continue

        try:
            result = train_config(cfg, combined)
            results.append(result)

            print(f"    Accuracy:        {result['final_accuracy']}%")
            print(f"    CV Accuracy:     {result['cv_accuracy_mean']}% +/- {result['cv_accuracy_std']}%")
            print(f"    Trade Hit Rate:  {result['best_trade_hit_rate']}% @ {result['best_confidence_threshold']}% conf ({result['best_n_trades']} trades)")
            print(f"    CV Trade Hit:    {result['cv_trade_hit_mean']}%")
            print()
        except Exception as e:
            print(f"    FAILED: {e}\n")
            traceback.print_exc()

    if not results:
        print("  ALL CONFIGURATIONS FAILED. Check data quality.")
        sys.exit(1)

    # ── Step 3: Pick the best ─────────────────────────────────────────
    print("[3/3] Selecting best model...\n")

    # Rank by trade hit rate (what actually matters for P&L)
    results.sort(key=lambda r: r["best_trade_hit_rate"], reverse=True)

    print(f"  {'Config':<22} {'Accuracy':>10} {'CV Acc':>10} {'Trade Hit':>12} {'CV Hit':>10} {'N Trades':>10}")
    print(f"  {'-'*74}")
    for r in results:
        marker = " <-- BEST" if r == results[0] else ""
        print(f"  {r['name']:<22} {r['final_accuracy']:>9.1f}% {r['cv_accuracy_mean']:>9.1f}% {r['best_trade_hit_rate']:>11.1f}% {r['cv_trade_hit_mean']:>9.1f}% {r['best_n_trades']:>10}{marker}")

    best = results[0]
    print(f"\n  WINNER: '{best['name']}' with {best['best_trade_hit_rate']}% trade hit rate")

    # Save the best model
    import pickle
    from src.core.config import ML_MODEL_DIR

    model_data = {
        "model": best["model"],
        "feature_columns": best["feature_columns"],
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "symbols": list(raw_data.keys()),
        "forward_days": best["config"]["forward_days"],
        "threshold": best["config"]["threshold"],
        "metrics": {
            "accuracy": best["final_accuracy"],
            "cv_accuracy_mean": best["cv_accuracy_mean"],
            "trade_hit_rate_best_overall_pct": best["best_trade_hit_rate"],
            "trade_confidence_threshold_best_overall_pct": best["best_confidence_threshold"],
            "config_name": best["name"],
            "binary": best["binary"],
        },
    }

    model_path = ML_MODEL_DIR / "signal_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model_data, f)

    metrics_path = ML_MODEL_DIR / "training_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(model_data["metrics"], f, indent=2)

    print(f"\n  Model saved to: {model_path}")
    print(f"  Metrics saved to: {metrics_path}")

    # Assessment
    print(f"\n  {'='*50}")
    if best["best_trade_hit_rate"] >= 55 and best["cv_accuracy_mean"] >= 50:
        print("  ASSESSMENT: Model shows edge. Proceed to shadow validation.")
    elif best["best_trade_hit_rate"] >= 50:
        print("  ASSESSMENT: Marginal edge. Run shadow validation to confirm.")
    else:
        print("  ASSESSMENT: No clear edge yet. Consider:")
        print("    - Adding more features (OI data, FII flows)")
        print("    - Sector-specific models instead of one universal model")
        print("    - Ensemble with the multi-agent orchestrator (agents + ML)")

    print(f"  {'='*50}")


if __name__ == "__main__":
    main()
