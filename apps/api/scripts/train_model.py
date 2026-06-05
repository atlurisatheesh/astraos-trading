#!/usr/bin/env python3
"""AstraOS CLI — Train XGBoost Signal Model.

Usage:
    python scripts/train_model.py
    python scripts/train_model.py --symbols RELIANCE TCS HDFCBANK --period 2y

This script:
  1. Fetches historical OHLCV data for each symbol via yfinance
  2. Computes 80+ features (technical indicators, volume, volatility)
  3. Labels data (BUY/SELL/HOLD) based on 5-day forward returns
  4. Trains an XGBoost classifier with walk-forward validation
  5. Saves the model to data/models/signal_model.pkl
"""

import argparse
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


async def main():
    parser = argparse.ArgumentParser(description="Train QUANTUS AI signal model")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
                 "SBIN", "BHARTIARTL", "LT", "BAJFINANCE", "WIPRO"],
        help="NSE symbols to train on (default: NIFTY top 10)",
    )
    parser.add_argument(
        "--period",
        default="2y",
        help="Historical period: 1y, 2y, 5y (default: 2y)",
    )

    args = parser.parse_args()

    print(f"\n🧠 QUANTUS AI — Training XGBoost Signal Model")
    print(f"   Symbols: {', '.join(args.symbols)}")
    print(f"   Period:  {args.period}")
    print(f"   {'='*50}\n")

    from src.ml.trainer import train_signal_model, get_training_status

    await train_signal_model(args.symbols, args.period)

    status = get_training_status()

    if status["status"] == "completed":
        metrics = status["metrics"]
        print(f"\n✅ Training complete!")
        print(f"   Accuracy: {metrics['accuracy']}%")
        print(f"   Train samples: {metrics['samples_train']}")
        print(f"   Test samples:  {metrics['samples_test']}")
        print(f"\n   Per-class performance:")
        for cls, vals in metrics["per_class"].items():
            print(f"     {cls:6s} — P:{vals['precision']:5.1f}%  R:{vals['recall']:5.1f}%  F1:{vals['f1']:5.1f}%  Support:{vals['support']}")
        print(f"\n   Top features:")
        for feat in metrics["top_features"][:10]:
            print(f"     {feat['feature']:20s} — {feat['importance']:.2f}%")
        print(f"\n   Model saved to: data/models/signal_model.pkl\n")
    else:
        print(f"\n❌ Training failed: {status.get('error', 'unknown')}\n")


if __name__ == "__main__":
    asyncio.run(main())
