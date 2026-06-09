"""Test the improved orchestrator on live stocks."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test():
    from src.agents.orchestrator import run_research_pipeline, get_agent_weights

    symbols = ["RELIANCE", "TCS", "HDFCBANK"]

    print("\n" + "=" * 65)
    print("  AstraOS — Orchestrator Live Test (6 Agents)")
    print("=" * 65)

    weights = get_agent_weights()
    print("\n  Current Agent Weights:")
    for name, w in sorted(weights.items(), key=lambda x: -x[1]):
        bar = "#" * int(w * 50)
        print(f"    {name:15s} {w:.0%}  {bar}")

    for sym in symbols:
        print("\n" + "-" * 65)
        print(f"  Analyzing {sym}...")
        print("-" * 65)

        try:
            signal = await run_research_pipeline(sym)
            d = signal.to_dict()

            action = d["action"]
            conf = d["confidence"]

            if action == "BUY":
                icon = "BUY"
            elif action == "SELL":
                icon = "SELL"
            else:
                icon = "HOLD"

            print(f"  SIGNAL:      {icon} {action}")
            print(f"  CONFIDENCE:  {conf}%")
            print(f"  ENTRY:       Rs {d['entry']:,.2f}")
            print(f"  TARGET:      Rs {d['target']:,.2f}")
            print(f"  STOP LOSS:   Rs {d['stop_loss']:,.2f}")
            print(f"  RISK/REWARD: {d['risk_reward']:.2f}")
            print(f"  REGIME:      {d['regime']}")
            print(f"  REASONING:   {d['reasoning'][:250]}")
            print()
            print("  Per-Agent Breakdown:")
            print(f"  {'Agent':17s} {'Signal':10s} {'Confidence':>12s}")
            print(f"  {'-'*42}")
            for agent in d.get("agents", []):
                name = agent.get("agent", "?")
                sig = agent.get("signal", "?")
                c = agent.get("confidence", 0)
                marker = " ***" if sig in ("bullish", "bearish") and c > 65 else ""
                print(f"  {name:17s} {sig:10s} {c:10.1f}%{marker}")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 65)
    print("  Test complete.")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(test())
