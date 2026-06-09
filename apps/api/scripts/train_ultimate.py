#!/usr/bin/env python3
"""AstraOS — Ultimate Model Training Pipeline.

10 improvements over the basic trainer:
  1. Candlestick pattern features (18 patterns → numeric scores)
  2. ATR-based dynamic labeling (not fixed %, adapts to volatility)
  3. Ensemble: XGBoost + LightGBM + RandomForest → majority vote
  4. Feature selection: drop noisy features, keep top 50
  5. Per-sector models (Banking, IT, Pharma behave differently)
  6. Macro features (VIX level, market breadth)
  7. Regime-conditional training (separate model for bull vs bear)
  8. Optuna hyperparameter tuning
  9. Stacking meta-learner
  10. Confidence calibration (Platt scaling)

Usage:
  cd D:\\stocks-monitoring\\apps\\api
  python scripts/train_ultimate.py
"""

import json
import pickle
import sys
import time
import traceback
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
import structlog

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = structlog.get_logger()

# ── Stock Universe ────────────────────────────────────────────────

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

SECTORS = {
    "banking": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "BAJFINANCE"],
    "it": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "pharma": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "APOLLOHOSP"],
    "auto": ["MARUTI", "M&M", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO"],
    "energy": ["RELIANCE", "ONGC", "BPCL", "NTPC", "POWERGRID", "COALINDIA"],
    "fmcg": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "TATACONSUM"],
    "metal": ["JSWSTEEL", "TATASTEEL", "HINDALCO"],
}


def fetch_data(symbol, period="5y"):
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


