#!/usr/bin/env python3
"""AstraOS — End-to-End Training & Validation Script.

Run this to:
  1. Train the XGBoost model on NIFTY 50 (3 years data)
  2. Run a historical backtest WITH transaction costs
  3. Evaluate go-live readiness criteria
  4. Print a clear PASS/FAIL report

Usage:
  cd D:\\stocks-monitoring\\apps\\api
  python scripts/train_and_validate.py

Prerequisites:
  pip install xgboost scikit-learn yfinance pandas numpy ta structlog pydantic-settings
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    print("=" * 70)
    print("  AstraOS — Model Training & Validation Pipeline")
    print("=" * 70)
    print()

    # ── Step 1: Train the model ───────────────────────────────────────
    print("[1/4] Training XGBoost on NIFTY 50 (3 years data)...")
    print("       This takes 15-30 minutes. Please wait.\n")

    from src.ml.trainer import train_signal_model_sync, get_training_status
    from src.ml.training_scheduler import NIFTY_50

    start = time.time()
    train_signal_model_sync(NIFTY_50, period="3y", forward_days=5, threshold=1.5)
    elapsed = time.time() - start

    status = get_training_status()
    if status["status"] != "completed":
        print(f"\n  TRAINING FAILED: {status.get('error', 'Unknown error')}")
        sys.exit(1)

    metrics = status["metrics"]
    print(f"  Training complete in {elapsed/60:.1f} minutes")
    print(f"  Overall accuracy: {metrics['accuracy']}%")
    print(f"  CV accuracy (out-of-sample): {metrics.get('cv_accuracy_mean', 'N/A')}%")
    print(f"  Trade hit rate (BUY/SELL only): {metrics.get('trade_hit_rate_best_overall_pct', 'N/A')}%")
    print(f"  Optimal confidence threshold: {metrics.get('trade_confidence_threshold_best_overall_pct', 'N/A')}%")
    print()

    # ── Step 2: Register model ────────────────────────────────────────
    print("[2/4] Registering model in versioned registry...")
    from src.ml.model_registry import register_model, CURRENT_MODEL, list_models

    result = register_model(CURRENT_MODEL, metrics)
    print(f"  Model v{result['version']} — {'PROMOTED' if result['promoted'] else 'NOT PROMOTED'}")
    print(f"  Reason: {result['promotion_reason']}")
    print()

    # ── Step 3: Backtest with transaction costs ───────────────────────
    print("[3/4] Running walk-forward backtest WITH transaction costs...")
    print("       (This simulates real-world P&L)\n")

    import yfinance as yf
    import pandas as pd
    from src.quant.backtester import (
        walk_forward_backtest, BacktestConfig, simple_momentum_strategy,
    )
    from src.quant.transaction_costs import Segment, Broker

    # Test on top 5 liquid stocks
    test_symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK"]
    all_dfs = []
    for sym in test_symbols:
        try:
            df = yf.download(f"{sym}.NS", period="3y", interval="1d", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if not df.empty:
                all_dfs.append(df)
        except Exception:
            pass

    if all_dfs:
        combined_df = pd.concat(all_dfs).sort_index()

        # Without costs
        bt_no_costs = walk_forward_backtest(
            combined_df,
            simple_momentum_strategy,
            config=BacktestConfig(include_costs=False),
        )

        # With costs
        bt_with_costs = walk_forward_backtest(
            combined_df,
            simple_momentum_strategy,
            config=BacktestConfig(
                segment=Segment.EQUITY_INTRADAY,
                broker=Broker.ZERODHA,
                include_costs=True,
            ),
        )

        print(f"  Backtest Results (SMA20 momentum, {len(test_symbols)} stocks):")
        print(f"  {'Metric':<25} {'Without Costs':>15} {'With Costs':>15} {'Difference':>15}")
        print(f"  {'-'*70}")
        print(f"  {'Total P&L':<25} {'Rs {:,.0f}'.format(bt_no_costs.total_pnl):>15} {'Rs {:,.0f}'.format(bt_with_costs.total_pnl):>15} {'Rs {:,.0f}'.format(bt_with_costs.total_pnl - bt_no_costs.total_pnl):>15}")
        print(f"  {'Win Rate':<25} {bt_no_costs.win_rate:>14.1f}% {bt_with_costs.win_rate:>14.1f}% {bt_with_costs.win_rate - bt_no_costs.win_rate:>14.1f}%")
        print(f"  {'Sharpe Ratio':<25} {bt_no_costs.sharpe_ratio:>15.3f} {bt_with_costs.sharpe_ratio:>15.3f} {bt_with_costs.sharpe_ratio - bt_no_costs.sharpe_ratio:>15.3f}")
        print(f"  {'Sortino Ratio':<25} {bt_no_costs.sortino_ratio:>15.3f} {bt_with_costs.sortino_ratio:>15.3f} {bt_with_costs.sortino_ratio - bt_no_costs.sortino_ratio:>15.3f}")
        print(f"  {'Profit Factor':<25} {bt_no_costs.profit_factor:>15.2f} {bt_with_costs.profit_factor:>15.2f} {bt_with_costs.profit_factor - bt_no_costs.profit_factor:>15.2f}")
        print(f"  {'Max Drawdown':<25} {bt_no_costs.max_drawdown:>14.2f}% {bt_with_costs.max_drawdown:>14.2f}% {bt_with_costs.max_drawdown - bt_no_costs.max_drawdown:>14.2f}%")
        print(f"  {'Total Costs':<25} {'Rs 0':>15} {'Rs {:,.0f}'.format(bt_with_costs.total_costs):>15}")
        print(f"  {'Cost Drag':<25} {'0%':>15} {bt_with_costs.cost_breakdown.get('cost_as_pct_of_gross', 0):>14.1f}%")
        print()

        print(f"  Monte Carlo (with costs) — 1000 simulations:")
        mc = bt_with_costs.monte_carlo
        print(f"    5th percentile (worst case):  Rs {mc.get('p5', 0):>12,.0f}")
        print(f"    50th percentile (median):     Rs {mc.get('p50', 0):>12,.0f}")
        print(f"    95th percentile (best case):  Rs {mc.get('p95', 0):>12,.0f}")
        print()

    # ── Step 4: Go-live readiness check ───────────────────────────────
    print("[4/4] Go-Live Readiness Assessment")
    print(f"  {'-'*50}")

    checks = {
        "ML Model Accuracy": {
            "value": metrics["accuracy"],
            "threshold": 55,
            "passed": metrics["accuracy"] >= 55,
            "unit": "%",
        },
        "CV Accuracy (out-of-sample)": {
            "value": metrics.get("cv_accuracy_mean", 0),
            "threshold": 50,
            "passed": (metrics.get("cv_accuracy_mean") or 0) >= 50,
            "unit": "%",
        },
        "Trade Hit Rate (BUY/SELL)": {
            "value": metrics.get("trade_hit_rate_best_overall_pct", 0),
            "threshold": 55,
            "passed": (metrics.get("trade_hit_rate_best_overall_pct") or 0) >= 55,
            "unit": "%",
        },
        "BUY Precision": {
            "value": metrics.get("per_class", {}).get("BUY", {}).get("precision", 0),
            "threshold": 50,
            "passed": metrics.get("per_class", {}).get("BUY", {}).get("precision", 0) >= 50,
            "unit": "%",
        },
        "SELL Precision": {
            "value": metrics.get("per_class", {}).get("SELL", {}).get("precision", 0),
            "threshold": 50,
            "passed": metrics.get("per_class", {}).get("SELL", {}).get("precision", 0) >= 50,
            "unit": "%",
        },
    }

    all_passed = True
    for name, check in checks.items():
        status_icon = "PASS" if check["passed"] else "FAIL"
        if not check["passed"]:
            all_passed = False
        print(f"  [{status_icon}] {name}: {check['value']}{check['unit']} (need >= {check['threshold']}{check['unit']})")

    print(f"\n  {'-'*50}")

    if all_passed:
        print("  RESULT: MODEL TRAINING PASSED")
        print()
        print("  NEXT STEPS:")
        print("    1. Start the API server:  uvicorn src.main:app --port 8000")
        print("    2. Start the dashboard:   cd ../web && npm run dev")
        print("    3. Enable paper trading:   POST /api/v1/scheduler/auto-trade/enable")
        print("    4. Run 30 TRADING DAYS of shadow validation")
        print("    5. Check readiness:        GET /api/v1/risk/circuit-breaker/status")
        print("    6. Only then consider live trading with 1-lot minimum")
    else:
        print("  RESULT: MODEL NEEDS IMPROVEMENT")
        print()
        print("  ACTIONS:")
        print("    1. Check top_features in training_metrics.json")
        print("    2. Try training with more data: period='5y'")
        print("    3. Try different threshold: threshold=2.0 (more selective)")
        print("    4. DO NOT proceed to live trading")

    print()
    print("=" * 70)

    # Save validation report
    report_path = Path(__file__).parent.parent / "data" / "models" / "validation_report.json"
    report = {
        "training_metrics": metrics,
        "go_live_checks": {k: {**v, "value": float(v["value"]) if v["value"] else 0} for k, v in checks.items()},
        "all_passed": all_passed,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if all_dfs:
        report["backtest_with_costs"] = bt_with_costs.to_dict()
        report["backtest_without_costs"] = bt_no_costs.to_dict()

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"  Report saved to: {report_path}")


if __name__ == "__main__":
    main()
