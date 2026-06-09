"""Test the complete market analysis engine on live stocks."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def test():
    from src.quant.market_analyzer import analyze_stock_complete

    symbols = ["RELIANCE", "HDFCBANK", "INFY"]

    for sym in symbols:
        print("\n" + "=" * 70)
        print(f"  COMPLETE ANALYSIS: {sym}")
        print("=" * 70)

        analysis = await analyze_stock_complete(sym)
        d = analysis.to_dict()

        # Verdict
        verdict = d["verdict"]
        conf = d["confidence"]
        print(f"\n  VERDICT:    {verdict} (confidence: {conf}%)")
        print(f"  PRICE:      Rs {d['price']:,.2f}")
        print(f"  REGIME:     {d['regime']} (volatility: {d['volatility']}%)")

        # Scores
        print(f"\n  Score Breakdown:")
        scores = d["scores"]
        for name, score in sorted(scores.items(), key=lambda x: abs(x[1]), reverse=True):
            bar_len = int(abs(score) / 5)
            direction = "+" if score > 0 else "-"
            bar = direction * bar_len
            label = "BULLISH" if score > 20 else "BEARISH" if score < -20 else "NEUTRAL"
            print(f"    {name:12s} {score:+6.1f}  {bar:20s}  {label}")

        # Key Levels
        print(f"\n  Key Levels:")
        levels = d["levels"]
        print(f"    Resistance 2:  Rs {levels['resistance_2']:,.2f}")
        print(f"    Resistance 1:  Rs {levels['resistance_1']:,.2f}")
        print(f"    VWAP:          Rs {levels['vwap']:,.2f}")
        print(f"    Pivot:         Rs {levels['pivot']:,.2f}")
        print(f"    Support 1:     Rs {levels['support_1']:,.2f}")
        print(f"    Support 2:     Rs {levels['support_2']:,.2f}")

        # Risk
        risk = d["risk"]
        print(f"\n  Trade Setup:")
        print(f"    Entry:         Rs {d['price']:,.2f}")
        print(f"    Stop Loss:     Rs {risk['suggested_sl']:,.2f}")
        print(f"    Target:        Rs {risk['suggested_target']:,.2f}")
        print(f"    Risk/Reward:   {risk['risk_reward']:.2f}")
        print(f"    ATR:           Rs {risk['atr']:,.2f}")

        # Candlestick Patterns
        candles = d["candlestick_patterns"]
        if candles:
            print(f"\n  Candlestick Patterns ({len(candles)} detected):")
            for cp in candles[:5]:
                stars = "*" * cp["reliability"]
                print(f"    {stars:5s} {cp['name']:25s} {cp['signal']:8s}  {cp['description'][:50]}")
        else:
            print(f"\n  Candlestick Patterns: None detected")

        # Chart Patterns
        charts = d["chart_patterns"]
        if charts:
            print(f"\n  Chart Patterns ({len(charts)} detected):")
            for chp in charts[:3]:
                print(f"    {chp['pattern']:25s} {chp['signal']:8s}  conf={chp['confidence']:.0%}")
        else:
            print(f"\n  Chart Patterns: None detected")

        # Reasoning
        print(f"\n  REASONING: {d['reasoning']}")

    print("\n" + "=" * 70)
    print("  Analysis complete.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test())
