import pytest
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import TestAsyncSessionLocal
from app.strategies.models import Strategy, StrategyVersion, StrategyRuntimeState, StrategyEventProcessing
from app.strategies.enums import StrategyLifecycleState
from app.strategies.state_manager import StrategyStateManager
from app.core.exceptions import ResourceNotFoundError, ValidationError
from sqlalchemy.exc import IntegrityError

@pytest.fixture(scope="function")
async def seed_strategy_and_version(db_session: AsyncSession):
    """Seeds a test strategy and version for state manager testing."""
    # Retrieve or create plan
    from app.subscriptions.models import Plan
    res = await db_session.execute(select(Plan))
    plan = res.scalars().first()
    if not plan:
        plan = Plan(
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
        db_session.add(plan)
        await db_session.flush()

    # Retrieve or create user
    from app.users.models import User
    res_user = await db_session.execute(select(User).where(User.email == "test@example.com"))
    user = res_user.scalar_one_or_none()
    if not user:
        user = User(
            email="test@example.com",
            password_hash="hashedpass",
            first_name="Test",
            last_name="User",
            role="USER",
            referral_code="REF-TEST",
            is_active=True
        )
        db_session.add(user)
        await db_session.flush()

    strategy = Strategy(
        user_id=user.id,
        name="Test State Strategy",
        strategy_type="CUSTOM_MULTI_LEG",
        status="DRAFT",
        is_active=True,
        mode="PAPER"
    )
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(
        strategy_id=strategy.id,
        version_number=1,
        underlying="NIFTY",
        capital=Decimal("100000.00"),
        trading_type="INTRADAY"
    )
    db_session.add(version)
    await db_session.flush()

    strategy.current_version_id = version.id
    db_session.add(strategy)
    await db_session.flush()
    await db_session.commit()

    return strategy, version

@pytest.mark.asyncio
async def test_initialize_runtime_state_creates_waiting_state(db_session: AsyncSession, seed_strategy_and_version):
    strategy, version = seed_strategy_and_version

    # Initialize state
    state = await StrategyStateManager.initialize_runtime_state(db_session, strategy.id, version.id)
    assert state.strategy_id == strategy.id
    assert state.strategy_version_id == version.id
    assert state.lifecycle_state == StrategyLifecycleState.WAITING

    # Verify database row physically exists
    res = await db_session.execute(select(StrategyRuntimeState).where(StrategyRuntimeState.strategy_id == strategy.id))
    db_row = res.scalar_one()
    assert db_row.id == state.id

@pytest.mark.asyncio
async def test_initialize_runtime_state_rejects_missing_strategy(db_session: AsyncSession):
    with pytest.raises(ResourceNotFoundError):
        await StrategyStateManager.initialize_runtime_state(db_session, 999999, 1)

@pytest.mark.asyncio
async def test_duplicate_initialization_returns_existing_state(db_session: AsyncSession, seed_strategy_and_version):
    strategy, version = seed_strategy_and_version

    # Initialize first time
    state1 = await StrategyStateManager.initialize_runtime_state(db_session, strategy.id, version.id)
    
    # Initialize second time
    state2 = await StrategyStateManager.initialize_runtime_state(db_session, strategy.id, version.id)
    
    assert state1.id == state2.id

    # Verify only ONE row exists
    res = await db_session.execute(select(StrategyRuntimeState).where(StrategyRuntimeState.strategy_id == strategy.id))
    rows = res.scalars().all()
    assert len(rows) == 1

@pytest.mark.asyncio
async def test_valid_transitions_matrix(db_session: AsyncSession, seed_strategy_and_version):
    strategy, version = seed_strategy_and_version
    await StrategyStateManager.initialize_runtime_state(db_session, strategy.id, version.id)

    # 1. WAITING -> ELIGIBLE
    state = await StrategyStateManager.transition_state(
        db_session, strategy.id, version.id, StrategyLifecycleState.ELIGIBLE, "Scheduler window open"
    )
    assert state.lifecycle_state == StrategyLifecycleState.ELIGIBLE

    # 2. ELIGIBLE -> MONITORING_ENTRY
    state = await StrategyStateManager.transition_state(
        db_session, strategy.id, version.id, StrategyLifecycleState.MONITORING_ENTRY, "WS data active"
    )
    assert state.lifecycle_state == StrategyLifecycleState.MONITORING_ENTRY

    # 3. MONITORING_ENTRY -> ENTRY_SIGNAL
    state = await StrategyStateManager.transition_state(
        db_session, strategy.id, version.id, StrategyLifecycleState.ENTRY_SIGNAL, "Rules match"
    )
    assert state.lifecycle_state == StrategyLifecycleState.ENTRY_SIGNAL

    # 4. ENTRY_SIGNAL -> ORDER_PENDING
    state = await StrategyStateManager.transition_state(
        db_session, strategy.id, version.id, StrategyLifecycleState.ORDER_PENDING, "Risk checks passed"
    )
    assert state.lifecycle_state == StrategyLifecycleState.ORDER_PENDING

    # 5. ORDER_PENDING -> MONITORING_EXIT
    state = await StrategyStateManager.transition_state(
        db_session, strategy.id, version.id, StrategyLifecycleState.MONITORING_EXIT, "Broker order filled"
    )
    assert state.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT

    # 6. MONITORING_EXIT -> EXIT_SIGNAL
    state = await StrategyStateManager.transition_state(
        db_session, strategy.id, version.id, StrategyLifecycleState.EXIT_SIGNAL, "Target reached"
    )
    assert state.lifecycle_state == StrategyLifecycleState.EXIT_SIGNAL

    # 7. EXIT_SIGNAL -> EXIT_ORDER_PENDING
    state = await StrategyStateManager.transition_state(
        db_session, strategy.id, version.id, StrategyLifecycleState.EXIT_ORDER_PENDING, "Exit order dispatched"
    )
    assert state.lifecycle_state == StrategyLifecycleState.EXIT_ORDER_PENDING

    # 8. EXIT_ORDER_PENDING -> POSITION_CLOSED
    state = await StrategyStateManager.transition_state(
        db_session, strategy.id, version.id, StrategyLifecycleState.POSITION_CLOSED, "Exit order filled"
    )
    assert state.lifecycle_state == StrategyLifecycleState.POSITION_CLOSED

    # 9. POSITION_CLOSED -> WAITING
    state = await StrategyStateManager.transition_state(
        db_session, strategy.id, version.id, StrategyLifecycleState.WAITING, "Reset cycle"
    )
    assert state.lifecycle_state == StrategyLifecycleState.WAITING

@pytest.mark.asyncio
async def test_invalid_transitions_matrix(db_session: AsyncSession, seed_strategy_and_version):
    strategy, version = seed_strategy_and_version
    await StrategyStateManager.initialize_runtime_state(db_session, strategy.id, version.id)

    # Attempting invalid WAITING -> POSITION_OPEN transition
    with pytest.raises(ValidationError):
        await StrategyStateManager.transition_state(
            db_session, strategy.id, version.id, StrategyLifecycleState.POSITION_OPEN, "Invalid step"
        )
    
    # Assert database state remains WAITING (no partial updates committed)
    state = await StrategyStateManager.get_runtime_state(db_session, strategy.id)
    assert state.lifecycle_state == StrategyLifecycleState.WAITING

@pytest.mark.asyncio
async def test_same_state_idempotent_noop(db_session: AsyncSession, seed_strategy_and_version):
    strategy, version = seed_strategy_and_version
    state = await StrategyStateManager.initialize_runtime_state(db_session, strategy.id, version.id)
    
    # Transition WAITING -> WAITING should be a no-op returning same state
    res = await StrategyStateManager.transition_state(
        db_session, strategy.id, version.id, StrategyLifecycleState.WAITING, "Idempotent duplicate"
    )
    assert res.id == state.id
    assert res.lifecycle_state == StrategyLifecycleState.WAITING

@pytest.mark.asyncio
async def test_strategy_version_safety_mismatch(db_session: AsyncSession, seed_strategy_and_version):
    strategy, version = seed_strategy_and_version
    await StrategyStateManager.initialize_runtime_state(db_session, strategy.id, version.id)

    # Attempt transition using an incorrect version ID (999)
    with pytest.raises(ValidationError):
        await StrategyStateManager.transition_state(
            db_session, strategy.id, 999, StrategyLifecycleState.ELIGIBLE, "Transition under wrong version"
        )
    
    # State remains WAITING
    state = await StrategyStateManager.get_runtime_state(db_session, strategy.id)
    assert state.lifecycle_state == StrategyLifecycleState.WAITING

@pytest.mark.asyncio
async def test_pause_and_resume_transitions(db_session: AsyncSession, seed_strategy_and_version):
    strategy, version = seed_strategy_and_version
    await StrategyStateManager.initialize_runtime_state(db_session, strategy.id, version.id)
    await StrategyStateManager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.ELIGIBLE, "Eligible")
    await StrategyStateManager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.MONITORING_ENTRY, "Monitoring")

    # Pause strategy
    state = await StrategyStateManager.pause_strategy(db_session, strategy.id, version.id, "Pause triggered")
    assert state.lifecycle_state == StrategyLifecycleState.PAUSED
    assert state.paused_from_state == StrategyLifecycleState.MONITORING_ENTRY

    # Resume strategy
    state = await StrategyStateManager.resume_strategy(db_session, strategy.id, version.id, "Resume triggered")
    assert state.lifecycle_state == StrategyLifecycleState.MONITORING_ENTRY
    assert state.paused_from_state is None

