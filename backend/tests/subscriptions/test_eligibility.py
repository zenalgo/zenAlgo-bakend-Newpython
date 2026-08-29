import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, date

from app.users.models import User, UserRole
from app.subscriptions.models import Subscription, Plan, UserDailyStrategyUsage
from app.strategies.models import Strategy, StrategyVersion
from app.subscriptions.service_eligibility import reserve_strategy_execution
from app.auth.service import hash_password

@pytest.fixture
async def setup_trader_and_strategy(db_session, seed_plans):
    free_plan, premium_plan = seed_plans

    # 1. Create active trader
    trader = User(
        email="trader@example.com",
        password_hash=hash_password("traderpass123"),
        role=UserRole.TRADER,
        is_active=True,
        referral_code="REF-TRA555"
    )
    db_session.add(trader)
    await db_session.flush()

    # 2. Assign Premium Subscription
    now = datetime.now()
    sub = Subscription(
        user_id=trader.id,
        plan_id=premium_plan.id,
        status="ACTIVE",
        start_at=now,
        current_period_start=now,
        current_period_end=now + datetime.resolution * 30 # standard far date
    )
    db_session.add(sub)
    await db_session.flush()

    # 3. Create Strategy
    strategy = Strategy(
        user_id=trader.id,
        name="Concurrent Test Strategy",
        status="ACTIVE_LIVE",
        mode="PAPER"
    )
    db_session.add(strategy)
    await db_session.flush()

    # 4. Create Strategy Version
    version = StrategyVersion(
        strategy_id=strategy.id,
        version_number=1,
        underlying="NIFTY",
        capital=Decimal("100000")
    )
    db_session.add(version)
    await db_session.flush()

    # Set as current version
    strategy.current_version_id = version.id
    db_session.add(strategy)

    # 5. Map Strategy to Premium Plan
    from app.subscriptions.models import PlanStrategyAccess
    access = PlanStrategyAccess(
        plan_id=premium_plan.id,
        strategy_id=strategy.id,
        is_enabled=True
    )
    db_session.add(access)
    await db_session.commit()

    return trader, strategy, premium_plan

@pytest.mark.asyncio
async def test_concurrent_quota_reservation_limits(setup_trader_and_strategy):
    trader, strategy, premium_plan = setup_trader_and_strategy
    
    # Premium plan limit is 3 strategy executions per day
    limit = premium_plan.max_strategy_executions_per_day
    assert limit == 3

    # Define a helper task to spawn independent connection and session scopes
    from app.core.database import AsyncSessionLocal
    async def run_reservation():
        async with AsyncSessionLocal() as session:
            try:
                res = await reserve_strategy_execution(session, trader.id, strategy.id, date.today())
                await session.commit()
                return res
            except Exception as e:
                await session.rollback()
                raise e

    #Concurrently fire 5 requests
    tasks = [run_reservation() for _ in range(5)]
    results = await asyncio.gather(*tasks)

    # Count success vs failures
    success_count = sum(1 for r in results if r.reserved is True)
    fail_count = sum(1 for r in results if r.reserved is False and r.reason == "DAILY_LIMIT_REACHED")

    assert success_count == 3
    assert fail_count == 2
