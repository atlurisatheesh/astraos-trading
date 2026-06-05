"""AstraOS — Alembic Migration Configuration."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

import os
import sys

# Add the project root so we can import our models
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.database import Base
from src.models.user import User
from src.models.instrument import Instrument
from src.models.trading import (
    Order, Position, Strategy, Signal, Watchlist, AuditLog, RiskEvent, KillSwitchState,
    PortfolioSnapshot, NewsArchive, Alert, UserSettings, TradeJournal,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return os.getenv("DATABASE_URL_SYNC", "postgresql://astraos:astraos_dev@localhost:5432/astraos")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    from sqlalchemy import create_engine

    url = get_url().replace("+asyncpg", "")
    connectable = create_engine(url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
