import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta, date
from sqlalchemy.future import select

from app.users.models import User, UserRole
from app.subscriptions.models import Subscription, Plan, PlanStrategyAccess
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyEntrySetting, StrategyEntryDay, StrategyExitSetting
from app.execution.models import StrategySignal, StrategyExecutionBatch, StrategyUserExecutionTrace, StrategyExecutionTraceEvent
from app.brokers.models import DhanBrokerSession
from app.execution.service import execute_signal_batch
from app.auth.service import hash_password

@pytest.mark.asyncio
async def test_full_signal_batch_execution_pipeline(db_session, seed_plans):
    free_plan, premium_plan = seed_plans

    # 1. Setup 3 Users
    user1 = User(email="user1@example.com", password_hash=hash_password("pass"), role=UserRole.TRADER, is_active=True, referral_code="REF-USR001")
    user2 = User(email="user2@example.com", password_hash=hash_password("pass"), role=UserRole.TRADER, is_active=True, referral_code="REF-USR002")
    user3 = User(email="user3@example.com", password_hash=hash_password("pass"), role=UserRole.TRADER, is_active=True, referral_code="REF-USR003")
    db_session.add_all([user1, user2, user3])
    await db_session.flush()

    # 2. Setup Subscriptions on Premium Plan
    now = datetime.now(timezone.utc)
    sub1 = Subscription(user_id=user1.id, plan_id=premium_plan.id, status="ACTIVE", start_at=now, current_period_start=now, current_period_end=now + timedelta(days=30))
    sub2 = Subscription(user_id=user2.id, plan_id=premium_plan.id, status="ACTIVE", start_at=now, current_period_start=now, current_period_end=now + timedelta(days=30))
    sub3 = Subscription(user_id=user3.id, plan_id=premium_plan.id, status="ACTIVE", start_at=now, current_period_start=now, current_period_end=now + timedelta(days=30))
    db_session.add_all([sub1, sub2, sub3])
    await db_session.flush()

    # 3. Setup Broker Sessions
    # User 1: Active Valid Session
    session1 = DhanBrokerSession(
        user_id=user1.id,
        dhan_client_id="CLIENT1",
        access_token="token1",
        status="ACTIVE",
        expiry_time=now + timedelta(hours=5),
        broker_name="DHAN"
    )
    # User 2: Expired Session
    session2 = DhanBrokerSession(
        user_id=user2.id,
        dhan_client_id="CLIENT2",
        access_token="token2",
        status="ACTIVE",
        expiry_time=now - timedelta(minutes=1),
        broker_name="DHAN"
    )
    # User 3: Missing Session -> Not seeded in table
    db_session.add_all([session1, session2])
    await db_session.flush()

    # 4. Setup Strategy & Version Config
    strategy = Strategy(user_id=user1.id, name="Test Integration Strategy", status="ACTIVE_LIVE", mode="PAPER")
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("10000.00"))
    db_session.add(version)
    await db_session.flush()

    strategy.current_version_id = version.id
    db_session.add(strategy)

    # Leg
    leg = StrategyLeg(
        strategy_version_id=version.id,
        sequence=1,
        segment="OPT",
        side="BUY",
        strike_selection="ATM",
        expiry="WEEKLY",
        lots=1
    )
    db_session.add(leg)

    entry_setting = StrategyEntrySetting(strategy_version_id=version.id, entry_time="09:30")
    db_session.add(entry_setting)

    entry_day = StrategyEntryDay(strategy_version_id=version.id, day_of_week="MONDAY")
    db_session.add(entry_day)

    exit_setting = StrategyExitSetting(strategy_version_id=version.id, exit_time="15:15")
    db_session.add(exit_setting)
    await db_session.flush()

    # 5. Map Strategy to Premium Plan
    access = PlanStrategyAccess(plan_id=premium_plan.id, strategy_id=strategy.id, is_enabled=True)
    db_session.add(access)
    await db_session.flush()

    # 6. Create Signal trigger
    signal = StrategySignal(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        trading_date=date.today(),
        entry_time="09:30"
    )
    db_session.add(signal)
    await db_session.commit() # commit all setup data

    # 7. Run Batch Execution!
    await execute_signal_batch(signal.id)

    # 8. Assertions
    # Fetch batch record
    stmt_batch = select(StrategyExecutionBatch).where(StrategyExecutionBatch.signal_id == signal.id)
    res_batch = await db_session.execute(stmt_batch)
    batch = res_batch.scalar_one()

    assert batch.total_users == 3
    assert batch.eligible_users == 1
    assert batch.rejected_users == 2
    assert batch.successful_users == 1
    assert batch.failed_users == 0
    assert batch.not_executed_users == 2
    assert batch.status == "COMPLETED"

    # User 1 Trace: EXECUTED
    stmt_t1 = select(StrategyUserExecutionTrace).where(StrategyUserExecutionTrace.execution_batch_id == batch.id, StrategyUserExecutionTrace.user_id == user1.id)
    res_t1 = await db_session.execute(stmt_t1)
    t1 = res_t1.scalar_one()
    assert t1.status == "EXECUTED"
    assert t1.current_step == "ORDER_FILLED"

    # User 1 timeline verification
    stmt_ev1 = select(StrategyExecutionTraceEvent).where(StrategyExecutionTraceEvent.execution_trace_id == t1.id).order_by(StrategyExecutionTraceEvent.id.asc())
    res_ev1 = await db_session.execute(stmt_ev1)
    events1 = res_ev1.scalars().all()
    steps1 = [e.step for e in events1]
    assert "INIT" in steps1
    assert "USER_CHECK" in steps1
    assert "SUBSCRIPTION_CHECK" in steps1
    assert "QUOTA_RESERVATION" in steps1
    assert "BROKER_SESSION_CHECK" in steps1
    assert "ORDER_PLACED" in steps1

    # User 2 Trace: EXPIRED
    stmt_t2 = select(StrategyUserExecutionTrace).where(StrategyUserExecutionTrace.execution_batch_id == batch.id, StrategyUserExecutionTrace.user_id == user2.id)
    res_t2 = await db_session.execute(stmt_t2)
    t2 = res_t2.scalar_one()
    assert t2.status == "BROKER_SESSION_INVALID"
    assert t2.failure_code == "DHAN_SESSION_EXPIRED"

    # User 3 Trace: MISSING
    stmt_t3 = select(StrategyUserExecutionTrace).where(StrategyUserExecutionTrace.execution_batch_id == batch.id, StrategyUserExecutionTrace.user_id == user3.id)
    res_t3 = await db_session.execute(stmt_t3)
    t3 = res_t3.scalar_one()
    assert t3.status == "BROKER_SESSION_INVALID"
    assert t3.failure_code == "DHAN_SESSION_NOT_FOUND"
