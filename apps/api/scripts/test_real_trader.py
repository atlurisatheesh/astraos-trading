"""Test the Real Trader Brain — no guessing, only confirmations."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test():
    from src.agents.real_trader_brain import analyze_like_real_trader

    symbols = ["RELIANCE", "HDFCBANK", "INFY", "TCS", "SBIN"]

    print("=" * 70)
    print("  REAL TRADER BRAIN — Zero Guessing, Pure Confirmation")
    print("  (Only trades when ALL 8 checks pass)")
    print("=" * 70)

    for sym in symbols:
        print(f"\n{'-' * 70}")
        print(f"  {sym}")
        print(f"{'-' * 70}")

        decision = await analyze_like_real_trader(sym)
        d = decision.to_dict()

        # Show the decision
        action = d["action"]
        conviction = d["conviction"]

        if action == "NO_TRADE":
            print(f"\n  DECISION:  NO TRADE")
            print(f"  REASON:    {d['reasoning'][:120]}")
        else:
            print(f"\n  DECISION:  {action}")
            print(f"  CONVICTION: {conviction}")
            print(f"  ENTRY:     Rs {d['entry']:,.2f}")
            print(f"  STOP LOSS: Rs {d['stop_loss']:,.2f}")
            print(f"  TARGET 1:  Rs {d['target_1']:,.2f}")
            print(f"  TARGET 2:  Rs {d['target_2']:,.2f}")
            print(f"  RISK/REW:  {d['risk_reward']:.2f}")
            print(f"  SIZE:      {d['position_size_pct']}% of capital")

        # Show checklist
        print(f"\n  CHECKLIST: {d['confirmations']}")
        for c in d["checklist"]:
            icon = "PASS" if c["passed"] else "FAIL"
            strength = "#" * c["strength"]
            print(f"    [{icon}] {c['name']:20s} {strength:10s}  {c['evidence'][:55]}")

        # Show red flags
        if d["red_flags"]:
            print(f"\n  RED FLAGS:")
            for rf in d["red_flags"]:
                print(f"    !! {rf}")

    print(f"\n{'=' * 70}")
    print("  A real trader's output: mostly NO_TRADE. That IS the edge.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test())
