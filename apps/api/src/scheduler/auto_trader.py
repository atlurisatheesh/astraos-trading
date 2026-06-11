"""AstraOS Scheduler — paper auto-trade execution engine."""

import asyncio
import random
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog

from .engine import push_feed
from ..knowledge.veteran_intraday_playbook import evaluate_trade_gate
from ..services.email_service import send_trade_alert
from ..services.telegram_service import notify_trade_execution
from ..risk.circuit_breaker import circuit_breaker
from ..risk.position_sizer import calculate_position_size
from ..risk.earnings_guard import is_earnings_blackout
from ..risk.shadow_validator import shadow_validator
from ..quant.time_features import IntradayWindow
from ..core.security_hardened import AuditEvent
from ..knowledge.creator_strategies import evaluate_creator_gates
from ..ml.model_monitor import model_monitor
from ..agents.outcome_tracker import outcome_tracker
from .position_manager import position_manager

logger = structlog.get_logger()
IST = ZoneInfo("Asia/Kolkata")

_daily_trades: list[dict] = []
_last_reset_date: str = ""


def _reset_daily_if_needed() -> None:
    global _daily_trades, _last_reset_date
    today = datetime.now(IST).strftime("%Y-%m-%d")
    if today != _last_reset_date:
        _daily_trades = []
        _last_reset_date = today


async def _is_platform_halted() -> bool:
    try:
        from ..core.database import async_session_factory
        from ..risk.kill_switch import is_platform_halted
        async with async_session_factory() as db:
            return await is_platform_halted(db)
    except Exception as exc:
        logger.error("Kill switch check failed", error=str(exc))
        push_feed("RISK", "Auto-trade halted — kill-switch unverifiable.")
        return True


