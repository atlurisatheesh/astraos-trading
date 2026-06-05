"""AstraOS AI — Multi-Agent Orchestrator (Research Brain).

Coordinates 5 research agents → synthesis → final signal.
Inspired by LangGraph but built with pure Python (zero cost).
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog

from .research_agents import (
    AgentResult,
    TechnicalAgent,
    DerivativesAgent,
    SentimentAgent,
    MacroAgent,
    SectorAgent,
)

logger = structlog.get_logger()


@dataclass
class SynthesizedSignal:
    """Final synthesized signal from all agents."""
    symbol: str
    action: str           # BUY | SELL | HOLD
    confidence: float     # 0-100
    entry_price: float
    target_price: float
    stop_loss: float
    risk_reward: float
    time_horizon: str
    regime: str
    reasoning: str
    agent_results: list[dict]
    timestamp: datetime

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "confidence": round(self.confidence, 1),
            "entry": round(self.entry_price, 2),
            "target": round(self.target_price, 2),
            "stop_loss": round(self.stop_loss, 2),
            "risk_reward": round(self.risk_reward, 2),
            "time_horizon": self.time_horizon,
            "regime": self.regime,
            "reasoning": self.reasoning,
            "agents": self.agent_results,
            "timestamp": self.timestamp.isoformat(),
        }


# Default agent weights — used until enough accuracy data is collected
DEFAULT_AGENT_WEIGHTS = {
    "technical": 0.30,
    "derivatives": 0.25,
    "sentiment": 0.15,
    "macro": 0.15,
    "sector": 0.15,
}

MIN_ACTION_NET_SCORE = 0.22
MIN_ACTION_CONFIDENCE = 68.0
MIN_ACTION_RISK_REWARD = 1.8
MIN_SUPPORTING_AGENTS = 3

# Bayesian weight tracker — updated as signals prove correct or incorrect
_agent_accuracy: dict[str, dict] = {
    name: {"correct": 1, "total": 2}  # start with weak prior
    for name in DEFAULT_AGENT_WEIGHTS
}


def get_agent_weights() -> dict[str, float]:
    """Return dynamically rebalanced weights based on tracked accuracy.

    Uses Bayesian updating: agents that have been more accurate get
    proportionally more weight. Falls back to defaults until enough
    data is collected (< 20 signals tracked).
    """
    total_tracked = sum(a["total"] for a in _agent_accuracy.values())
    if total_tracked < 20:
        return DEFAULT_AGENT_WEIGHTS.copy()

    # Calculate accuracy-proportional weights
    accuracies = {}
    for name, stats in _agent_accuracy.items():
        accuracies[name] = stats["correct"] / max(stats["total"], 1)

    total_acc = sum(accuracies.values())
    if total_acc == 0:
        return DEFAULT_AGENT_WEIGHTS.copy()

    weights = {name: acc / total_acc for name, acc in accuracies.items()}
    return weights


def update_agent_accuracy(agent_name: str, was_correct: bool) -> None:
    """Update an agent's accuracy record after a signal resolves."""
    if agent_name not in _agent_accuracy:
        _agent_accuracy[agent_name] = {"correct": 0, "total": 0}
    _agent_accuracy[agent_name]["total"] += 1
    if was_correct:
        _agent_accuracy[agent_name]["correct"] += 1
    logger.info(
        "Agent accuracy updated",
        agent=agent_name,
        correct=was_correct,
        stats=_agent_accuracy[agent_name],
    )


AGENT_WEIGHTS = DEFAULT_AGENT_WEIGHTS


def _count_supporting_agents(results: list[AgentResult], action: str) -> int:
    target_signal = "bullish" if action == "BUY" else "bearish"
    return sum(1 for result in results if result.signal == target_signal and result.confidence >= 60)


async def run_research_pipeline(symbol: str) -> SynthesizedSignal:
    """Run all research agents in parallel, then synthesize.

    This is the core "Research Brain" — it replaces the LLM for signal generation.
    Every agent runs independently, then results are weighted and combined.
    """
    agents = [
        TechnicalAgent(),
        DerivativesAgent(),
        SentimentAgent(),
        MacroAgent(),
        SectorAgent(),
    ]

    # Run all agents in parallel (async)
    logger.info("Research pipeline started", symbol=symbol, agents=len(agents))
    results: list[AgentResult] = await asyncio.gather(
        *[agent.analyze(symbol) for agent in agents],
        return_exceptions=True,
    )

    # Filter out exceptions
    valid_results = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("Agent failed", error=str(r))
        else:
            valid_results.append(r)

    if not valid_results:
        return _fallback_signal(symbol)

    # Synthesize: weighted vote
    signal = _synthesize(symbol, valid_results)

    # Optionally enrich reasoning with GPT
    try:
        from .gpt_agent import generate_research_summary
        enriched = await generate_research_summary(symbol, [r.to_dict() for r in valid_results])
        if enriched:
            signal.reasoning = enriched
    except Exception as exc:
        logger.debug("GPT enrichment skipped", reason=str(exc))

    logger.info("Research pipeline complete", symbol=symbol, action=signal.action, confidence=signal.confidence)
    return signal


