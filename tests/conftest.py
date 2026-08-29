import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, delete
from decimal import Decimal
from sqlalchemy.pool import NullPool

# Import all SQLAlchemy models to register them in Base.metadata
import app.users.models
import app.wallets.models
import app.subscriptions.models
import app.strategies.models
import app.execution.models
import app.brokers.models

from app.main import app as fastapi_app
from app.core.config import settings
from app.core.database import Base, get_db
from app.subscriptions.models import Plan
from app.users.models import User, UserRole
from app.auth.service import hash_password

# Use settings.DATABASE_URL with NullPool to prevent event loop mismatch errors
test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Override the application database configuration globally for test isolation
import app.core.database
app.core.database.engine = test_engine
app.core.database.AsyncSessionLocal = TestAsyncSessionLocal

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True, scope="function")
async def clean_db():
    """Ensures tables exist and cleans up database tables in topological order before each test run."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(delete(table))
    yield
    # Cleanup after test
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(delete(table))

@pytest.fixture(scope="function")
async def db_session():
    """Yields clean db session for raw inserts and queries during assertions."""
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

@pytest.fixture(scope="function")
async def client(db_session):
    """Configures HTTPX AsyncClient using ASGITransport."""
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def test_user(db_session):
    """Creates a standard test user."""
    user = User(
        email="testuser@example.com",
        password_hash=hash_password("Password123!"),
        role=UserRole.USER,
        is_active=True,
        referral_code="REF-TESTUSER"
    )
    db_session.add(user)
    await db_session.flush()
    return user

@pytest.fixture(scope="function")
async def seed_plans(db_session):
    """Seeds standard FREE and PREMIUM plans for subscription testing."""
    free_plan = Plan(
        code="FREE",
        name="Free Trial Plan",
        monthly_price=Decimal("0.00"),
        gst_percentage=Decimal("18.00"),
        min_wallet_balance=Decimal("0.00"),
        max_active_strategies=1,
        max_strategy_executions_per_day=1,
        subscription_type="MONTHLY",
        is_active=True
    )
    premium_plan = Plan(
        code="PREMIUM",
        name="Premium Trading Plan",
        monthly_price=Decimal("999.00"),
        gst_percentage=Decimal("18.00"),
        min_wallet_balance=Decimal("500.00"),
        max_active_strategies=10,
        max_strategy_executions_per_day=3,
        subscription_type="MONTHLY",
        is_active=True
    )
    db_session.add_all([free_plan, premium_plan])
    await db_session.flush()
    return free_plan, premium_plan
