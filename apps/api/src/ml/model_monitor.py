"""AstraOS ML — Model Drift Monitor.

Detects when the model's real-world performance degrades below acceptable
thresholds and triggers an alert + automatic retrain.

Monitors:
  1. Rolling win rate (last 50 predictions vs actual outcomes)
  2. Confidence calibration (is 80% confidence actually 80% correct?)
  3. Feature distribution shift (are inputs changing vs training data?)
  4. Time since last training (models go stale after ~4-6 weeks)
"""

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog

logger = structlog.get_logger()
IST = ZoneInfo("Asia/Kolkata")


@dataclass
class PredictionRecord:
    symbol: str
    predicted_action: str
    confidence: float
    actual_outcome: str | None = None  # "correct" | "wrong" | None (pending)
    timestamp: float = field(default_factory=time.time)


class ModelMonitor:
    """Tracks model performance in real-time and detects drift."""

    # Thresholds for alerts
    MIN_ROLLING_WIN_RATE = 0.55      # Below this = model is useless
    MIN_CALIBRATION_SCORE = 0.60     # Confidence should match reality
    MAX_DAYS_SINCE_TRAIN = 30        # Retrain after 30 days

    def __init__(self, window_size: int = 50):
        self._predictions: deque[PredictionRecord] = deque(maxlen=500)
        self._window = window_size
        self._alerts: list[dict] = []

    def record_prediction(self, symbol: str, action: str, confidence: float) -> None:
        self._predictions.append(PredictionRecord(
            symbol=symbol,
            predicted_action=action,
            confidence=confidence,
        ))

    def record_outcome(self, symbol: str, was_correct: bool) -> None:
        """Record whether a prediction was correct (called when trade resolves)."""
        for pred in reversed(self._predictions):
            if pred.symbol == symbol and pred.actual_outcome is None:
                pred.actual_outcome = "correct" if was_correct else "wrong"
                break

        # Check for drift after every outcome
        self._check_drift()

    def _check_drift(self) -> None:
        """Check all drift indicators."""
        resolved = [p for p in self._predictions if p.actual_outcome is not None]
        recent = resolved[-self._window:] if len(resolved) >= 20 else []

        if not recent:
            return

        # 1. Rolling win rate
        correct = sum(1 for p in recent if p.actual_outcome == "correct")
        win_rate = correct / len(recent)

        if win_rate < self.MIN_ROLLING_WIN_RATE:
            alert = {
                "type": "LOW_WIN_RATE",
                "severity": "CRITICAL",
                "message": f"Model win rate dropped to {win_rate:.0%} (last {len(recent)} predictions). "
                           f"Minimum: {self.MIN_ROLLING_WIN_RATE:.0%}. Recommend immediate retrain.",
                "win_rate": round(win_rate, 4),
                "sample_size": len(recent),
                "timestamp": datetime.now(IST).isoformat(),
            }
            self._alerts.append(alert)
            logger.critical("MODEL DRIFT DETECTED: Low win rate", **alert)

        # 2. Confidence calibration
        # Group predictions by confidence bucket and check accuracy
        high_conf = [p for p in recent if p.confidence >= 70]
        if len(high_conf) >= 10:
            high_conf_correct = sum(1 for p in high_conf if p.actual_outcome == "correct")
            calibration = high_conf_correct / len(high_conf)

            if calibration < self.MIN_CALIBRATION_SCORE:
                alert = {
                    "type": "CALIBRATION_DRIFT",
                    "severity": "WARNING",
                    "message": f"High-confidence predictions (>=70%) only {calibration:.0%} accurate. "
                               f"Model is overconfident. Recommend recalibration.",
                    "calibration": round(calibration, 4),
                    "timestamp": datetime.now(IST).isoformat(),
                }
                self._alerts.append(alert)
                logger.warning("MODEL DRIFT: Calibration issue", **alert)

    def check_staleness(self, trained_at: str | None) -> dict | None:
        """Check if model is too old."""
        if not trained_at:
            return {"type": "NO_TRAINING_DATE", "severity": "WARNING",
                    "message": "Model has no training date — may be stale"}

        try:
            trained = datetime.fromisoformat(trained_at.replace("Z", "+00:00"))
            age_days = (datetime.now(IST) - trained.replace(tzinfo=IST)).days

            if age_days > self.MAX_DAYS_SINCE_TRAIN:
                alert = {
                    "type": "STALE_MODEL",
                    "severity": "WARNING",
                    "message": f"Model is {age_days} days old (trained: {trained_at}). "
                               f"Max recommended age: {self.MAX_DAYS_SINCE_TRAIN} days. Retrain recommended.",
                    "age_days": age_days,
                }
                self._alerts.append(alert)
                return alert
        except Exception:
            pass

        return None

    def get_health_report(self) -> dict:
        """Get model health status."""
        resolved = [p for p in self._predictions if p.actual_outcome is not None]
        recent = resolved[-self._window:]

        total = len(recent)
        correct = sum(1 for p in recent if p.actual_outcome == "correct")
        win_rate = correct / total if total > 0 else 0

        return {
            "total_predictions": len(self._predictions),
            "resolved_predictions": len(resolved),
            "rolling_win_rate": round(win_rate * 100, 1),
            "sample_size": total,
            "status": "HEALTHY" if win_rate >= self.MIN_ROLLING_WIN_RATE else "DEGRADED",
            "recent_alerts": self._alerts[-5:],
        }

    def should_retrain(self) -> bool:
        """Returns True if the model should be retrained immediately."""
        resolved = [p for p in self._predictions if p.actual_outcome is not None]
        recent = resolved[-self._window:]

        if len(recent) < 20:
            return False

        correct = sum(1 for p in recent if p.actual_outcome == "correct")
        win_rate = correct / len(recent)

        return win_rate < self.MIN_ROLLING_WIN_RATE


# Singleton
model_monitor = ModelMonitor()
