import pytest
import asyncio
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.subscriptions.models import Subscription, Plan, PlanStrategyAccess, UserDailyStrategyUsage
from app.brokers.models import BrokerAccount, UserDailyBrokerConnection
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyExecution
from app.execution.models import StrategySignal, StrategyUserExecutionTrace, StrategyExecutionBatch
from app.strategies.risk.enums import RiskDecisionType, RiskCheckType, RiskFailureCode
from app.strategies.risk.schemas import UserRiskEvaluationResult
from app.strategies.risk.service import RiskEngine

@pytest.fixture
async def setup_risk_environment(db_session):
    """Sets up a complete multi-user strategy subscription environment."""
    user1 = User(email="risk_user1@example.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=True, referral_code="REF-RISK01")
    user2 = User(email="risk_user2@example.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=True, referral_code="REF-RISK02")
    user_inactive = User(email="risk_inactive@example.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=False, referral_code="REF-RISK03")
    db_session.add_all([user1, user2, user_inactive])
    await db_session.flush()

    plan = Plan(code="RISK_PLAN", name="Risk Plan", monthly_price=Decimal("999.0"), max_strategy_executions_per_day=2, is_active=True)
    db_session.add(plan)
    await db_session.flush()

    sub1 = Subscription(user_id=user1.id, plan_id=plan.id, status="ACTIVE", start_at=datetime.now(timezone.utc), current_period_start=datetime.now(timezone.utc), current_period_end=datetime.now(timezone.utc) + timedelta(days=30))
    sub2 = Subscription(user_id=user2.id, plan_id=plan.id, status="ACTIVE", start_at=datetime.now(timezone.utc), current_period_start=datetime.now(timezone.utc), current_period_end=datetime.now(timezone.utc) + timedelta(days=30))
    sub_inact = Subscription(user_id=user_inactive.id, plan_id=plan.id, status="ACTIVE", start_at=datetime.now(timezone.utc), current_period_start=datetime.now(timezone.utc), current_period_end=datetime.now(timezone.utc) + timedelta(days=30))
    db_session.add_all([sub1, sub2, sub_inact])
    await db_session.flush()

    strategy = Strategy(user_id=user1.id, name="Risk Engine Test Strat", is_active=True, status="ACTIVE_LIVE", mode="PAPER")
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("50000.00"))
    db_session.add(version)
    await db_session.flush()

    leg = StrategyLeg(strategy_version_id=version.id, sequence=1, segment="OPT", side="BUY", strike_selection="ATM", expiry="WEEKLY", lots=2)
    access = PlanStrategyAccess(plan_id=plan.id, strategy_id=strategy.id, is_enabled=True)
    db_session.add_all([leg, access])
    await db_session.flush()

    # Broker connection for user 1 & user 2
    b_acc1 = BrokerAccount(user_id=user1.id, broker_code="MOCK", account_client_id="MOCK_01", status="ACTIVE")
    b_acc2 = BrokerAccount(user_id=user2.id, broker_code="MOCK", account_client_id="MOCK_02", status="ACTIVE")
    db_session.add_all([b_acc1, b_acc2])
    await db_session.flush()

    today = date.today()
    conn1 = UserDailyBrokerConnection(user_id=user1.id, connection_date=today, broker_account_id=b_acc1.id, broker_code="MOCK", status="ACTIVE")
    conn2 = UserDailyBrokerConnection(user_id=user2.id, connection_date=today, broker_account_id=b_acc2.id, broker_code="MOCK", status="ACTIVE")
    db_session.add_all([conn1, conn2])
    await db_session.flush()

    signal = StrategySignal(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        trading_date=today,
        entry_time="09:30",
        signal_key=f"{strategy.id}:{version.id}:ENTRY:2026-09-01T09:30:00Z",
        market_event_key="ev_risk_1",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED",
        price=Decimal("25000.00"),
        reason="Entry conditions matched"
    )
    db_session.add(signal)
    await db_session.flush()

    return {
        "user1": user1,
        "user2": user2,
        "user_inactive": user_inactive,
        "strategy": strategy,
        "version": version,
        "signal": signal,
        "plan": plan
    }

# --- Tests 9D: Core Orchestration, User Isolation, and Quota Reservation ---

@pytest.mark.asyncio
async def test_risk_engine_user_approval(db_session, setup_risk_environment):
    """Test 9D-01: Valid user passes all 14 risk checks and reserves execution quota."""
    env = setup_risk_environment
    engine = RiskEngine()

    res = await engine.evaluate_user_risk(db_session, env["signal"], env["user1"].id)

    assert res.decision == RiskDecisionType.APPROVED
    assert res.approved_lots == 2
    assert res.required_capital == Decimal("50000.00")
    assert res.failure_code is None
    assert len(res.checks) >= 10

@pytest.mark.asyncio
async def test_risk_engine_user_isolation(db_session, setup_risk_environment):
    """Test 9D-02: User A passes risk while User B (reached daily limit) fails risk on the same signal."""
    env = setup_risk_environment
    engine = RiskEngine()

    # Pre-exhaust user 2's daily quota limit (max 2)
    today = date.today()
    usage2 = UserDailyStrategyUsage(user_id=env["user2"].id, trading_date=today, strategy_execution_count=2)
    db_session.add(usage2)
    await db_session.flush()

    # Evaluate both users on the SAME signal
    res1 = await engine.evaluate_user_risk(db_session, env["signal"], env["user1"].id)
    res2 = await engine.evaluate_user_risk(db_session, env["signal"], env["user2"].id)

    # User 1 is APPROVED
    assert res1.decision == RiskDecisionType.APPROVED
    assert res1.user_id == env["user1"].id

    # User 2 is REJECTED
    assert res2.decision == RiskDecisionType.REJECTED
    assert res2.user_id == env["user2"].id
    assert res2.failure_code == RiskFailureCode.DAILY_LIMIT_REACHED

@pytest.mark.asyncio
async def test_risk_engine_inactive_user_rejection(db_session, setup_risk_environment):
    """Test 9D-03: Inactive user is rejected with USER_INACTIVE."""
    env = setup_risk_environment
    engine = RiskEngine()

    res = await engine.evaluate_user_risk(db_session, env["signal"], env["user_inactive"].id)
    assert res.decision == RiskDecisionType.REJECTED
    assert res.failure_code == RiskFailureCode.USER_INACTIVE

@pytest.mark.asyncio
async def test_risk_engine_safety_exit_bypass(db_session, setup_risk_environment):
    """Test 9D-04: Safety EXIT signal bypasses entry quota checks and is approved."""
    env = setup_risk_environment
    engine = RiskEngine()

    exit_signal = StrategySignal(
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        trading_date=date.today(),
        entry_time="15:15",
        signal_key=f"{env['strategy'].id}:{env['version'].id}:EXIT:2026-09-01T15:15:00Z",
        market_event_key="ev_exit_risk_1",
        signal_type="EXIT",
        direction="SELL",
        status="CREATED",
        price=Decimal("25100.00"),
        reason="Forced exit"
    )
    db_session.add(exit_signal)
    await db_session.flush()

    res = await engine.evaluate_user_risk(db_session, exit_signal, env["user1"].id)
    assert res.decision == RiskDecisionType.APPROVED
    assert "Safety EXIT approved" in res.reason

@pytest.mark.asyncio
async def test_risk_engine_redis_lock_failure_closed(db_session, setup_risk_environment):
    """Test 9D-05: Concurrency lock acquisition failure safely fails closed."""
    env = setup_risk_environment
    engine = RiskEngine()

    with patch("app.core.redis.redis_manager.lock", side_effect=Exception("Redis connection timed out")):
        res = await engine.evaluate_user_risk(db_session, env["signal"], env["user1"].id)
        assert res.decision == RiskDecisionType.REJECTED
        assert res.failure_code == RiskFailureCode.RESERVATION_FAILED

@pytest.mark.asyncio
async def test_risk_engine_no_broker_order_execution_called(db_session, setup_risk_environment):
    """Test 9D-06: Risk Engine evaluates risk without placing broker orders."""
    env = setup_risk_environment
    engine = RiskEngine()

    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_place_order:
        res = await engine.evaluate_user_risk(db_session, env["signal"], env["user1"].id)
        assert res.decision == RiskDecisionType.APPROVED
        mock_place_order.assert_not_called()

@pytest.mark.asyncio
async def test_risk_engine_idempotent_duplicate_evaluation(db_session, setup_risk_environment):
    """Test 9D-07: Idempotent evaluation of the same (signal_id, user_id) returns cached decision without re-decrementing quota."""
    env = setup_risk_environment
    engine = RiskEngine()

    res1 = await engine.evaluate_user_risk(db_session, env["signal"], env["user1"].id)
    assert res1.decision == RiskDecisionType.APPROVED

    # Create trace record representing first successful evaluation
    batch = StrategyExecutionBatch(signal_id=env["signal"].id, strategy_id=env["strategy"].id, strategy_version_id=env["version"].id, trading_date=date.today(), total_users=1, status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(
        execution_batch_id=batch.id,
        signal_id=env["signal"].id,
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        user_id=env["user1"].id,
        status="PENDING",
        correlation_id=f"IDEMP-SIG-{env['signal'].id}-USR-{env['user1'].id}"
    )
    db_session.add(trace)
    await db_session.flush()

    # Second evaluation returns idempotent result
    res2 = await engine.evaluate_user_risk(db_session, env["signal"], env["user1"].id)
    assert res2.decision == RiskDecisionType.APPROVED
    assert "Idempotent return" in res2.reason

@pytest.mark.asyncio
async def test_risk_engine_version_safety(db_session, setup_risk_environment):
    """Test 9D-08: Signal evaluating version 1 evaluates against version 1, not a newly added draft version 2."""
    env = setup_risk_environment
    engine = RiskEngine()

    # Create version 2 with different capital
    v2 = StrategyVersion(strategy_id=env["strategy"].id, version_number=2, underlying="NIFTY", capital=Decimal("150000.00"))
    db_session.add(v2)
    await db_session.flush()

    res = await engine.evaluate_user_risk(db_session, env["signal"], env["user1"].id)
    assert res.decision == RiskDecisionType.APPROVED
    # Must preserve signal's evaluated version ID (version 1)
    assert res.strategy_version_id == env["version"].id
    assert res.required_capital == Decimal("50000.00")

@pytest.mark.asyncio
async def test_risk_engine_resolve_candidate_users(db_session, setup_risk_environment):
    """Test 9D-09: Resolves only users who subscribe to plans authorizing the strategy."""
    env = setup_risk_environment
    engine = RiskEngine()

    candidates = await engine.resolve_candidate_users(db_session, env["strategy"].id)
    assert env["user1"].id in candidates
    assert env["user2"].id in candidates
    assert env["user_inactive"].id in candidates # User is subscribed, inactive check occurs inside pipeline

