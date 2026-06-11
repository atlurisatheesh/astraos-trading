"""AstraOS API — Main FastAPI Application Entry Point."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.exceptions import AstraOSError, astraos_exception_handler

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    settings = get_settings()
    logger.info(
        "AstraOS starting",
        env=settings.app_env,
        market_data=settings.market_data_provider,
        broker=settings.broker_provider,
        llm=settings.llm_provider,
    )


    # Ensure all tables exist on startup (works for both SQLite and PostgreSQL)
    try:
        from .core.database import engine, Base
        # Import models to populate Base.metadata — must happen before create_all
        from .models.user import User  # noqa: F401
        from .models.instrument import Instrument  # noqa: F401
        from .models.broker import BrokerCredential  # noqa: F401
        from .models.trading import (  # noqa: F401
            Alert, AuditLog, KillSwitchState, NewsArchive, Order,
            PortfolioSnapshot, Position, RiskEvent, Signal, Strategy,
            TradeJournal, UserSettings, Watchlist,
        )
        tables_before = set(Base.metadata.tables.keys())
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        tables_after = set(Base.metadata.tables.keys())
        logger.info("Database tables ensured", tables=sorted(tables_after))
    except Exception as e:
        import traceback
        logger.error("DB create_all FAILED", error=str(e), trace=traceback.format_exc()[-500:])

    # Start the continuous monitoring scheduler
    try:
        from .scheduler.engine import start_scheduler
        await start_scheduler()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.warning("Scheduler failed to start — API continues without scheduler", error=str(e))

    yield

    # Stop scheduler on shutdown
    try:
        from .scheduler.engine import stop_scheduler
        await stop_scheduler()
    except Exception:
        pass

    logger.info("AstraOS shutting down")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title="AstraOS API",
        description="AI-native stock trading intelligence platform",
        version="0.2.0",
        docs_url="/docs" if settings.app_debug else None,
        redoc_url="/redoc" if settings.app_debug else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate Limiting
    from .core.rate_limiter import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, requests_per_minute=120, burst=30)

    # Security Headers + HTTPS enforcement
    from .core.security_middleware import SecurityHeadersMiddleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Exception handlers
    app.add_exception_handler(AstraOSError, astraos_exception_handler)

    # Debug: catch-all handler to surface actual errors (remove after fix)
    from fastapi import Request
    from fastapi.responses import JSONResponse
    import traceback as tb

    @app.exception_handler(Exception)
    async def debug_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "type": type(exc).__name__,
                     "trace": tb.format_exc()[-1000:]},
        )

    # Routers
    from .routers import auth, watchlists, signals, orders, positions
    from .routers import market, news, backtest, research, websocket as ws_router
    from .routers import sentiment, exchange, broker, knowledge, rag_router
    from .routers import scheduler_router, ml_router
    from .routers import fundamentals, screener, derivatives
    from .routers import portfolio, alerts as alerts_router, journal, settings as settings_router
    from .routers import risk as risk_router
    from .routers import advanced as advanced_router
    from .routers import pro as pro_router

    app.include_router(auth.router)
    app.include_router(watchlists.router)
    app.include_router(signals.router)
    app.include_router(orders.router)
    app.include_router(positions.router)
    app.include_router(market.router)
    app.include_router(news.router)
    app.include_router(backtest.router)
    app.include_router(research.router)
    app.include_router(ws_router.router)
    app.include_router(sentiment.router)
    app.include_router(exchange.router)
    app.include_router(broker.router)
    app.include_router(knowledge.router)
    app.include_router(rag_router.router)
    app.include_router(scheduler_router.router)
    app.include_router(ml_router.router)
    app.include_router(fundamentals.router)
    app.include_router(screener.router)
    app.include_router(derivatives.router)
    app.include_router(portfolio.router)
    app.include_router(alerts_router.router)
    app.include_router(journal.router)
    app.include_router(settings_router.router)
    app.include_router(risk_router.router)
    app.include_router(advanced_router.router)
    app.include_router(pro_router.router)

    @app.get("/debug/db", tags=["Debug"])
    async def debug_db():
        from .core.database import engine, Base
        from sqlalchemy import text
        tables_in_metadata = sorted(Base.metadata.tables.keys())
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables_in_db = [row[0] for row in result]
        except Exception as e:
            tables_in_db = [f"ERROR: {e}"]
        return {
            "db_url": str(engine.url),
            "metadata_tables": tables_in_metadata,
            "db_tables": tables_in_db,
        }

    @app.post("/debug/init-db", tags=["Debug"])
    async def debug_init_db():
        import traceback as tb
        from .core.database import engine, Base
        from .models.user import User  # noqa
        from .models.instrument import Instrument  # noqa
        from .models.broker import BrokerCredential  # noqa
        from .models.trading import (  # noqa
            Alert, AuditLog, KillSwitchState, NewsArchive, Order,
            PortfolioSnapshot, Position, RiskEvent, Signal, Strategy,
            TradeJournal, UserSettings, Watchlist,
        )
        from sqlalchemy import text
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = [row[0] for row in result]
            return {"status": "ok", "tables_created": sorted(tables)}
        except Exception as e:
            return {"status": "error", "error": str(e), "trace": tb.format_exc()}

    @app.get("/health", tags=["Health"])
    async def health_check():
        # Include scheduler status in health check
        scheduler_status = "unknown"
        try:
            from .scheduler.engine import get_scheduler_status
            sched = get_scheduler_status()
            scheduler_status = sched.get("status", "unknown")
        except Exception:
            pass

        return {
            "status": "healthy",
            "service": "AstraOS API",
            "version": "0.2.0",
            "env": settings.app_env,
            "providers": {
                "market_data": settings.market_data_provider,
                "broker": settings.broker_provider,
                "llm": settings.llm_provider,
            },
            "scheduler": scheduler_status,
        }

    return app


app = create_app()

