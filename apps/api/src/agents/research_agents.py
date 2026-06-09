"""AstraOS AI Agents — Base Agent Infrastructure."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import structlog

logger = structlog.get_logger()


@dataclass
class AgentResult:
    """Result from an AI research agent."""
    agent_name: str
    signal: str          # "bullish" | "bearish" | "neutral"
    confidence: float    # 0-100
    reasoning: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "signal": self.signal,
            "confidence": round(self.confidence, 1),
            "reasoning": self.reasoning,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseAgent(ABC):
    """Abstract base for all research agents."""

    name: str = "base"

    @abstractmethod
    async def analyze(self, symbol: str, context: dict | None = None) -> AgentResult:
        """Run analysis and return a result."""
        ...


class TechnicalAgent(BaseAgent):
    """Agent specializing in technical analysis (60+ indicators)."""

    name = "technical"

    async def analyze(self, symbol: str, context: dict | None = None) -> AgentResult:
        from ..services.market_data_service import get_market_data_provider
        from ..quant.technical import compute_all_indicators, get_signal_summary

        provider = get_market_data_provider()
        df = await provider.get_ohlcv(symbol, period="1y")

        if df.empty:
            return AgentResult(
                agent_name=self.name, signal="neutral", confidence=0,
                reasoning=f"No data available for {symbol}",
            )

        indicators = compute_all_indicators(df)
        summary = get_signal_summary(indicators)

        # Score on a -100 to +100 scale (negative = bearish, positive = bullish)
        bull_points = 0.0
        bear_points = 0.0
        max_points = 0.0

        # 1. Trend (3 points)
        max_points += 3
        if summary["trend"] == "bullish":
            bull_points += 3
        else:
            bear_points += 3

        # 2. Momentum (2 points)
        max_points += 2
        if summary["momentum"] == "oversold":
            bull_points += 2  # Contrarian buy
        elif summary["momentum"] == "overbought":
            bear_points += 2  # Contrarian sell
        else:
            bull_points += 1  # Slight edge to bulls in neutral

        # 3. MACD (2 points)
        max_points += 2
        if summary["macd"] > summary["macd_signal"]:
            bull_points += 2
        else:
            bear_points += 2

        # 4. ADX trend strength (1 point for the dominant side)
        max_points += 1
        if summary["adx"] > 25:
            if summary["trend"] == "bullish":
                bull_points += 1
            else:
                bear_points += 1

        # 5. VWAP position (2 points)
        max_points += 2
        vwap_dev = summary.get("vwap_dev_pct", 0)
        if summary.get("above_vwap"):
            bull_points += 2
        else:
            bear_points += 2

        # 6. Volume confirmation (2 points)
        max_points += 2
        rel_vol = summary.get("rel_volume", 1)
        has_volume = rel_vol > 1.2
        divergence = summary.get("pv_divergence", False)
        if has_volume and not divergence:
            # Volume confirms the current direction
            if summary["trend"] == "bullish":
                bull_points += 2
            else:
                bear_points += 2
        elif divergence:
            # Divergence — goes against the trend
            if summary["trend"] == "bullish":
                bear_points += 1
            else:
                bull_points += 1

        # 7. Multi-timeframe alignment (3 points)
        max_points += 3
        mtf = summary.get("mtf_alignment", 0)
        bull_points += mtf
        bear_points += (3 - mtf)

        # 8. Breakout detection (2 points)
        max_points += 2
        if summary.get("breakout_up"):
            bull_points += 2
        elif summary.get("breakout_down"):
            bear_points += 2

        # Calculate net score
        net_score = (bull_points - bear_points) / max_points if max_points else 0
        # Convert to 0-100 confidence scale
        confidence = 50 + net_score * 50
        confidence = max(10, min(95, confidence))

        if net_score > 0.15:
            signal = "bullish"
        elif net_score < -0.15:
            signal = "bearish"
        else:
            signal = "neutral"

        reasons = []
        reasons.append(f"Trend: {summary['trend']}")
        reasons.append(f"RSI: {summary['rsi']:.1f}")
        reasons.append(f"MACD: {'bull' if summary['macd'] > summary['macd_signal'] else 'bear'}")
        reasons.append(f"ADX: {summary['adx']:.1f}")
        reasons.append(f"VWAP: {'above' if summary.get('above_vwap') else 'below'} ({vwap_dev:+.1f}%)")
        reasons.append(f"RelVol: {rel_vol:.1f}x")
        reasons.append(f"MTF: {mtf}/3 aligned")
        if summary.get("breakout_up"):
            reasons.append("BREAKOUT UP")
        if summary.get("breakout_down"):
            reasons.append("BREAKOUT DOWN")

        return AgentResult(
            agent_name=self.name,
            signal=signal,
            confidence=confidence,
            reasoning=" | ".join(reasons),
            data=summary,
        )


class DerivativesAgent(BaseAgent):
    """Agent specializing in F&O / options analysis."""

    name = "derivatives"

    async def analyze(self, symbol: str, context: dict | None = None) -> AgentResult:
        from ..services.market_data_service import get_market_data_provider

        provider = get_market_data_provider()
        try:
            chain = await provider.get_options_chain(symbol)
        except Exception:
            return AgentResult(
                agent_name=self.name, signal="neutral", confidence=30,
                reasoning="Options data unavailable",
            )

        calls = chain.get("calls", [])
        puts = chain.get("puts", [])

        total_call_oi = sum(c.get("openInterest", 0) or 0 for c in calls)
        total_put_oi = sum(p.get("openInterest", 0) or 0 for p in puts)

        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else 1.0

        # Calculate max pain (strike with maximum OI on both sides)
        max_pain_strike = 0
        if calls and puts:
            try:
                all_strikes = set()
                call_oi_map = {}
                put_oi_map = {}
                for c in calls:
                    s = c.get("strike", 0)
                    all_strikes.add(s)
                    call_oi_map[s] = c.get("openInterest", 0) or 0
                for p in puts:
                    s = p.get("strike", 0)
                    all_strikes.add(s)
                    put_oi_map[s] = p.get("openInterest", 0) or 0

                # Max pain = strike where total intrinsic loss for option writers is minimum
                min_loss = float("inf")
                for strike in sorted(all_strikes):
                    if strike <= 0:
                        continue
                    loss = 0
                    for s in all_strikes:
                        if s > strike:
                            loss += call_oi_map.get(s, 0) * (s - strike)
                        elif s < strike:
                            loss += put_oi_map.get(s, 0) * (strike - s)
                    if loss < min_loss:
                        min_loss = loss
                        max_pain_strike = strike
            except Exception:
                pass

        # IV Rank estimation (compare current avg IV to 52-week range)
        avg_iv = 0
        try:
            call_ivs = [c.get("impliedVolatility", 0) or 0 for c in calls if c.get("impliedVolatility")]
            put_ivs = [p.get("impliedVolatility", 0) or 0 for p in puts if p.get("impliedVolatility")]
            all_ivs = call_ivs + put_ivs
            if all_ivs:
                avg_iv = sum(all_ivs) / len(all_ivs) * 100
        except Exception:
            pass

        # Enhanced signal logic
        score = 0  # -100 to +100
        reasons = []

        # PCR analysis (primary signal)
        if pcr > 1.3:
            score += 30
            reasons.append(f"PCR {pcr:.2f} (very bullish — heavy put writing)")
        elif pcr > 1.1:
            score += 15
            reasons.append(f"PCR {pcr:.2f} (mildly bullish)")
        elif pcr < 0.7:
            score -= 30
            reasons.append(f"PCR {pcr:.2f} (very bearish — heavy call writing)")
        elif pcr < 0.9:
            score -= 15
            reasons.append(f"PCR {pcr:.2f} (mildly bearish)")
        else:
            reasons.append(f"PCR {pcr:.2f} (neutral)")

        # IV rank (high IV = premium selling opportunity, low IV = buying opportunity)
        if avg_iv > 0:
            if avg_iv > 30:
                reasons.append(f"IV {avg_iv:.0f}% HIGH — premiums expensive")
                score -= 5  # High IV often precedes drops
            elif avg_iv < 15:
                reasons.append(f"IV {avg_iv:.0f}% LOW — premiums cheap")
                score += 5
            else:
                reasons.append(f"IV {avg_iv:.0f}%")

        # Max pain gravity (price tends toward max pain near expiry)
        if max_pain_strike > 0:
            reasons.append(f"MaxPain: {max_pain_strike}")

        # Determine signal
        if score > 20:
            signal = "bullish"
            confidence = 55 + min(30, score)
        elif score < -20:
            signal = "bearish"
            confidence = 55 + min(30, abs(score))
        else:
            signal = "neutral"
            confidence = 45 + abs(score)

        reasoning = " | ".join(reasons)

        # Query RAG Engine for book insights (Natenberg / McMillan)
        try:
            from ..knowledge.rag_engine import get_rag_engine
            rag = get_rag_engine()
            
            # Formulate query based on signal
            if pcr > 1.2:
                rag_query = "options strategies for bullish sentiment and high put call ratio"
            elif pcr < 0.8:
                rag_query = "options strategies for bearish sentiment and low put call ratio"
            else:
                rag_query = "neutral options strategies like iron condor or straddle"
                
            docs = rag.search(rag_query, k=1)
            book_insight = ""
            if docs:
                book_insight = f"\n\n[RAG Insight from {docs[0]['book']} (pg {docs[0]['page']})]: {docs[0]['content'][:150]}..."
                reasoning += book_insight
        except Exception as e:
            # RAG is non-blocking, fail silently if index isn't built yet
            pass

        return AgentResult(
            agent_name=self.name, signal=signal, confidence=confidence,
            reasoning=reasoning,
            data={
                "pcr": round(pcr, 2),
                "total_call_oi": total_call_oi,
                "total_put_oi": total_put_oi,
                "max_pain": max_pain_strike,
                "avg_iv": round(avg_iv, 1),
            },
        )


class SentimentAgent(BaseAgent):
    """Agent analyzing news sentiment (FinBERT-powered, keyword fallback)."""

    name = "sentiment"

    BULLISH_WORDS = {"buy", "bullish", "upgrade", "beat", "outperform", "growth", "profit", "record", "surge", "rally", "gain", "up", "strong", "breakout", "positive"}
    BEARISH_WORDS = {"sell", "bearish", "downgrade", "miss", "underperform", "loss", "decline", "fall", "crash", "drop", "weak", "negative", "warning", "risk", "default"}

    async def analyze(self, symbol: str, context: dict | None = None) -> AgentResult:
        from ..services.news_service import get_news_provider

        provider = get_news_provider()
        news = await provider.fetch_news(query=f"{symbol} stock India NSE", limit=10)

        if not news:
            return AgentResult(
                agent_name=self.name, signal="neutral", confidence=30,
                reasoning="No recent news found",
            )

        # ── Try FinBERT (deep NLP sentiment) ──
        try:
            from ..nlp.finbert import get_finbert

            analyzer = get_finbert()
            news_dicts = [{"title": n.title, "summary": n.summary} for n in news]
            enriched = await analyzer.analyze_news_items(news_dicts)

            # Weighted aggregate: title sentiment counts 2x
            total_positive = 0.0
            total_negative = 0.0
            total_neutral = 0.0
            article_scores = []

            for item in enriched:
                sent = item.get("sentiment", {})
                pos = sent.get("positive", 0.33)
                neg = sent.get("negative", 0.33)
                neu = sent.get("neutral", 0.34)
                total_positive += pos
                total_negative += neg
                total_neutral += neu
                article_scores.append({
                    "title": item.get("title", "")[:80],
                    "label": sent.get("label", "neutral"),
                    "score": round(sent.get("score", 0.5), 3),
                })

            n = len(enriched)
            avg_pos = total_positive / n
            avg_neg = total_negative / n
            avg_neu = total_neutral / n

            # Determine signal
            if avg_pos > avg_neg and avg_pos > avg_neu:
                signal = "bullish"
                confidence = 50 + (avg_pos - max(avg_neg, avg_neu)) * 100
            elif avg_neg > avg_pos and avg_neg > avg_neu:
                signal = "bearish"
                confidence = 50 + (avg_neg - max(avg_pos, avg_neu)) * 100
            else:
                signal = "neutral"
                confidence = 40 + avg_neu * 20

            confidence = min(90, max(25, confidence))

            pos_count = sum(1 for a in article_scores if a["label"] == "positive")
            neg_count = sum(1 for a in article_scores if a["label"] == "negative")

            return AgentResult(
                agent_name=self.name, signal=signal, confidence=confidence,
                reasoning=f"FinBERT analyzed {n} articles: {pos_count} positive, {neg_count} negative. "
                          f"Avg sentiment: pos={avg_pos:.2f}, neg={avg_neg:.2f}, neu={avg_neu:.2f}",
                data={
                    "method": "finbert",
                    "articles": n,
                    "avg_positive": round(avg_pos, 3),
                    "avg_negative": round(avg_neg, 3),
                    "avg_neutral": round(avg_neu, 3),
                    "article_scores": article_scores[:5],
                },
            )

        except Exception as e:
            logger.warning("FinBERT unavailable, using keyword fallback", error=str(e))

        # ── Fallback: keyword-based sentiment ──
        bullish_score = 0
        bearish_score = 0

        for item in news:
            text = (item.title + " " + item.summary).lower()
            bullish_score += sum(1 for w in self.BULLISH_WORDS if w in text)
            bearish_score += sum(1 for w in self.BEARISH_WORDS if w in text)

        total = bullish_score + bearish_score
        if total == 0:
            return AgentResult(
                agent_name=self.name, signal="neutral", confidence=40,
                reasoning="News sentiment neutral — no strong signals",
                data={"method": "keyword", "articles_analyzed": len(news)},
            )

        sentiment = bullish_score / total
        # Keyword sentiment is LOW quality — cap confidence at 60% (not 85-90%)
        confidence = 35 + (abs(sentiment - 0.5) * 50)

        signal = "bullish" if sentiment > 0.65 else "bearish" if sentiment < 0.35 else "neutral"
        return AgentResult(
            agent_name=self.name, signal=signal, confidence=min(60, confidence),
            reasoning=f"Keyword analysis (low reliability): {len(news)} articles — {bullish_score} bullish vs {bearish_score} bearish",
            data={"method": "keyword", "articles": len(news), "bullish_keywords": bullish_score, "bearish_keywords": bearish_score},
        )


class MacroAgent(BaseAgent):
    """Agent analyzing macro indicators (VIX, indices, FII flows)."""

    name = "macro"

    async def analyze(self, symbol: str, context: dict | None = None) -> AgentResult:
        from ..services.market_data_service import get_market_data_provider

        provider = get_market_data_provider()

        # Check India VIX (fear gauge)
        try:
            vix_df = await provider.get_ohlcv("^INDIAVIX", period="1mo", interval="1d")
            if not vix_df.empty:
                col = "Close" if "Close" in vix_df.columns else vix_df.columns[3] if len(vix_df.columns) > 3 else vix_df.columns[0]
                vix = float(vix_df[col].iloc[-1])
            else:
                vix = 15.0
        except Exception:
            vix = 15.0

        # VIX-based regime assessment
        if vix > 25:
            signal, confidence = "bearish", 75
            reasoning = f"VIX at {vix:.1f} — high fear, risk-off environment"
        elif vix < 12:
            signal, confidence = "bullish", 70
            reasoning = f"VIX at {vix:.1f} — low fear, complacency (contrarian caution)"
        else:
            signal, confidence = "neutral", 55
            reasoning = f"VIX at {vix:.1f} — moderate volatility, normal conditions"

        # Query RAG Engine for book insights (Dalton / Sinclair)
        try:
            from ..knowledge.rag_engine import get_rag_engine
            rag = get_rag_engine()
            
            if vix > 25:
                rag_query = "high volatility trading strategies and crisis market regime"
            elif vix < 12:
                rag_query = "low volatility regime complacency and option structures"
            else:
                rag_query = "normal market regime trend allocation"
                
            docs = rag.search(rag_query, k=1)
            book_insight = ""
            if docs:
                book_insight = f"\n\n[RAG Insight from {docs[0]['book']} (pg {docs[0]['page']})]: {docs[0]['content'][:150]}..."
                reasoning += book_insight
        except Exception as e:
            pass

        return AgentResult(
            agent_name=self.name, signal=signal, confidence=confidence,
            reasoning=reasoning, data={"vix": round(vix, 2)},
        )


class SectorAgent(BaseAgent):
    """Agent analyzing relative sector strength."""

    name = "sector"

    # yfinance-compatible NSE sector index symbols
    SECTOR_MAP = {
        # Banking & Financial
        "HDFCBANK": "^NSEBANK", "ICICIBANK": "^NSEBANK", "SBIN": "^NSEBANK",
        "KOTAKBANK": "^NSEBANK", "AXISBANK": "^NSEBANK", "INDUSINDBK": "^NSEBANK",
        "BAJFINANCE": "^NSEBANK", "BAJAJFINSV": "^NSEBANK", "SBILIFE": "^NSEBANK",
        "HDFCLIFE": "^NSEBANK",
        # IT — use NIFTY IT
        "TCS": "^CNXIT", "INFY": "^CNXIT", "WIPRO": "^CNXIT", "HCLTECH": "^CNXIT",
        "TECHM": "^CNXIT", "LTIM": "^CNXIT",
        # Energy — use NIFTY as proxy (energy indices don't work well on yfinance)
        "RELIANCE": "^NSEI", "ONGC": "^NSEI", "BPCL": "^NSEI",
        "NTPC": "^NSEI", "POWERGRID": "^NSEI", "COALINDIA": "^NSEI",
        # Pharma
        "SUNPHARMA": "^CNXPHARMA", "CIPLA": "^CNXPHARMA", "DRREDDY": "^CNXPHARMA",
        "DIVISLAB": "^CNXPHARMA", "APOLLOHOSP": "^CNXPHARMA",
        # Auto — use NIFTY as proxy
        "MARUTI": "^NSEI", "TATAMOTORS": "^NSEI", "M&M": "^NSEI",
        "BAJAJ-AUTO": "^NSEI", "EICHERMOT": "^NSEI", "HEROMOTOCO": "^NSEI",
        # FMCG
        "HINDUNILVR": "^NSEI", "ITC": "^NSEI", "NESTLEIND": "^NSEI",
        "BRITANNIA": "^NSEI", "TATACONSUM": "^NSEI",
        # Metal
        "JSWSTEEL": "^NSEI", "TATASTEEL": "^NSEI", "HINDALCO": "^NSEI",
        # Infrastructure
        "LT": "^NSEI", "ULTRACEMCO": "^NSEI", "GRASIM": "^NSEI",
        "ADANIENT": "^NSEI", "ADANIPORTS": "^NSEI",
        # Others
        "TITAN": "^NSEI", "ASIANPAINT": "^NSEI",
        "BHARTIARTL": "^CNXIT", "UPL": "^CNXPHARMA",
    }

    async def analyze(self, symbol: str, context: dict | None = None) -> AgentResult:
        from ..services.market_data_service import get_market_data_provider

        clean_symbol = symbol.replace(".NS", "").upper()
        sector_index = self.SECTOR_MAP.get(clean_symbol)

        if not sector_index:
            return AgentResult(
                agent_name=self.name, signal="neutral", confidence=40,
                reasoning=f"Sector mapping not found for {symbol}",
            )

        provider = get_market_data_provider()
        try:
            df = await provider.get_ohlcv(sector_index, period="3mo")
            if df.empty:
                raise ValueError("No sector data")

            col = "Close" if "Close" in df.columns else df.columns[3]
            close = df[col].values
            change_1m = (close[-1] - close[-21]) / close[-21] * 100
            change_3m = (close[-1] - close[0]) / close[0] * 100

            if change_1m > 5:
                signal, confidence = "bullish", 70 + min(20, change_1m * 2)
                reasoning = f"Sector up {change_1m:.1f}% in 1M — strong rotation"
            elif change_1m < -5:
                signal, confidence = "bearish", 70 + min(20, abs(change_1m) * 2)
                reasoning = f"Sector down {change_1m:.1f}% in 1M — outflows"
            else:
                signal, confidence = "neutral", 50
                reasoning = f"Sector flat ({change_1m:+.1f}% 1M)"

            return AgentResult(
                agent_name=self.name, signal=signal, confidence=min(90, confidence),
                reasoning=reasoning,
                data={"change_1m": round(change_1m, 2), "change_3m": round(change_3m, 2)},
            )
        except Exception as e:
            return AgentResult(
                agent_name=self.name, signal="neutral", confidence=35,
                reasoning=f"Sector analysis unavailable: {e}",
            )