async def execute_auto_trades(signals: dict[str, dict], config: dict) -> None:
    """Paper auto-trade engine with full protection stack."""
    _reset_daily_if_needed()

    if await _is_platform_halted():
        return

    cb = circuit_breaker.check_all()
    if not cb["trading_allowed"]:
        push_feed("RISK", f"Circuit breaker: {cb['mode']} — {', '.join(cb.get('triggers', []))}")
        return

    tod = IntradayWindow.classify(datetime.now(IST))
    if tod["trade_suitability"] < 0.4:
        push_feed("RISK", f"Window '{tod['window_name']}' suitability={tod['trade_suitability']:.1f} — skipping")
        return

    daily_pnl = position_manager.get_daily_pnl()
    max_daily_loss = config.get("max_daily_loss", 15000)
    if daily_pnl < -max_daily_loss:
        push_feed("RISK", f"Daily loss Rs {abs(daily_pnl):,.0f} — paused until tomorrow")
        return

    min_confidence = config.get("min_confidence", 82)
    min_rr = config.get("min_risk_reward", 1.8)
    max_positions = config.get("max_positions", 3)
    capital = config.get("capital", 1_000_000)

    # Veteran gate
    try:
        from .live_scanner import get_alerts
        alerts = get_alerts(limit=25)
    except Exception:
        alerts = []
    try:
        from ..services.news_service import get_news_provider
        news = await get_news_provider().fetch_news(query="RBI OR Fed OR inflation India", limit=8)
    except Exception:
        news = []

    gate = evaluate_trade_gate(now=datetime.now(IST), alerts=alerts, news_items=news)
    if not gate.allowed:
        push_feed("RISK", f"Veteran gate blocked: {', '.join(gate.reasons)}")
        return

    qualifying = [
        (sym, sig) for sym, sig in signals.items()
        if sig.get("confidence", 0) >= min_confidence
        and sig.get("action") in ("BUY", "SELL")
        and sig.get("risk_reward", 0) >= min_rr
        and sig.get("entry", 0) > 0
        and sig.get("stop_loss", 0) > 0
        and sig.get("target", 0) > 0
        and not _is_already_positioned(sym)
    ]
    qualifying.sort(key=lambda x: x[1].get("confidence", 0), reverse=True)
    qualifying = qualifying[: max(0, max_positions - len(_daily_trades))]

    for symbol, signal in qualifying:
        try:
            action = signal["action"]
            entry = signal.get("entry", 0)
            target = signal.get("target", 0)
            sl = signal.get("stop_loss", 0)
            rr = signal.get("risk_reward", 0)
            conf = signal.get("confidence", 0)

            if entry <= 0:
                continue

            # Earnings blackout
            blackout, reason = is_earnings_blackout(symbol)
            if blackout:
                push_feed("RISK", reason)
                continue

            # RealTraderBrain 8-checkpoint gate
            try:
                from ..agents.real_trader_brain import analyze_like_real_trader
                brain = await analyze_like_real_trader(symbol)
                if brain.action == "NO_TRADE":
                    failed = [c.name for c in brain.checklist if not c.passed]
                    push_feed("RISK", f"Brain blocked {symbol}: {brain.confirmations_passed}/8 passed. Failed: {', '.join(failed[:3])}")
                    continue
                push_feed("BRAIN", f"Brain: {brain.conviction} on {symbol} ({brain.confirmations_passed}/8 ✓)")
            except Exception as be:
                logger.warning("RealTraderBrain error", symbol=symbol, error=str(be))

            # Creator gate
            creator = evaluate_creator_gates(
                signal=signal, now=datetime.now(IST),
                rsi=signal.get("rsi", 50), volume_ratio=signal.get("rel_volume", 1.0),
                above_vwap=signal.get("above_vwap", True),
                candle_patterns=signal.get("candlestick_patterns", []),
                regime=signal.get("regime", "normal"),
            )
            if not creator["allowed"]:
                push_feed("RISK", f"Creator blocked {symbol}: {'; '.join(creator['reasons'][:2])}")
                continue

            if rr < min_rr:
                continue

            # Kelly sizing
            pos = calculate_position_size(
                capital=capital, entry_price=entry, stop_loss=sl, confidence=conf,
                max_risk_pct=config.get("max_risk_per_trade_pct", 2.0),
                lot_size=signal.get("lot_size", 1),
            )
            if pos.quantity <= 0:
                continue

            # Slippage simulation
            slip_bps = random.uniform(2, 10)
            slip = entry * slip_bps / 10000
            fill = entry + slip if action == "BUY" else entry - slip

            trade = {
                "symbol": symbol, "action": action,
                "quantity": pos.quantity, "entry_price": entry,
                "fill_price": round(fill, 2), "slippage": round(slip, 2),
                "target": target, "stop_loss": sl, "confidence": conf,
                "position_value": round(pos.quantity * fill, 2),
                "kelly_fraction": round(pos.kelly_fraction, 4),
                "risk_per_trade": round(pos.risk_per_trade, 2),
                "time_window": tod["window_name"],
                "timestamp": datetime.now(IST).isoformat(),
                "status": "PAPER_EXECUTED", "broker": "paper",
            }
            _daily_trades.append(trade)
            position_manager.add_position(trade)

            # Feedback loop 1: shadow validator
            shadow_validator.record_signal(
                symbol=symbol, action=action, entry_price=fill,
                target_price=target, stop_loss=sl, confidence=conf,
                agent_signals=signal.get("agents", {}),
            )

            # Feedback loop 2: outcome tracker (Bayesian reweighting)
            outcome_tracker.record_signal(
                symbol=symbol, action=action, entry_price=fill,
                target_price=target, stop_loss=sl,
                agent_signals={
                    a.get("agent", "?"): {"signal": a.get("signal", "neutral"), "confidence": a.get("confidence", 50)}
                    for a in signal.get("agents", []) if isinstance(a, dict)
                },
            )

            push_feed(
                "AUTO_TRADE",
                f"{action} {pos.quantity} {symbol} @ Rs {entry:,.2f} | "
                f"Target Rs {target:,.0f} | SL Rs {sl:,.0f} | Conf {conf:.0f}%",
                trade,
            )

            AuditEvent.log_trade(
                user_id="system_auto_trader", symbol=symbol, action=action,
                quantity=pos.quantity, price=fill, broker="paper",
            )

            logger.info("Paper trade executed", symbol=symbol, action=action,
                        qty=pos.quantity, fill=fill, kelly=pos.kelly_fraction, conf=conf)

            asyncio.create_task(
                notify_trade_execution(symbol=symbol, side=action, quantity=pos.quantity,
                                       price=entry, reason=f"Paper AI (Conf {conf:.0f}%)")
            )
            asyncio.create_task(
                send_trade_alert(symbol=symbol, side=action, quantity=pos.quantity,
                                 price=entry, reason=f"Paper AI (Conf {conf:.0f}%)")
            )

        except Exception as exc:
            logger.error("Auto-trade failed", symbol=symbol, error=str(exc))
            push_feed("ERROR", f"Trade failed {symbol}: {exc}")


def _is_already_positioned(symbol: str) -> bool:
    return any(t["symbol"] == symbol for t in _daily_trades)


def get_daily_trades() -> list[dict]:
    _reset_daily_if_needed()
    return _daily_trades.copy()


def get_daily_pnl() -> float:
    return position_manager.get_daily_pnl()
