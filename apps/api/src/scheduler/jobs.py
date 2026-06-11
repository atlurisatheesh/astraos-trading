"""AstraOS Scheduler — Job Definitions.

Each job is an async function executed by the scheduler engine.
Jobs call existing services (market data, news, agents) and push results to the feed.
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import structlog  # type: ignore

from .engine import push_feed, is_market_hours  # type: ignore

logger = structlog.get_logger()

IST = ZoneInfo("Asia/Kolkata")

# ── NIFTY 50 Universe (top stocks for continuous monitoring) ──
NIFTY_50_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "BAJFINANCE",
    "LT", "KOTAKBANK", "HCLTECH", "AXISBANK", "ASIANPAINT",
    "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "WIPRO",
    "NESTLEIND", "BAJAJFINSV", "NTPC", "TATAMOTORS", "POWERGRID",
    "M&M", "ONGC", "JSWSTEEL", "TATASTEEL", "ADANIENT",
    "ADANIPORTS", "COALINDIA", "GRASIM", "TECHM", "HDFCLIFE",
    "DRREDDY", "BPCL", "DIVISLAB", "CIPLA", "BRITANNIA",
    "EICHERMOT", "HEROMOTOCO", "APOLLOHOSP", "TATACONSUM", "SBILIFE",
    "BAJAJ-AUTO", "INDUSINDBK", "UPL", "HINDALCO", "SHREECEM",
]

# ── In-memory signal store (latest signals) ──
_signals: dict[str, dict] = {}
_signal_history: list[dict] = []

# ── Auto-trade settings ──
_auto_trade_enabled: bool = False
_auto_trade_config = {
    "min_confidence": 82,    # ← unified with auto_trader default (was 75 — too loose)
    "min_risk_reward": 1.8,  # ← explicit (was missing, auto_trader default silently applied)
    "max_daily_loss": 15000,
    "max_position_size": 50000,
    "max_positions": 3,      # ← matches auto_trader default (was 6 — over-concentrated)
    "capital": 1_000_000,
    "max_risk_per_trade_pct": 2.0,
}

# ── News sentiment store ──
_news_sentiments: list[dict] = []


async def restore_state() -> None:
    """Reload signals + positions from DB after a restart."""
    try:
        from ..services.state_store import load_state

        saved = await load_state("signals")
        if saved:
            _signals.update(saved.get("latest", {}))
            _signal_history.extend(saved.get("history", []))
            logger.info("Signals restored", count=len(_signals))

        from .position_manager import position_manager
        await position_manager.restore()
    except Exception as e:
        logger.warning("Scheduler state restore failed", error=str(e))


def get_signals() -> dict[str, dict]:
    """Get latest signals for all monitored symbols."""
    return _signals.copy()


def get_signal_history() -> list[dict]:
    """Get signal history."""
    return _signal_history[:100]


def get_news_sentiments() -> list[dict]:
    """Get recent news with sentiment scores."""
    return _news_sentiments[:50]


# ═══════════════════════════════════════════════════════════════
# JOB 1: Market Scan — runs every 5 min during market hours
# ═══════════════════════════════════════════════════════════════

async def job_market_scan() -> None:
    """Scan NIFTY 50 stocks for price movements and anomalies."""
    if not is_market_hours():
        return

    try:
        from ..services.market_data_service import get_market_data_provider  # type: ignore

        provider = get_market_data_provider()
        scan_results = []

        # Scan in batches of 10 to avoid rate limiting
        for i in range(0, min(10, len(NIFTY_50_SYMBOLS)), 5):
            batch = NIFTY_50_SYMBOLS[i:i + 5]
            for symbol in batch:
                try:
                    quote = await provider.get_quote(symbol)
                    if abs(quote.change_pct) > 2.0:
                        direction = "🟢 SURGE" if quote.change_pct > 0 else "🔴 DROP"
                        push_feed(
                            "SCAN",
                            f"{direction} · {symbol} {quote.change_pct:+.2f}% at ₹{quote.price}",
                            {"symbol": symbol, "price": float(quote.price), "change_pct": quote.change_pct},
                        )
                        scan_results.append(symbol)
                except Exception as e:
                    logger.debug("Scan skip", symbol=symbol, error=str(e))

        logger.info("Market scan complete", scanned=min(10, len(NIFTY_50_SYMBOLS)), alerts=len(scan_results))

    except Exception as e:
        logger.error("Market scan failed", error=str(e))
        push_feed("ERROR", f"Market scan failed: {e}")


# ═══════════════════════════════════════════════════════════════
# JOB 2: News Ingestion + FinBERT Scoring — every 15 min
# ═══════════════════════════════════════════════════════════════

async def job_ingest_news() -> None:
    """Fetch latest news and score with FinBERT sentiment analysis."""
    try:
        from ..services.news_service import get_news_provider  # type: ignore

        provider = get_news_provider()
        news_items = await provider.fetch_news(query="India stock market NSE NIFTY", limit=15)

        if not news_items:
            logger.info("No new news items found")
            return

        # Try FinBERT, fall back to keyword sentiment
        scored_items = []
        try:
            from ..nlp.finbert import get_finbert  # type: ignore

            analyzer = get_finbert()
            news_dicts = [{"title": n.title, "summary": n.summary} for n in news_items]
            enriched = await analyzer.analyze_news_items(news_dicts)

            for item, enriched_item in zip(news_items, enriched):
                sentiment = enriched_item.get("sentiment", {})
                scored_items.append({
                    "title": item.title,
                    "source": item.source,
                    "url": item.url,
                    "published": item.published.isoformat(),
                    "sentiment_label": sentiment.get("label", "neutral"),
                    "sentiment_score": sentiment.get("score", 0.5),
                    "positive": sentiment.get("positive", 0.33),
                    "negative": sentiment.get("negative", 0.33),
                    "neutral": sentiment.get("neutral", 0.34),
                })

        except Exception as e:
            logger.warning("FinBERT unavailable, using basic scoring", error=str(e))
            for item in news_items:
                scored_items.append({
                    "title": item.title,
                    "source": item.source,
                    "url": item.url,
                    "published": item.published.isoformat(),
                    "sentiment_label": "neutral",
                    "sentiment_score": 0.5,
                })

        # Store in memory
        _news_sentiments.clear()
        _news_sentiments.extend(scored_items)

        # Push notable news to feed
        for item in scored_items[:3]:
            label = item["sentiment_label"]
            icon = "🟢" if label == "positive" else "🔴" if label == "negative" else "🟡"
            push_feed(
                "NEWS",
                f"{icon} {item['title'][:100]}",
                {"source": item["source"], "sentiment": label, "score": item["sentiment_score"]},
            )

        logger.info("News ingested", articles=len(scored_items),
                     positive=sum(1 for i in scored_items if i["sentiment_label"] == "positive"),
                     negative=sum(1 for i in scored_items if i["sentiment_label"] == "negative"))

    except Exception as e:
        logger.error("News ingestion failed", error=str(e))
        push_feed("ERROR", f"News ingestion failed: {e}")


# ═══════════════════════════════════════════════════════════════
# JOB 3: Signal Generation — every 10 min during market hours
# ═══════════════════════════════════════════════════════════════

async def job_generate_signals() -> None:
    """Run the multi-agent research pipeline on key stocks."""
    if not is_market_hours():
        return

    try:
        from ..agents.orchestrator import run_research_pipeline  # type: ignore

        # Analyze a rotating subset of stocks (5 per cycle to avoid rate limits)
        cycle_index = int(datetime.now(IST).timestamp()) % (len(NIFTY_50_SYMBOLS) // 5)
        batch = NIFTY_50_SYMBOLS[cycle_index * 5:(cycle_index + 1) * 5]

        for symbol in batch:
            try:
                signal = await run_research_pipeline(symbol)
                signal_dict = signal.to_dict()
                _signals[symbol] = signal_dict

                # Record history
                _signal_history.insert(0, signal_dict)
                if len(_signal_history) > 500:
                    _signal_history.pop()

                # Push high-confidence signals to feed
                if signal.confidence > 70 and signal.action != "HOLD":
                    emoji = "📈" if signal.action == "BUY" else "📉"
                    push_feed(
                        "SIGNAL",
                        f"{emoji} {signal.action} · {symbol} · Confidence {signal.confidence:.0f}% · "
                        f"Target ₹{signal.target_price:,.0f} · SL ₹{signal.stop_loss:,.0f}",
                        signal_dict,
                    )

                    # Track signal for outcome measurement
                    try:
                        from ..agents.outcome_tracker import outcome_tracker
                        outcome_tracker.record_signal(
                            symbol=symbol,
                            action=signal.action,
                            entry_price=signal.entry_price,
                            target_price=signal.target_price,
                            stop_loss=signal.stop_loss,
                            agent_signals={
                                r.get("agent", ""): {"signal": r.get("signal"), "confidence": r.get("confidence")}
                                for r in signal.agent_results
                            },
                        )
                    except Exception:
                        pass

            except Exception as e:
                logger.error("Signal generation failed", symbol=symbol, error=str(e))

        logger.info("Signals generated", batch=batch, total_signals=len(_signals))

        # Mirror to DB so signals survive restarts
        from ..services.state_store import save_state
        await save_state("signals", {"latest": _signals, "history": _signal_history[:200]})

    except Exception as e:
        logger.error("Signal generation job failed", error=str(e))
        push_feed("ERROR", f"Signal generation failed: {e}")


# ═══════════════════════════════════════════════════════════════
# JOB 4: Auto-Trade Check — every 5 min during market hours
# ═══════════════════════════════════════════════════════════════

async def job_auto_trade_check() -> None:
    """Check signals and auto-execute trades when criteria met."""
    if not is_market_hours() or not _auto_trade_enabled:
        return

    try:
        from .auto_trader import execute_auto_trades  # type: ignore
        await execute_auto_trades(_signals, _auto_trade_config)
    except ImportError:
        logger.debug("Auto-trader module not yet available")
    except Exception as e:
        logger.error("Auto-trade check failed", error=str(e))
        push_feed("ERROR", f"Auto-trade check failed: {e}")


# ═══════════════════════════════════════════════════════════════
# JOB 5: Daily Email Report — 3:35 PM IST (after market close)
# ═══════════════════════════════════════════════════════════════

async def job_daily_email_report() -> None:
    """Send end-of-day P&L summary via email."""
    try:
        from ..services.email_service import send_daily_summary, is_configured  # type: ignore
        from .auto_trader import get_daily_trades, get_daily_pnl  # type: ignore

        if not is_configured():
            logger.debug("Email not configured — skipping daily report")
            return

        trades = get_daily_trades()
        total_pnl = get_daily_pnl()
        win_count = sum(1 for t in trades if t.get("pnl", 0) > 0)
        win_rate = (win_count / len(trades) * 100) if trades else 0.0

        await send_daily_summary(
            total_pnl=total_pnl,
            win_rate=win_rate,
            trade_count=len(trades),
            positions=trades,
        )

        push_feed("SYSTEM", f"📧 Daily P&L report emailed (₹{total_pnl:,.2f})")
        logger.info("Daily email sent", pnl=total_pnl, trades=len(trades))

    except Exception as e:
        logger.error("Daily email report failed", error=str(e))


# ═══════════════════════════════════════════════════════════════
# JOB 6: Weekly Digest — Saturday 10 AM IST
# ═══════════════════════════════════════════════════════════════

async def job_weekly_digest() -> None:
    """Send weekly market digest via email."""
    try:
        from ..services.email_service import send_weekly_digest, is_configured  # type: ignore

        if not is_configured():
            logger.debug("Email not configured — skipping weekly digest")
            return

        # Aggregate from signal history
        history = _signal_history[:200]
        total_trades = len(history)
        best = max(history, key=lambda x: x.get("pnl", 0), default={"symbol": "—", "pnl": 0})
        worst = min(history, key=lambda x: x.get("pnl", 0), default={"symbol": "—", "pnl": 0})
        weekly_pnl = sum(h.get("pnl", 0) for h in history)

        await send_weekly_digest(
            weekly_pnl=weekly_pnl,
            best_trade=best,
            worst_trade=worst,
            total_trades=total_trades,
        )

        push_feed("SYSTEM", f"📈 Weekly digest emailed (₹{weekly_pnl:,.2f})")
        logger.info("Weekly digest sent", pnl=weekly_pnl)

    except Exception as e:
        logger.error("Weekly digest failed", error=str(e))


# ═══════════════════════════════════════════════════════════════
# JOB 7: Position Manager — check exits every minute
# ═══════════════════════════════════════════════════════════════

async def job_check_position_exits() -> None:
    """Check open positions for target/SL/trailing stop exits."""
    if not is_market_hours():
        return

    try:
        from .position_manager import position_manager
        from ..services.market_data_service import get_market_data_provider

        open_pos = position_manager.get_open_positions()
        if not open_pos:
            return

        # Fetch current prices for all open positions
        provider = get_market_data_provider()
        symbols = list(set(p["symbol"] for p in open_pos))
        current_prices = {}
        for sym in symbols:
            try:
                quote = await provider.get_quote(sym)
                current_prices[sym] = float(quote.price)
            except Exception:
                pass

        if current_prices:
            closed = position_manager.check_exits(current_prices)
            if closed:
                total_pnl = sum(p.get("pnl", 0) for p in closed)
                push_feed(
                    "POSITION",
                    f"Closed {len(closed)} positions | Net P&L: Rs {total_pnl:,.0f}",
                )

            # Also check outcome tracker for signal accuracy
            try:
                from ..agents.outcome_tracker import outcome_tracker
                outcome_tracker.check_outcomes(current_prices)
            except Exception:
                pass

    except Exception as e:
        logger.error("Position exit check failed", error=str(e))


# ═══════════════════════════════════════════════════════════════
# JOB 8: Broker Sync — pull live positions/funds from connected
# brokers (Angel One etc.) every 2 min during market hours
# ═══════════════════════════════════════════════════════════════

# Latest broker snapshots, keyed by "<user_id>:<broker>"
_broker_snapshots: dict[str, dict] = {}


def get_broker_snapshots() -> dict[str, dict]:
    """Latest synced broker portfolio data (positions/funds per session)."""
    return _broker_snapshots.copy()


async def job_sync_broker_positions() -> None:
    """Sync live positions, holdings and funds from all connected brokers.

    This is what makes the agent actively monitor Angel One — without it,
    broker data only refreshes while a user has the Live Monitor page open.
    """
    if not is_market_hours():
        return

    try:
        from ..routers.broker import get_active_sessions  # type: ignore

        sessions = get_active_sessions()
        if not sessions:
            return

        for key, broker in list(sessions.items()):
            try:
                positions = await broker.get_positions()
                funds = await broker.get_funds()

                pos_dicts = [vars(p) for p in positions]
                total_pnl = sum(p.get("pnl", 0) for p in pos_dicts)

                prev = _broker_snapshots.get(key, {})
                _broker_snapshots[key] = {
                    "positions": pos_dicts,
                    "funds": funds,
                    "total_pnl": round(total_pnl, 2),
                    "synced_at": datetime.now(IST).isoformat(),
                }

                # Alert on meaningful P&L swing since last sync (> ₹1,000)
                prev_pnl = prev.get("total_pnl", total_pnl)
                if abs(total_pnl - prev_pnl) > 1000:
                    arrow = "📈" if total_pnl > prev_pnl else "📉"
                    push_feed(
                        "BROKER",
                        f"{arrow} Live P&L moved ₹{prev_pnl:,.0f} → ₹{total_pnl:,.0f} "
                        f"({len(pos_dicts)} open positions)",
                        {"pnl": total_pnl, "positions": len(pos_dicts)},
                    )
            except Exception as e:
                logger.warning("Broker sync failed for session", session=key, error=str(e))

        logger.info("Broker sync complete", sessions=len(sessions))

    except Exception as e:
        logger.error("Broker sync job failed", error=str(e))


# ── Control functions ──

def set_auto_trade(enabled: bool) -> None:
    """Enable or disable auto-trading."""
    global _auto_trade_enabled
    _auto_trade_enabled = enabled
    status = "ENABLED" if enabled else "DISABLED"
    push_feed("SYSTEM", f"🤖 Auto-trading {status}")


def get_auto_trade_config() -> dict:
    """Get current auto-trade configuration."""
    return {
        "enabled": _auto_trade_enabled,
        **_auto_trade_config,
    }