@pytest.mark.asyncio
async def test_monitoring_started_and_stopped_timestamps(db_session: AsyncSession, seed_strategy_and_version):
    strategy, version = seed_strategy_and_version
    state = await StrategyStateManager.initialize_runtime_state(db_session, strategy.id, version.id)
    assert state.monitoring_started_at is None
    assert state.monitoring_stopped_at is None

    # Transition to MONITORING_ENTRY
    await StrategyStateManager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.ELIGIBLE, "Eligible")
    state = await StrategyStateManager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.MONITORING_ENTRY, "Monitoring entry")
    assert state.monitoring_started_at is not None
    assert state.monitoring_stopped_at is None
    t1 = state.monitoring_started_at

    # Transition away from MONITORING_ENTRY to ENTRY_SIGNAL
    state = await StrategyStateManager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.ENTRY_SIGNAL, "Signal matched")
    assert state.monitoring_started_at == t1
    assert state.monitoring_stopped_at is not None

@pytest.mark.asyncio
async def test_transaction_rollback_safety(db_session: AsyncSession, seed_strategy_and_version):
    strategy, version = seed_strategy_and_version
    await StrategyStateManager.initialize_runtime_state(db_session, strategy.id, version.id)

    # Open a sub-transaction block (nested savepoint)
    async with db_session.begin_nested():
        try:
            # Attempt an invalid transition
            await StrategyStateManager.transition_state(
                db_session, strategy.id, version.id, StrategyLifecycleState.POSITION_OPEN, "Failing transaction"
            )
        except ValidationError:
            # We expected this validation error to abort the nested transaction
            pass
    
    # Retrieve and verify database row is still WAITING
    state = await StrategyStateManager.get_runtime_state(db_session, strategy.id)
    assert state.lifecycle_state == StrategyLifecycleState.WAITING

