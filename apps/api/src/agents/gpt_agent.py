"""AstraOS AI — GPT Research Agent & Analyst Chat.

Uses OpenAI GPT-4 (or fallback to Gemini) for:
1. Deep stock research summaries
2. Interactive analyst chat
3. Pattern recognition narratives
"""

import structlog

from ..core.config import settings
from ..knowledge.creator_lessons import get_creator_lesson_prompt
from ..knowledge.veteran_intraday_playbook import get_intraday_playbook_prompt, is_veteran_scalp_symbol

logger = structlog.get_logger()


VETERAN_TRADER_PRINCIPLES = """You think like a veteran Indian trader shaped by decades of market cycles.

Mindset:
- Capital preservation is always first. Flat is a valid position.
- You only act when the edge is clear, risk is defined, and reward justifies the trade.
- You never promise profit, fixed income, or zero-loss outcomes.
- You avoid FOMO, revenge trading, averaging losers, and low-liquidity traps.
- You prefer disciplined execution in NIFTY 50, BANKNIFTY, and liquid large caps.
- You respect regime, volatility, position sizing, and invalidation levels.

Required reasoning rules:
- Start from risk, then setup, then execution.
- If evidence is mixed or incomplete, explicitly say NO TRADE / WAIT.
- Every actionable idea must include: setup, entry zone, stop loss, target zone, invalidation, and why the trade can fail.
- Prefer high-probability, repeatable setups over aggressive predictions.
- Sound experienced, skeptical, and practical rather than promotional.
"""


async def _call_openai(messages: list[dict], model: str = "gpt-4o-mini") -> str:
    """Call OpenAI chat completions API."""
    api_key = settings.openai_api_key
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    import httpx
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages, "max_tokens": 1024, "temperature": 0.4},
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_gemini(prompt: str) -> str:
    """Fallback: call Google Gemini for research."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as exc:
        logger.error("Gemini fallback failed", error=str(exc))
        return ""


async def generate_research_summary(symbol: str, agent_results: list[dict]) -> str:
    """Generate a rich research narrative from agent results using LLM."""
    context = "\n".join(
        f"- {r.get('agent', 'unknown')}: {r.get('signal', 'neutral')} "
        f"(confidence={r.get('confidence', 0)}%) — {r.get('reasoning', '')}"
        for r in agent_results
    )

    prompt = f"""You are a senior Indian equity research analyst and battle-tested trader. Summarize the multi-agent analysis for {symbol}.

Agent Results:
{context}

{get_intraday_playbook_prompt(symbol)}

Write a concise investment note covering:
1. Market regime and setup quality
2. Technical and derivatives alignment
3. Key risks and invalidation
4. Actionable plan only if the edge is strong; otherwise say WAIT/NO TRADE
5. Entry / target / stop-loss only when justified

Use professional tone. Reference Indian market context (NSE/BSE, SEBI, FII/DII flows)."""

    messages = [
        {"role": "system", "content": f"You are a senior SEBI-registered research analyst. Be factual, skeptical, and concise.\n\n{VETERAN_TRADER_PRINCIPLES}"},
        {"role": "user", "content": prompt},
    ]

    try:
        return await _call_openai(messages)
    except Exception:
        logger.info("OpenAI unavailable, using Gemini fallback")
        return await _call_gemini(prompt)


async def analyst_chat(user_message: str, history: list[dict] | None = None) -> str:
    """Interactive analyst chat — answers questions about stocks and strategies."""
    intraday_focus = any(token in user_message.upper() for token in ("NIFTY", "BANKNIFTY", "SCALP", "INTRADAY"))
    playbook = get_intraday_playbook_prompt("BANKNIFTY" if intraday_focus else "")
    system_prompt = f"""You are Quantus AI, an expert Indian stock market analyst chatbot.
You have deep knowledge of:
- NSE/BSE equity markets, NIFTY 50, Bank NIFTY, sectoral indices
- F&O derivatives (options chain analysis, PCR, max pain, Greeks, IV)
- Technical analysis (RSI, MACD, Bollinger Bands, support/resistance)
- Fundamental analysis (P/E, EPS, ROCE, debt ratios)
- Investment frameworks (Graham value, Fisher quality, CANSLIM)
- SEBI regulations and risk management

Rules:
- Always add disclaimer: "Not financial advice. Do your own research."
- Never guarantee profit, daily income, or zero-loss outcomes
- Be concise (max 300 words)
- Use Indian market terminology (lakhs, crores, NSE symbols)
- Reference current market conditions when possible
- If setup quality is weak, explicitly say WAIT or NO TRADE
- Prefer disciplined setups in liquid instruments and explain invalidation clearly

{VETERAN_TRADER_PRINCIPLES}"""
    if playbook:
        system_prompt = f"{system_prompt}\n\n{playbook}"

    creator_lessons = get_creator_lesson_prompt(user_message)
    if creator_lessons:
        system_prompt = f"{system_prompt}\n\n{creator_lessons}"

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history[-10:])  # Last 10 messages for context
    messages.append({"role": "user", "content": user_message})

    try:
        return await _call_openai(messages)
    except Exception:
        logger.info("OpenAI unavailable for chat, using Gemini")
        return await _call_gemini(f"You are a stock market analyst chatbot. User asks: {user_message}")


async def detect_patterns(symbol: str, ohlcv_data: list[dict]) -> list[dict]:
    """Use LLM to identify chart patterns from OHLCV data."""
    if not ohlcv_data:
        return []

    # Take last 30 data points
    recent = ohlcv_data[-30:]
    data_summary = "\n".join(
        f"{d.get('date', '')}: O={d.get('open', 0):.2f} H={d.get('high', 0):.2f} "
        f"L={d.get('low', 0):.2f} C={d.get('close', 0):.2f} V={d.get('volume', 0)}"
        for d in recent
    )

    prompt = f"""Analyze this OHLCV data for {symbol} and identify any chart patterns.

{data_summary}

{get_intraday_playbook_prompt(symbol) if is_veteran_scalp_symbol(symbol) else ''}

Return a JSON array of patterns found. Each pattern:
{{"name": "pattern_name", "confidence": 0-100, "direction": "bullish|bearish|neutral", "description": "brief explanation", "invalidation": "what breaks the pattern"}}

Only identify patterns you are confident about (>60% confidence).
If the chart is noisy or lacks clear structure, return an empty array."""

    messages = [
        {"role": "system", "content": f"You are a technical chart pattern recognition expert. Return only valid JSON.\n\n{VETERAN_TRADER_PRINCIPLES}"},
        {"role": "user", "content": prompt},
    ]

    try:
        import json
        response = await _call_openai(messages, model="gpt-4o-mini")
        # Try to parse JSON from response
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        return json.loads(response)
    except Exception as exc:
        logger.error("Pattern detection failed", error=str(exc))
        return []