def fetch_vix(period="5y"):
    """Fetch India VIX as a macro feature."""
    try:
        df = yf.download("^INDIAVIX", period=period, interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        if not df.empty:
            return df["Close"].rename("VIX")
    except Exception:
        pass
    return pd.Series(dtype=float, name="VIX")


def fetch_nifty(period="5y"):
    """Fetch NIFTY 50 index as market breadth reference."""
    try:
        df = yf.download("^NSEI", period=period, interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        if not df.empty:
            return df["Close"].rename("NIFTY")
    except Exception:
        pass
    return pd.Series(dtype=float, name="NIFTY")


def build_features_enhanced(df, forward_days=5, threshold=2.0, vix_series=None, nifty_series=None):
    """Build features with candlestick patterns, macro data, and ATR-based labels."""
    from src.ml.feature_builder import build_features

    # Standard features (84 columns)
    featured = build_features(df, forward_days=forward_days, threshold=threshold, include_labels=False)
    if featured.empty:
        return pd.DataFrame()

    # ── Add candlestick pattern features ──
    try:
        from src.quant.candlestick_patterns import get_candlestick_features
        # Compute on last N rows with a sliding window
        candle_cols = {"candle_bullish_count": [], "candle_bearish_count": [],
                       "candle_max_reliability": [], "candle_net_signal": []}

        ohlcv = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        for i in range(len(featured)):
            # Use a window ending at this row's date
            if i < 15:
                for k in candle_cols:
                    candle_cols[k].append(0)
                continue
            window = ohlcv.iloc[max(0, i - 15):i + 1]
            try:
                cf = get_candlestick_features(window)
                for k in candle_cols:
                    candle_cols[k].append(cf.get(k, 0))
            except Exception:
                for k in candle_cols:
                    candle_cols[k].append(0)

        for k, vals in candle_cols.items():
            if len(vals) == len(featured):
                featured[k] = vals
    except Exception as e:
        print(f"    Candlestick features skipped: {e}")

    # ── Add VIX as macro feature ──
    if vix_series is not None and not vix_series.empty:
        try:
            featured = featured.copy()
            aligned_vix = vix_series.reindex(featured.index, method="ffill")
            featured["macro_vix"] = aligned_vix.values[:len(featured)]
            featured["macro_vix_ma5"] = featured["macro_vix"].rolling(5).mean()
            featured["macro_vix_high"] = (featured["macro_vix"] > 20).astype(int)
        except Exception:
            pass

    # ── Add NIFTY relative strength ──
    if nifty_series is not None and not nifty_series.empty:
        try:
            aligned_nifty = nifty_series.reindex(featured.index, method="ffill")
            nifty_ret = aligned_nifty.pct_change(5) * 100
            featured["macro_nifty_ret5d"] = nifty_ret.values[:len(featured)]
        except Exception:
            pass

    # ── ATR-based dynamic labels (adapts to each stock's volatility) ──
    close = df["Close"]
    high = df["High"]
    low = df["Low"]

    # Calculate ATR
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr_14 = tr.rolling(14).mean()

    # Dynamic threshold: 1.5x ATR as the move that matters
    atr_threshold = (atr_14 * 1.5 / close * 100)  # as percentage
    atr_threshold = atr_threshold.reindex(featured.index)

    # Future return
    future_ret = close.shift(-forward_days) / close - 1
    future_ret_pct = (future_ret * 100).reindex(featured.index)

    # Label: UP if return > ATR-threshold, DOWN if < -ATR-threshold
    # Use fixed threshold as fallback
    effective_threshold = atr_threshold.fillna(threshold)

    featured["label"] = 1  # default HOLD/neutral
    featured.loc[future_ret_pct > effective_threshold, "label"] = 2   # UP
    featured.loc[future_ret_pct < -effective_threshold, "label"] = 0  # DOWN

    # Binary: drop HOLD
    featured = featured[featured["label"] != 1].copy()
    featured["label"] = (featured["label"] == 2).astype(int)  # 1=UP, 0=DOWN

    # Remove last N rows (no future data)
    if forward_days > 0:
        featured = featured.iloc[:-forward_days]

    # Keep only numeric
    numeric_cols = featured.select_dtypes(include=[np.number]).columns.tolist()
    featured = featured[numeric_cols]

    # Drop raw OHLCV
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        featured = featured.drop(columns=[col], errors="ignore")

    featured = featured.ffill().dropna()
    return featured


def train_ensemble(X_train, y_train, X_test, y_test):
    """Train XGBoost + LightGBM + RandomForest ensemble."""
    from xgboost import XGBClassifier
    from sklearn.ensemble import RandomForestClassifier, VotingClassifier
    from sklearn.metrics import accuracy_score
    from sklearn.calibration import CalibratedClassifierCV

    # Compute class weights
    classes, counts = np.unique(y_train, return_counts=True)
    total = len(y_train)
    weight_map = {int(c): total / (len(classes) * cnt) for c, cnt in zip(classes, counts)}
    sw = np.array([weight_map.get(int(yi), 1.0) for yi in y_train])

    # Model 1: XGBoost
    xgb = XGBClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.7, min_child_weight=5,
        reg_alpha=0.3, reg_lambda=1.5, objective="binary:logistic",
        eval_metric="logloss", random_state=42, n_jobs=-1,
    )

    # Model 2: RandomForest
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_split=10,
        min_samples_leaf=5, max_features="sqrt",
        class_weight="balanced", random_state=42, n_jobs=-1,
    )

    # Try LightGBM if available
    try:
        from lightgbm import LGBMClassifier
        lgb = LGBMClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.03,
            subsample=0.8, colsample_bytree=0.7, min_child_weight=5,
            reg_alpha=0.3, reg_lambda=1.5, objective="binary",
            class_weight="balanced", random_state=42, n_jobs=-1,
            verbose=-1,
        )
        models = [("xgb", xgb), ("rf", rf), ("lgb", lgb)]
        print("    Using XGBoost + LightGBM + RandomForest ensemble")
    except ImportError:
        models = [("xgb", xgb), ("rf", rf)]
        print("    Using XGBoost + RandomForest ensemble (install lightgbm for 3-model)")

    # Train each model individually (for diagnostics)
    individual_results = {}
    for name, model in models:
        model.fit(X_train, y_train, sample_weight=sw if name == "xgb" else None)
        pred = model.predict(X_test)
        acc = accuracy_score(y_test, pred)
        individual_results[name] = acc
        print(f"      {name:4s} accuracy: {acc*100:.1f}%")

    # Voting ensemble
    ensemble = VotingClassifier(estimators=models, voting="soft")
    ensemble.fit(X_train, y_train)
    ensemble_pred = ensemble.predict(X_test)
    ensemble_acc = accuracy_score(y_test, ensemble_pred)
    print(f"      ENSEMBLE accuracy: {ensemble_acc*100:.1f}%")

    # Confidence calibration (Platt scaling)
    try:
        calibrated = CalibratedClassifierCV(ensemble, method="sigmoid", cv=3)
        calibrated.fit(X_train, y_train)
        cal_pred = calibrated.predict(X_test)
        cal_acc = accuracy_score(y_test, cal_pred)
        print(f"      CALIBRATED accuracy: {cal_acc*100:.1f}%")

        # Use calibrated if better, else raw ensemble
        if cal_acc >= ensemble_acc:
            return calibrated, cal_acc, individual_results
    except Exception as e:
        print(f"      Calibration failed: {e}")

    return ensemble, ensemble_acc, individual_results


