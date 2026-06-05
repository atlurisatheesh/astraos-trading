"""AstraOS NLP — FinBERT Sentiment Analysis Pipeline.

Uses Hugging Face `transformers` + `ProsusAI/finbert` model for
production-grade financial sentiment analysis.

Zero-cost: Model weights are downloaded once (free), inference is local.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger()

# Lazy-loaded model (downloads ~500MB on first use, then cached)
_model = None
_tokenizer = None


def _load_model():
    """Load FinBERT model (lazy, thread-safe)."""
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer

    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch

        model_name = "ProsusAI/finbert"
        logger.info("Loading FinBERT model", model=model_name)

        _tokenizer = AutoTokenizer.from_pretrained(model_name)
        _model = AutoModelForSequenceClassification.from_pretrained(model_name)
        _model.eval()  # Inference mode

        logger.info("FinBERT loaded successfully")
        return _model, _tokenizer

    except ImportError:
        logger.warning("transformers/torch not installed — using fallback keyword sentiment")
        return None, None
    except Exception as e:
        logger.error("FinBERT load failed", error=str(e))
        return None, None


@dataclass
class SentimentResult:
    """Sentiment analysis result for a single text."""
    text: str
    label: str       # "positive" | "negative" | "neutral"
    score: float     # confidence 0.0 - 1.0
    positive: float
    negative: float
    neutral: float

    def to_dict(self) -> dict:
        return {
            "text": self.text[:100],
            "label": self.label,
            "score": round(self.score, 4),
            "positive": round(self.positive, 4),
            "negative": round(self.negative, 4),
            "neutral": round(self.neutral, 4),
        }


class FinBERTAnalyzer:
    """Production FinBERT sentiment analyzer.

    Features:
    - Batch processing (efficient GPU/CPU utilization)
    - Confidence scoring with 3-class probabilities
    - Graceful fallback to keyword-based when model unavailable
    """

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self._model, self._tokenizer = _load_model()
            self._loaded = True

    async def analyze_text(self, text: str) -> SentimentResult:
        """Analyze sentiment of a single text."""
        results = await self.analyze_batch([text])
        return results[0]

    async def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Analyze sentiment of multiple texts (batched for efficiency)."""
        self._ensure_loaded()

        if self._model is None:
            # Fallback: keyword-based sentiment
            return [self._keyword_fallback(t) for t in texts]

        # Run inference in thread pool (avoid blocking event loop)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._infer_batch, texts)

    def _infer_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Run FinBERT inference on a batch of texts."""
        import torch
        import torch.nn.functional as F

        results = []

        # Process in chunks of 16 (memory efficient)
        chunk_size = 16
        for i in range(0, len(texts), chunk_size):
            chunk = texts[i:i + chunk_size]

            # Tokenize
            inputs = self._tokenizer(
                chunk,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )

            # Inference (no gradient computation)
            with torch.no_grad():
                outputs = self._model(**inputs)
                probs = F.softmax(outputs.logits, dim=-1)

            # FinBERT labels: [positive, negative, neutral]
            for j, text in enumerate(chunk):
                scores = probs[j].tolist()
                positive, negative, neutral = scores[0], scores[1], scores[2]

                if positive >= negative and positive >= neutral:
                    label = "positive"
                    score = positive
                elif negative >= positive and negative >= neutral:
                    label = "negative"
                    score = negative
                else:
                    label = "neutral"
                    score = neutral

                results.append(SentimentResult(
                    text=text, label=label, score=score,
                    positive=positive, negative=negative, neutral=neutral,
                ))

        return results

    def _keyword_fallback(self, text: str) -> SentimentResult:
        """Fallback keyword-based sentiment when FinBERT unavailable."""
        text_lower = text.lower()

        bullish = {"buy", "bullish", "upgrade", "growth", "profit", "record",
                   "surge", "rally", "gain", "strong", "outperform", "beat"}
        bearish = {"sell", "bearish", "downgrade", "loss", "decline", "fall",
                   "crash", "drop", "weak", "underperform", "miss", "warning"}

        bull_count = sum(1 for w in bullish if w in text_lower)
        bear_count = sum(1 for w in bearish if w in text_lower)
        total = bull_count + bear_count

        if total == 0:
            return SentimentResult(
                text=text, label="neutral", score=0.5,
                positive=0.33, negative=0.33, neutral=0.34,
            )

        positive = bull_count / total
        negative = bear_count / total
        neutral = max(0, 1 - positive - negative)

        if positive > negative:
            label, score = "positive", positive
        elif negative > positive:
            label, score = "negative", negative
        else:
            label, score = "neutral", 0.5

        return SentimentResult(
            text=text, label=label, score=score,
            positive=positive, negative=negative, neutral=neutral,
        )

    async def analyze_news_items(self, news_items: list[dict]) -> list[dict]:
        """Analyze sentiment of news items (with title + summary)."""
        texts = [f"{n.get('title', '')}. {n.get('summary', '')}" for n in news_items]
        sentiments = await self.analyze_batch(texts)

        enriched = []
        for item, sent in zip(news_items, sentiments):
            enriched.append({
                **item,
                "sentiment": sent.to_dict(),
            })
        return enriched


# ── Singleton ──
_analyzer: Optional[FinBERTAnalyzer] = None


def get_finbert() -> FinBERTAnalyzer:
    """Get singleton FinBERT analyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = FinBERTAnalyzer()
    return _analyzer
