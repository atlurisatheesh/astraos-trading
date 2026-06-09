"""Test the proven strategies knowledge base."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge.proven_strategies import (
    get_strategy_for_conditions, CANDLESTICK_RELIABILITY,
    SMART_MONEY_RULES, BANK_NIFTY_STRATEGIES, RISK_RULES,
)

print("=" * 70)
print("  AstraOS — Proven Strategies Knowledge Base")
print("=" * 70)

print("\n  Strategy Recommendations by Market Condition:\n")
conditions = [
    ("bull", 14, False, False, 10),
    ("sideways", 16, False, False, 10),
    ("bear", 22, False, False, 10),
    ("crisis", 30, False, False, 10),
    ("normal", 15, True, False, 10),
    ("normal", 15, False, True, 10),
]

for regime, vix, expiry, event, hour in conditions:
    rec = get_strategy_for_conditions(regime=regime, vix=vix, is_expiry=expiry, is_event_day=event, time_hour=hour)
    strategy = rec["strategy"]
    reason = rec["reason"][:65]
    print(f"    Regime={regime:8s} VIX={vix:2.0f} Expiry={str(expiry):5s} Event={str(event):5s}")
    print(f"    -> {strategy}")
    print(f"       {reason}")
    print()

print("-" * 70)
print("\n  Top 10 Candlestick Patterns (by backtest win rate):\n")
sorted_p = sorted(CANDLESTICK_RELIABILITY.items(), key=lambda x: x[1][0], reverse=True)
print(f"    {'Pattern':<25s} {'Win Rate':>10s} {'Profit F':>10s} {'Best Context'}")
print(f"    {'-'*75}")
for name, (wr, pf, ctx) in sorted_p[:10]:
    print(f"    {name:<25s} {wr:>9.0%} {pf:>10.1f} {ctx}")

print()
print("-" * 70)
print("\n  Bank Nifty Strategies:\n")
for key, strat in BANK_NIFTY_STRATEGIES.items():
    wr = strat.get("estimated_win_rate", 0)
    rr = strat.get("estimated_rr", 0)
    print(f"    {strat['name']}")
    print(f"      Win Rate: {wr:.0%}  |  Risk/Reward: {rr:.1f}x")
    print(f"      {strat['description']}")
    print()

print("-" * 70)
print("\n  Smart Money — OI Analysis Signals:\n")
for signal, meaning in SMART_MONEY_RULES["oi_analysis"].items():
    print(f"    {signal:20s} -> {meaning}")

print()
print("-" * 70)
print("\n  Risk Rules:\n")
for category, rules in RISK_RULES.items():
    print(f"    [{category}]")
    if isinstance(rules, dict):
        for k, v in rules.items():
            if isinstance(v, list):
                print(f"      {k}: {', '.join(v[:3])}")
            else:
                print(f"      {k}: {v}")
    print()

print("=" * 70)
print("  Knowledge base loaded successfully.")
print("=" * 70)
