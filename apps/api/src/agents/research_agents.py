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

        # Score based on indicators
        bullish_count = 0
        total = 0

        # Trend
        if summary["trend"] == "bullish":
            bullish_count += 3
        total += 3

        # Momentum
        if summary["momentum"] == "oversold":
            bullish_count += 2  # Contrarian buy
        elif summary["momentum"] == "neutral":
            bullish_count += 1
        total += 2

        # MACD
        if summary["macd"] > summary["macd_signal"]:
            bullish_count += 2
        total += 2

        # ADX strength
        if summary["adx"] > 25:
            bullish_count += 1
        total += 1

        confidence = (bullish_count / total) * 100 if total else 50
        signal = "bullish" if confidence > 60 else "bearish" if confidence < 40 else "neutral"

        return AgentResult(
            agent_name=self.name,
            signal=signal,
            confidence=confidence,
            reasoning=f"Trend: {summary['trend']}, RSI: {summary['rsi']:.1f}, MACD: {'bullish' if summary['macd'] > summary['macd_signal'] else 'bearish'}, ADX: {summary['adx']:.1f}",
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

        if pcr > 1.2:
            signal, confidence = "bullish", 65 + min(20, (pcr - 1.2) * 50)
            reasoning = f"PCR {pcr:.2f} — high put writing suggests support"
        elif pcr < 0.8:
            signal, confidence = "bearish", 65 + min(20, (0.8 - pcr) * 50)
            reasoning = f"PCR {pcr:.2f} — low PCR suggests bearish sentiment"
        else:
            signal, confidence = "neutral", 50
            reasoning = f"PCR {pcr:.2f} — balanced put/call ratio"

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
            data={"pcr": round(pcr, 2), "total_call_oi": total_call_oi, "total_put_oi": total_put_oi},
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
        confidence = 40 + (abs(sentiment - 0.5) * 100)

        signal = "bullish" if sentiment > 0.6 else "bearish" if sentiment < 0.4 else "neutral"
        return AgentResult(
            agent_name=self.name, signal=signal, confidence=min(85, confidence),
            reasoning=f"Keyword analysis: {len(news)} articles — {bullish_score} bullish vs {bearish_score} bearish",
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

    SECTOR_MAP = {
        "RELIANCE": "^CNXENERGY", "ONGC": "^CNXENERGY", "BPCL": "^CNXENERGY",
        "TCS": "^CNXIT", "INFY": "^CNXIT", "WIPRO": "^CNXIT", "HCLTECH": "^CNXIT",
        "HDFCBANK": "^CNXBANK", "ICICIBANK": "^CNXBANK", "SBIN": "^CNXBANK",
        "SUNPHARMA": "^CNXPHARMA", "CIPLA": "^CNXPHARMA", "DRREDDY": "^CNXPHARMA",
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
