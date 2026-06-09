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


    # Run database migrations on startup (production)
    if settings.app_env == "production":
        try:
            import subprocess, sys, os
            result = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                capture_output=True, text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            if result.returncode == 0:
                logger.info("Database migrations applied successfully")
            else:
                logger.warning("Migration note", stdout=result.stdout[-200:], stderr=result.stderr[-200:])
        except Exception as e:
            logger.warning("Migration skipped", error=str(e))

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