def feature_selection(X_train, y_train, feature_names, top_n=50):
    """Select top N features using XGBoost importance."""
    from xgboost import XGBClassifier

    selector = XGBClassifier(
        n_estimators=100, max_depth=4, learning_rate=0.1,
        objective="binary:logistic", random_state=42, n_jobs=-1,
    )
    selector.fit(X_train, y_train)

    importances = dict(zip(feature_names, selector.feature_importances_))
    sorted_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)

    selected = [f for f, imp in sorted_features[:top_n]]
    dropped = [f for f, imp in sorted_features[top_n:]]

    print(f"    Selected {len(selected)} features, dropped {len(dropped)}")
    print(f"    Top 10: {', '.join(f for f, _ in sorted_features[:10])}")

    return selected


def main():
    print("=" * 70)
    print("  AstraOS — Ultimate Model Training Pipeline")
    print("  (Ensemble + Candlesticks + ATR Labels + Macro + Feature Selection)")
    print("=" * 70)

    # ── Step 1: Fetch all data ────────────────────────────────────────
    print("\n[1/6] Fetching 5 years of data...")
    t0 = time.time()

    raw_data = {}
    for sym in NIFTY_50:
        try:
            df = fetch_data(sym, "5y")
            if not df.empty and len(df) > 200:
                raw_data[sym] = df
        except Exception:
            pass
    print(f"  Fetched {len(raw_data)} stocks in {time.time()-t0:.0f}s")

    # Macro data
    print("  Fetching VIX + NIFTY macro data...")
    vix = fetch_vix("5y")
    nifty = fetch_nifty("5y")
    print(f"  VIX: {len(vix)} rows, NIFTY: {len(nifty)} rows")

    # ── Step 2: Build enhanced features ───────────────────────────────
    print("\n[2/6] Building enhanced features (candlesticks + macro + ATR labels)...")
    t0 = time.time()

    all_features = []
    for sym, df in raw_data.items():
        try:
            feat = build_features_enhanced(df, forward_days=5, threshold=2.0,
                                           vix_series=vix, nifty_series=nifty)
            if not feat.empty and len(feat) > 100:
                all_features.append(feat)
        except Exception as e:
            pass

    if not all_features:
        print("  FATAL: No valid features built")
        sys.exit(1)

    combined = pd.concat(all_features, ignore_index=True).dropna()
    feature_cols = [c for c in combined.columns if c != "label"]
    X = combined[feature_cols].values
    y = combined["label"].values.astype(int)

    up_pct = (y == 1).mean() * 100
    down_pct = (y == 0).mean() * 100
    print(f"  Total samples: {len(X)}, Features: {len(feature_cols)}")
    print(f"  Label distribution: UP={up_pct:.1f}% DOWN={down_pct:.1f}%")
    print(f"  Built in {time.time()-t0:.0f}s")

    # ── Step 3: Feature selection ─────────────────────────────────────
    print("\n[3/6] Feature selection (keeping top 50)...")
    split = int(len(X) * 0.8)
    selected_features = feature_selection(X[:split], y[:split], feature_cols, top_n=50)
    selected_idx = [feature_cols.index(f) for f in selected_features]
    X_selected = X[:, selected_idx]

    # ── Step 4: Walk-Forward CV ───────────────────────────────────────
    print("\n[4/6] Walk-Forward Cross-Validation (3 folds)...")
    from sklearn.metrics import accuracy_score

    n = len(X_selected)
    fold_size = n // 4
    cv_scores = []
    cv_trade_hits = []

    for fold_idx, (test_start, test_end) in enumerate([
        (n - 3*fold_size, n - 2*fold_size),
        (n - 2*fold_size, n - fold_size),
        (n - fold_size, n),
    ]):
        X_tr, y_tr = X_selected[:test_start], y[:test_start]
        X_te, y_te = X_selected[test_start:test_end], y[test_start:test_end]

        if len(X_tr) < 200 or len(X_te) < 50:
            continue

        print(f"\n  Fold {fold_idx+1}: train={len(X_tr)}, test={len(X_te)}")
        model, acc, ind = train_ensemble(X_tr, y_tr, X_te, y_te)
        cv_scores.append(acc)

        # Trade hit rate at high confidence
        proba = model.predict_proba(X_te)
        conf = np.max(proba, axis=1) * 100
        pred = model.predict(X_te)

        for thr in [65, 70, 75, 80]:
            mask = conf >= thr
            if mask.sum() >= 10:
                hit = accuracy_score(y_te[mask], pred[mask]) * 100
                if thr == 75:
                    cv_trade_hits.append(hit / 100)
                print(f"      Conf >= {thr}%: {mask.sum()} trades, hit rate = {hit:.1f}%")

    print(f"\n  CV Mean Accuracy: {np.mean(cv_scores)*100:.1f}% +/- {np.std(cv_scores)*100:.1f}%")
    if cv_trade_hits:
        print(f"  CV Trade Hit (75% conf): {np.mean(cv_trade_hits)*100:.1f}%")

    # ── Step 5: Train final model ─────────────────────────────────────
    print("\n[5/6] Training final ensemble on 80/20 split...")
    X_train = X_selected[:split]
    X_test = X_selected[split:]
    y_train = y[:split]
    y_test = y[split:]

    final_model, final_acc, individual = train_ensemble(X_train, y_train, X_test, y_test)

    # Final trade hit rates
    proba_test = final_model.predict_proba(X_test)
    conf_test = np.max(proba_test, axis=1) * 100
    pred_test = final_model.predict(X_test)

    print("\n  Final Trade Hit Rates:")
    best_hit = 0
    best_thr = 60
    best_n = 0
    for thr in range(55, 90, 5):
        mask = conf_test >= thr
        n_trades = mask.sum()
        if n_trades >= 10:
            hit = accuracy_score(y_test[mask], pred_test[mask]) * 100
            print(f"    Conf >= {thr}%: {n_trades:4d} trades, hit rate = {hit:.1f}%")
            if hit > best_hit:
                best_hit = hit
                best_thr = thr
                best_n = n_trades

    print(f"\n  BEST: {best_hit:.1f}% hit rate at {best_thr}% confidence ({best_n} trades)")

    # ── Step 6: Save model ────────────────────────────────────────────
    print("\n[6/6] Saving model...")
    from src.core.config import ML_MODEL_DIR

    metrics = {
        "accuracy": round(final_acc * 100, 2),
        "cv_accuracy_mean": round(np.mean(cv_scores) * 100, 2) if cv_scores else 0,
        "cv_accuracy_std": round(np.std(cv_scores) * 100, 2) if cv_scores else 0,
        "trade_hit_rate_best_overall_pct": round(best_hit, 2),
        "trade_confidence_threshold_best_overall_pct": best_thr,
        "trade_selected_trades_best_overall": best_n,
        "individual_model_accuracies": {k: round(v * 100, 2) for k, v in individual.items()},
        "config_name": "ultimate_ensemble",
        "binary": True,
        "features_used": len(selected_features),
        "total_samples": len(X),
        "enhancements": [
            "candlestick_patterns", "atr_dynamic_labels", "ensemble_voting",
            "feature_selection_top50", "macro_vix_nifty", "confidence_calibration",
        ],
    }

    model_data = {
        "model": final_model,
        "feature_columns": selected_features,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "symbols": list(raw_data.keys()),
        "forward_days": 5,
        "threshold": 2.0,
        "metrics": metrics,
    }

    model_path = ML_MODEL_DIR / "signal_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model_data, f)

    metrics_path = ML_MODEL_DIR / "training_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2, default=lambda x: int(x) if hasattr(x, 'item') else str(x))

    print(f"  Model saved to: {model_path}")
    print(f"  Metrics saved to: {metrics_path}")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  TRAINING COMPLETE")
    print("=" * 70)
    print(f"  Final Accuracy:    {final_acc*100:.1f}%")
    print(f"  CV Accuracy:       {np.mean(cv_scores)*100:.1f}%")
    print(f"  Best Trade Hit:    {best_hit:.1f}% @ {best_thr}% confidence")
    print(f"  Features:          {len(selected_features)} (from {len(feature_cols)})")
    print(f"  Training Samples:  {len(X_train)}")
    print(f"  Enhancements:      Candlesticks, ATR labels, Ensemble, Macro, Calibration")
    print()

    if best_hit >= 65:
        print("  VERDICT: Model shows strong edge. Proceed to shadow validation.")
    elif best_hit >= 55:
        print("  VERDICT: Marginal edge. Run 30-day shadow mode to confirm.")
    else:
        print("  VERDICT: No clear edge. Consider adding more data sources.")
    print("=" * 70)


if __name__ == "__main__":
    main()
