import inspect
import pathlib
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy import inspect as sa_inspect
from app.core.database import Base
import app.main

versions_dir = pathlib.Path(__file__).parent.parent / "migrations" / "versions"


@pytest.mark.asyncio
async def test_startup_does_not_call_create_all():
    """Verify application on_startup does NOT invoke Base.metadata.create_all."""
    # Statically verify that create_all is not in on_startup source code
    source = inspect.getsource(app.main.on_startup)
    assert "create_all" not in source, "app.main.on_startup must not call create_all"

    # Verify dynamically with mocks
    with patch("app.core.database.Base.metadata.create_all") as mock_create_all, \
         patch.object(app.main.redis_manager, "init_redis", new_callable=AsyncMock), \
         patch.object(app.main.order_reconciliation_worker, "start", new_callable=AsyncMock), \
         patch.object(app.main, "seed_instruments_if_empty", new_callable=AsyncMock):
        
        await app.main.on_startup()
        mock_create_all.assert_not_called()


def test_initial_migration_source_does_not_contain_create_all():
    """Verify initial schema migration does not fall back to Base.metadata.create_all."""
    initial_path = versions_dir / "f0ee417c76c7_initial_schema_migration.py"
    source = initial_path.read_text()
    assert "create_all" not in source, (
        "f0ee417c76c7_initial_schema_migration.py must not contain 'create_all' calls"
    )


def test_rules_migration_unconditional_table_creation():
    """Verify 022b1c175d14 creates strategy_conditions and strategy_golden_rules unconditionally."""
    rules_path = versions_dir / "022b1c175d14_add_rules_and_golden_rules_tables.py"
    source = rules_path.read_text()
    assert "op.create_table('strategy_conditions'" in source or "create_table('strategy_conditions'" in source
    assert "op.create_table('strategy_golden_rules'" in source or "create_table('strategy_golden_rules'" in source
    assert "IF NOT EXISTS" not in source, "Workaround 'IF NOT EXISTS' must not be used in 022b1c175d14"


@pytest.mark.asyncio
async def test_all_model_tables_exist_in_db():
    """Verify all tables defined in SQLAlchemy Base.metadata exist in the database."""
    from app.core.database import engine
    import app.users.models
    import app.wallets.models
    import app.subscriptions.models
    import app.strategies.models
    import app.execution.models
    import app.brokers.models
    import app.core.settings_model
    import app.instruments.models

    async with engine.connect() as conn:
        db_tables = await conn.run_sync(lambda sync_conn: sa_inspect(sync_conn).get_table_names())
        model_tables = set(Base.metadata.tables.keys())
        missing_tables = model_tables - set(db_tables)
        assert not missing_tables, f"Database missing tables required by models: {missing_tables}"
