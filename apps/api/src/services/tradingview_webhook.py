# type: ignore
"""AstraOS Services — TradingView Webhook Receiver.

Receives POST webhooks from TradingView alerts and converts them
into trade signals or auto-executes via the broker adapter.

Expected payload format:
{
    "action": "BUY" or "SELL",
    "symbol": "RELIANCE",
    "price": 2850.50,
    "quantity": 10,
    "strategy": "MA_Crossover",
    "timeframe": "1h",
    "message": "MACD bullish crossover on 1h chart"
}
"""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class WebhookSignal:
    """A parsed TradingView webhook signal."""
    action: str
    symbol: str
    price: float
    quantity: int
    strategy: str
    timeframe: str
    message: str
    timestamp: str
    source: str = "tradingview"
    auto_execute: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "symbol": self.symbol,
            "price": self.price,
            "quantity": self.quantity,
            "strategy": self.strategy,
            "timeframe": self.timeframe,
            "message": self.message,
            "timestamp": self.timestamp,
            "source": self.source,
            "auto_execute": self.auto_execute,
        }


class TradingViewWebhookService:
    """Process TradingView webhook alerts."""

    def __init__(self, webhook_secret: str = "") -> None:
        self._secret = webhook_secret
        self._signal_log: list[WebhookSignal] = []
        self._max_log = 500

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify HMAC signature if secret is configured."""
        if not self._secret:
            return True  # No verification if secret not set
        expected = hmac.new(self._secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook(self, data: dict[str, Any], auto_execute: bool = False) -> WebhookSignal:
        """Parse a TradingView webhook payload."""
        signal = WebhookSignal(
            action=data.get("action", "BUY").upper(),
            symbol=data.get("symbol", "").upper().replace(".NS", ""),
            price=float(data.get("price", 0)),
            quantity=int(data.get("quantity", 1)),
            strategy=data.get("strategy", "tradingview_alert"),
            timeframe=data.get("timeframe", ""),
            message=data.get("message", "TradingView alert triggered"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            auto_execute=auto_execute,
        )

        self._signal_log.append(signal)
        if len(self._signal_log) > self._max_log:
            self._signal_log = self._signal_log[-self._max_log:]

        logger.info(
            "TV webhook received",
            action=signal.action,
            symbol=signal.symbol,
            strategy=signal.strategy,
        )
        return signal

    def get_recent_signals(self, limit: int = 50) -> list[WebhookSignal]:
        """Get recent webhook signals."""
        return self._signal_log[-limit:]

    async def execute_signal(self, signal: WebhookSignal) -> dict[str, Any]:
        """Execute a webhook signal through the broker."""
        try:
            from ..broker import get_broker
            broker = get_broker()
            if signal.action == "BUY":
                result = await broker.place_order(
                    symbol=signal.symbol,
                    side="BUY",
                    quantity=signal.quantity,
                    order_type="MARKET",
                )
            elif signal.action == "SELL":
                result = await broker.place_order(
                    symbol=signal.symbol,
                    side="SELL",
                    quantity=signal.quantity,
                    order_type="MARKET",
                )
            else:
                return {"status": "skipped", "reason": f"Unknown action: {signal.action}"}

            return {"status": "executed", "order": result}
        except Exception as e:
            logger.error("Webhook execution failed", error=str(e))
            return {"status": "error", "error": str(e)}


_service: Optional[TradingViewWebhookService] = None

def get_webhook_service() -> TradingViewWebhookService:
    global _service
    if _service is None:
        _service = TradingViewWebhookService()
    return _service
