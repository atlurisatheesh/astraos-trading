"""AstraOS Scheduler — paper auto-trade execution engine.

Now includes:
  - Level 0 circuit breaker (consecutive-loss pause, daily/weekly/monthly limits)
  - Kelly Criterion position sizing (Half-Kelly, confidence-scaled)
  - Time-of-day trade suitability filtering
  - Realistic slippage simulation on paper fills
  - Full audit logging on every trade action
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog  # type: ignore

from .engine import push_feed  # type: ignore
from ..knowledge.veteran_intraday_playbook import evaluate_trade_gate
from ..services.email_service import send_trade_alert
from ..services.telegram_service import notify_trade_execution
from ..risk.circuit_breaker import circuit_breaker
from ..risk.position_sizer import calculate_position_size
from ..quant.time_features import IntradayWindow
from ..core.security_hardened import AuditEvent

logger = structlog.get_logger()

IST = ZoneInfo("Asia/Kolkata")

_daily_pnl: float = 0.0
_daily_trades: list[dict] = []
_last_reset_date: str = ""


def _reset_daily_if_needed() -> None:
    """Reset daily counters at the start of a new trading day."""
    global _daily_pnl, _daily_trades, _last_reset_date
    today = datetime.now(IST).strftime("%Y-%m-%d")
    if today != _last_reset_date:
        _daily_pnl = 0.0
        _daily_trades = []
        _last_reset_date = today


async def _is_platform_halted() -> bool:
    """Check the durable platform kill switch and fail closed on errors."""
    try:
        from ..core.database import async_session_factory
        from ..risk.kill_switch import is_platform_halted

        async with async_session_factory() as db:
            return await is_platform_halted(db)
    except Exception as exc:
        logger.error("Kill switch check failed - auto-trade halted", error=str(exc))
        push_feed("RISK", "Auto-trade halted because kill-switch status could not be verified.")
        return True


async def execute_auto_trades(signals: dict[str, dict], config: dict) -> None:
    """Check latest signals and simulate qualifying trades.

    This function is intentionally paper-only. It is suitable for monitoring and
    dry runs, not live broker execution.
    """
    _reset_daily_if_needed()

    if await _is_platform_halted():
        logger.warning("Kill switch active - auto-trade halted")
        return

    # Level 0: Circuit breaker check (consecutive losses, daily/weekly limits)
    cb_status = circuit_breaker.check_all()
    if not cb_status["trading_allowed"]:
        push_feed(
            "RISK",
            f"Circuit breaker active — mode: {cb_status['mode']}. "
            f"Triggers: {', '.join(cb_status.get('triggers', []))}",
        )
        logger.warning("Circuit breaker blocked auto-trade", status=cb_status)
        return

    # Time-of-day suitability check
    tod = IntradayWindow.classify(datetime.now(IST))
    if tod["trade_suitability"] < 0.4:
        push_feed(
            "RISK",
            f"Time window '{tod['window_name']}' has low suitability ({tod['trade_suitability']:.1f}) — skipping new entries",
        )
        return

    max_daily_loss = config.get("max_daily_loss", 15000)
    if _daily_pnl < -max_daily_loss:
        push_feed(
            "RISK",
            f"Daily loss limit hit (Rs {abs(_daily_pnl):,.0f}). Auto-trade paused until tomorrow.",
        )
        logger.warning("Daily loss limit breached", pnl=_daily_pnl, limit=max_daily_loss)
        return

    min_confidence = config.get("min_confidence", 82)
    min_risk_reward = config.get("min_risk_reward", 1.8)
    max_position_size = config.get("max_position_size", 50000)
    max_positions = config.get("max_positions", 3)
    capital = config.get("capital", 1_000_000)

    recent_alerts = []
    recent_news = []
    try:
        from .live_scanner import get_alerts  # type: ignore

        recent_alerts = get_alerts(limit=25)
    except Exception:
        recent_alerts = []

    try:
        from ..services.news_service import get_news_provider

        recent_news = await get_news_provider().fetch_news(
            query="RBI OR Fed OR inflation OR policy India market",
            limit=8,
        )
    except Exception:
        recent_news = []

    gate = evaluate_trade_gate(now=datetime.now(IST), alerts=recent_alerts, news_items=recent_news)
    if not gate.allowed:
        push_feed("RISK", f"Veteran trade gate blocked fresh entries: {', '.join(gate.reasons)}")
        logger.info("Auto-trade blocked by veteran gate", reasons=gate.reasons)
        return

    qualifying = []
    for symbol, signal in signals.items():
        if (
            signal.get("confidence", 0) >= min_confidence
            and signal.get("action") in ("BUY", "SELL")
            and signal.get("risk_reward", 0) >= min_risk_reward
            and signal.get("entry", 0) > 0
            and signal.get("stop_loss", 0) > 0
            and signal.get("target", 0) > 0
            and not _is_already_positioned(symbol)
        ):
            qualifying.append((symbol, signal))

    qualifying.sort(key=lambda x: x[1].get("confidence", 0), reverse=True)
    available_slots = max(0, max_positions - len(_daily_trades))
    qualifying = qualifying[:available_slots]

    if not qualifying:
        return

    for symbol, signal in qualifying:
        try:
            action = signal["action"]
            entry_price = signal.get("entry", 0)
            target = signal.get("target", 0)
            stop_loss = signal.get("stop_loss", 0)
            risk_reward = signal.get("risk_reward", 0)
            confidence = signal.get("confidence", 0)

            if entry_price <= 0:
                continue

            if risk_reward < min_risk_reward:
                logger.info(
                    "Trade skipped due to low risk reward",
                    symbol=symbol,
                    risk_reward=risk_reward,
                    min_risk_reward=min_risk_reward,
                )
                continue

            # Kelly Criterion position sizing
            pos = calculate_position_size(
                capital=capital,
                entry_price=entry_price,
                stop_loss=stop_loss,
                confidence=confidence,
                max_risk_pct=config.get("max_risk_per_trade_pct", 2.0),
                lot_size=signal.get("lot_size", 1),
            )

            if pos.quantity <= 0:
                logger.info("Position size too small", symbol=symbol, reason=pos.reasoning)
                continue

            quantity = pos.quantity
            position_value = pos.position_value

            # Simulate realistic fill with slippage
            import random
            slippage_bps = random.uniform(2, 10)  # 2-10 basis points
            slippage_amount = entry_price * slippage_bps / 10000
            fill_price = entry_price + slippage_amount if action == "BUY" else entry_price - slippage_amount

            trade = {
                "symbol": symbol,
                "action": action,
                "quantity": quantity,
                "entry_price": entry_price,
                "fill_price": round(fill_price, 2),
                "slippage": round(slippage_amount, 2),
                "target": target,
                "stop_loss": stop_loss,
                "confidence": confidence,
                "position_value": round(quantity * fill_price, 2),
                "kelly_fraction": round(pos.kelly_fraction, 4),
                "risk_per_trade": round(pos.risk_per_trade, 2),
                "time_window": tod["window_name"],
                "timestamp": datetime.now(IST).isoformat(),
                "status": "PAPER_EXECUTED",
                "broker": "paper",
            }
            _daily_trades.append(trade)

            push_feed(
                "AUTO_TRADE",
                f"{action} {quantity} {symbol} @ Rs {entry_price:,.2f} | "
                f"Target Rs {target:,.0f} | SL Rs {stop_loss:,.0f} | Conf {confidence:.0f}%",
                trade,
            )

            # Audit log the trade
            AuditEvent.log_trade(
                user_id="system_auto_trader",
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=fill_price,
                broker="paper",
            )

            logger.info(
                "Paper auto-trade executed",
                symbol=symbol,
                action=action,
                qty=quantity,
                price=fill_price,
                slippage=slippage_amount,
                kelly=pos.kelly_fraction,
                confidence=confidence,
            )

            asyncio.create_task(
                notify_trade_execution(
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    price=entry_price,
                    reason=f"Paper AI Signal (Conf {confidence:.0f}%)",
                )
            )

            asyncio.create_task(
                send_trade_alert(
                    symbol=symbol,
                    side=action,
                    quantity=quantity,
                    price=entry_price,
                    reason=f"Paper AI Signal (Conf {confidence:.0f}%)",
                )
            )

        except Exception as exc:
            logger.error("Auto-trade execution failed", symbol=symbol, error=str(exc))
            push_feed("ERROR", f"Trade execution failed for {symbol}: {exc}")


def _is_already_positioned(symbol: str) -> bool:
    """Check if we already have an open paper position for this symbol today."""
    return any(t["symbol"] == symbol for t in _daily_trades)


def get_daily_trades() -> list[dict]:
    """Get all paper trades executed today."""
    _reset_daily_if_needed()
    return _daily_trades.copy()


def get_daily_pnl() -> float:
    """Get today's paper P&L."""
    return _daily_pnl
