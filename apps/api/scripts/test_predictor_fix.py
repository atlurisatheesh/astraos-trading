"""Test that the binary model predictor is working correctly."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test():
    from src.ml.predictor import predict_signal

    print("=" * 60)
    print("  Testing Fixed Binary Predictor")
    print("=" * 60)

    for sym in ["RELIANCE", "TCS", "SBIN", "HDFCBANK", "INFY"]:
        r = await predict_signal(sym)
        action = r.get("action", "?")
        conf = r.get("confidence", 0)
        binary = r.get("binary", "?")
        probs = r.get("probabilities", {})
        regime = r.get("regime", "?")

        print(f"\n  {sym}")
        print(f"    Action:      {action}")
        print(f"    Confidence:  {conf}%")
        print(f"    Binary mode: {binary}")
        print(f"    Probabilities: BUY={probs.get('BUY', '?')}% SELL={probs.get('SELL', '?')}%")
        print(f"    Regime:      {regime}")

        if action == "BUY":
            print(f"    >>> ML says GO LONG")
        elif action == "SELL":
            print(f"    >>> ML says GO SHORT")
        else:
            print(f"    >>> ML says WAIT (not confident enough)")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(test())