def _synthesize(symbol: str, results: list[AgentResult]) -> SynthesizedSignal:
    """Combine agent results using dynamically rebalanced weighted scoring."""

    weights = get_agent_weights()

    bullish_score = 0.0
    bearish_score = 0.0
    total_weight = 0.0

    for r in results:
        weight = weights.get(r.agent_name, 0.1)
        confidence_factor = r.confidence / 100

        if r.signal == "bullish":
            bullish_score += weight * confidence_factor
        elif r.signal == "bearish":
            bearish_score += weight * confidence_factor
        # neutral contributes to neither

        total_weight += weight

    # Normalize
    net_score = (bullish_score - bearish_score) / total_weight if total_weight > 0 else 0

    # Determine action
    if net_score > MIN_ACTION_NET_SCORE:
        action = "BUY"
        confidence = 50 + net_score * 100
    elif net_score < -MIN_ACTION_NET_SCORE:
        action = "SELL"
        confidence = 50 + abs(net_score) * 100
    else:
        action = "HOLD"
        confidence = 40 + abs(net_score) * 50

    confidence = min(95, max(20, confidence))

    # Get technical data for price levels
    tech_result = next((r for r in results if r.agent_name == "technical"), None)
    price = tech_result.data.get("price", 0) if tech_result else 0

    # Calculate target and stop loss
    atr = tech_result.data.get("atr", price * 0.02) if tech_result else price * 0.02
    if atr == 0:
        atr = price * 0.02

    if action == "BUY":
        target = price + atr * 3
        stop_loss = price - atr * 1.5
    elif action == "SELL":
        target = price - atr * 3
        stop_loss = price + atr * 1.5
    else:
        target = price
        stop_loss = price

    risk = abs(price - stop_loss) if price != stop_loss else 1
    reward = abs(target - price)
    rr = reward / risk if risk > 0 else 0

    # Get regime
    macro_result = next((r for r in results if r.agent_name == "macro"), None)
    regime = "unknown"
    if macro_result and macro_result.data:
        vix = macro_result.data.get("vix", 15)
        regime = "high_vol" if vix > 25 else "low_vol" if vix < 12 else "normal"

    supporting_agents = _count_supporting_agents(results, action) if action in {"BUY", "SELL"} else 0

    if action in {"BUY", "SELL"}:
        if confidence < MIN_ACTION_CONFIDENCE:
            action = "HOLD"
        elif rr < MIN_ACTION_RISK_REWARD:
            action = "HOLD"
        elif supporting_agents < MIN_SUPPORTING_AGENTS:
            action = "HOLD"
        elif regime == "high_vol" and confidence < 75:
            action = "HOLD"

    # Build reasoning
    reasons = [f"{r.agent_name}: {r.signal} ({r.confidence:.0f}%)" for r in results]
    reasoning = f"Multi-agent consensus: {action}. Agents: {'; '.join(reasons)}"
    if action == "HOLD":
        filters = []
        if confidence < MIN_ACTION_CONFIDENCE:
            filters.append(f"confidence below {MIN_ACTION_CONFIDENCE:.0f}")
        if rr < MIN_ACTION_RISK_REWARD:
            filters.append(f"risk-reward below {MIN_ACTION_RISK_REWARD:.1f}")
        if supporting_agents and supporting_agents < MIN_SUPPORTING_AGENTS:
            filters.append(f"only {supporting_agents} supporting agents")
        if regime == "high_vol":
            filters.append("high-volatility regime")
        if filters:
            reasoning += f". Capital-preservation filter kept trade inactive: {', '.join(filters)}"

    return SynthesizedSignal(
        symbol=symbol,
        action=action,
        confidence=confidence,
        entry_price=price,
        target_price=target,
        stop_loss=stop_loss,
        risk_reward=rr,
        time_horizon="3-5 days",
        regime=regime,
        reasoning=reasoning,
        agent_results=[r.to_dict() for r in results],
        timestamp=datetime.now(timezone.utc),
    )


def _fallback_signal(symbol: str) -> SynthesizedSignal:
    """Fallback when all agents fail."""
    return SynthesizedSignal(
        symbol=symbol, action="HOLD", confidence=0,
        entry_price=0, target_price=0, stop_loss=0,
        risk_reward=0, time_horizon="N/A", regime="unknown",
        reasoning="All research agents failed — defaulting to HOLD",
        agent_results=[], timestamp=datetime.now(timezone.utc),
    )
