"""AstraOS Agent — ML Model Agent.

Wraps the trained XGBoost model as an agent in the orchestrator pipeline.
This is the most objective agent — it's purely data-driven, no heuristics.

The model was trained on 5 years of NIFTY 50 data with 84+ features
and achieves 69.8% trade hit rate at 75% confidence threshold.
"""

import structlog

from .research_agents import AgentResult, BaseAgent

logger = structlog.get_logger()


class MLModelAgent(BaseAgent):
    """Agent that uses the trained XGBoost model for signal generation."""

    name = "ml_model"

    async def analyze(self, symbol: str, context: dict | None = None) -> AgentResult:
        try:
            from ..ml.predictor import predict_signal

            prediction = await predict_signal(symbol)

            if prediction.get("error"):
                return AgentResult(
                    agent_name=self.name,
                    signal="neutral",
                    confidence=0,
                    reasoning=f"ML model error: {prediction['error']}",
                )

            action = prediction.get("signal", "HOLD")
            confidence = prediction.get("confidence", 0)
            probabilities = prediction.get("probabilities", {})
            regime = prediction.get("regime", "unknown")
            model_accuracy = prediction.get("model_accuracy", 0)
            cv_accuracy = prediction.get("cv_accuracy", 0)

            # Check if this is a binary model (UP/DOWN only, no HOLD)
            is_binary = prediction.get("binary", False) or len(probabilities) == 2

            if is_binary:
                # Binary model: class 1=UP (BUY), class 0=DOWN (SELL)
                # The confidence is the probability of the predicted class
                if action == "BUY" or (probabilities.get("BUY", 0) > probabilities.get("SELL", 0)):
                    signal = "bullish"
                else:
                    signal = "bearish"
                # Binary models are more decisive — lower the neutral threshold
                if confidence < 52:
                    signal = "neutral"
                    confidence = max(30, confidence * 0.8)
            else:
                # 3-class model
                if action == "BUY":
                    signal = "bullish"
                elif action == "SELL":
                    signal = "bearish"
                else:
                    signal = "neutral"
                if confidence < 55:
                    signal = "neutral"
                    confidence = max(30, confidence * 0.7)

            reasoning_parts = [
                f"XGBoost {'binary' if is_binary else '3-class'}: {action} ({confidence:.1f}%)",
                f"Accuracy: {model_accuracy}%",
            ]
            if cv_accuracy:
                reasoning_parts.append(f"CV: {cv_accuracy}%")
            if regime != "unknown":
                reasoning_parts.append(f"Regime: {regime}")

            return AgentResult(
                agent_name=self.name,
                signal=signal,
                confidence=min(95, confidence),
                reasoning=" | ".join(reasoning_parts),
                data={
                    "action": action,
                    "probabilities": probabilities,
                    "model_accuracy": model_accuracy,
                    "cv_accuracy": cv_accuracy,
                    "regime": regime,
                    "trained_at": prediction.get("trained_at", ""),
                },
            )

        except Exception as e:
            logger.error("ML agent failed", symbol=symbol, error=str(e))
            return AgentResult(
                agent_name=self.name,
                signal="neutral",
                confidence=0,
                reasoning=f"ML model unavailable: {str(e)[:100]}",
            )