@pytest.mark.asyncio
async def test_strategy_runtime_states_unique_constraint(db_session: AsyncSession, seed_strategy_and_version):
    strategy, version = seed_strategy_and_version
    await StrategyStateManager.initialize_runtime_state(db_session, strategy.id, version.id)

    # Attempting to insert a second runtime state for the same strategy should raise an IntegrityError
    duplicate_state = StrategyRuntimeState(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        lifecycle_state=StrategyLifecycleState.WAITING
    )
    db_session.add(duplicate_state)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    
    await db_session.rollback()

@pytest.mark.asyncio
async def test_strategy_event_processing_idempotency_key(db_session: AsyncSession, seed_strategy_and_version):
    strategy, version = seed_strategy_and_version

    # Insert idempotency processing record
    event_key = f"{strategy.id}:NIFTY:5m:CANDLE_CLOSED:2026-08-30T15:00:00+05:30"
    processed1 = StrategyEventProcessing(
        strategy_id=strategy.id,
        market_event_key=event_key
    )
    db_session.add(processed1)
    await db_session.flush()

    # Attempting to insert duplicate event key should throw an IntegrityError
    processed2 = StrategyEventProcessing(
        strategy_id=strategy.id,
        market_event_key=event_key
    )
    db_session.add(processed2)
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()

@pytest.mark.asyncio
async def test_concurrent_state_locking_serialization(seed_strategy_and_version):
    """
    Simulates concurrent transactions against the same strategy runtime row 
    and checks that SELECT FOR UPDATE serializes operations safely.
    """
    strategy, version = seed_strategy_and_version
    
    # 1. Initialize WAITING state row
    async with TestAsyncSessionLocal() as db_init:
        await StrategyStateManager.initialize_runtime_state(db_init, strategy.id, version.id)
        await db_init.commit()

    # We will open two isolated database sessions (representing two concurrent websocket ticks/workers)
    session_a = TestAsyncSessionLocal()
    session_b = TestAsyncSessionLocal()

    worker_a_locked_event = asyncio.Event()

    # Task A will start first, lock the row, wait 0.5s, update state to ELIGIBLE, and commit
    async def worker_a():
        async with session_a.begin():
            # Retrieves row and acquires FOR UPDATE database lock
            state_a = await StrategyStateManager.get_runtime_state(session_a, strategy.id, lock=True)
            assert state_a.lifecycle_state == StrategyLifecycleState.WAITING
            
            # Notify Worker B that A has successfully acquired the row lock
            worker_a_locked_event.set()
            
            await asyncio.sleep(0.5)
            
            await StrategyStateManager.transition_state(
                session_a, strategy.id, version.id, StrategyLifecycleState.ELIGIBLE, "Worker A success"
            )

    # Task B starts shortly after, attempts to get row and lock. It must wait until Task A releases the lock
    async def worker_b():
        # Ensure Worker A has successfully locked the row first
        await worker_a_locked_event.wait()
        async with session_b.begin():
            # Attempts to lock. This call blocks waiting for Worker A's transaction commit
            state_b = await StrategyStateManager.get_runtime_state(session_b, strategy.id, lock=True)
            
            # When B wakes up, the lock is released. B must read the NEW state ("ELIGIBLE")
            assert state_b.lifecycle_state == StrategyLifecycleState.ELIGIBLE
            
            # Attempting to transition from ELIGIBLE -> MONITORING_ENTRY
            await StrategyStateManager.transition_state(
                session_b, strategy.id, version.id, StrategyLifecycleState.MONITORING_ENTRY, "Worker B success"
            )

    try:
        await asyncio.gather(worker_a(), worker_b())
    finally:
        await session_a.close()
        await session_b.close()

    # Verify final database state is MONITORING_ENTRY
    async with TestAsyncSessionLocal() as db_final:
        final_state = await StrategyStateManager.get_runtime_state(db_final, strategy.id)
        assert final_state.lifecycle_state == StrategyLifecycleState.MONITORING_ENTRY
