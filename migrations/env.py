import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# Load settings and base model
from app.core.config import settings
from app.core.database import Base

# Import all models to register them on Base.metadata for autogenerate
from app.users.models import User
from app.wallets.models import Wallet, WalletTransaction
from app.subscriptions.models import Plan, PlanFeature, PlanStrategyAccess, Subscription, SubscriptionEvent, UserDailyStrategyUsage, SubscriptionPayment
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyEntrySetting, StrategyEntryDay, StrategyExitSetting, StrategyExecution, StrategyExecutionLeg
from app.execution.models import StrategySignal, StrategyExecutionBatch, StrategyUserExecutionTrace, StrategyExecutionTraceEvent
from app.brokers.models import DhanBrokerSession, UserHolding, UserPosition, UserOrder, UserTrade, UserFundSnapshot

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using AsyncEngine."""
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
