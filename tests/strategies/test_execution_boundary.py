import pytest
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from unittest.mock import patch

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.subscriptions.models import Subscription, Plan, PlanStrategyAccess
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyExecution
from app.execution.models import StrategySignal, StrategyExecutionBatch, StrategyUserExecutionTrace
from app.execution.enums import ExecutionMode, OrderType, LegRole, OptionStrikePolicy, OptionExpiryPolicy
from app.execution.contracts import ExecutionRequest, LogicalLeg
from app.execution.validator import ExecutionValidator

@pytest.fixture
async def setup_boundary_environment(db_session):
    """Sets up a complete strategy, version, signal, and risk approval environment."""
    user = User(email="boundary_trader@example.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=True, referral_code="REF-BOUND01")
    inactive_user = User(email="boundary_inactive@example.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=False, referral_code="REF-BOUND02")
    db_session.add_all([user, inactive_user])
    await db_session.flush()

    strategy = Strategy(user_id=user.id, name="Boundary Test Strategy", is_active=True, status="ACTIVE_LIVE", mode="PAPER")
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("50000.00"))
    db_session.add(version)
    await db_session.flush()

    signal = StrategySignal(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        trading_date=date.today(),
        entry_time="09:30",
        signal_key=f"{strategy.id}:{version.id}:ENTRY:2026-09-01T09:30:00Z",
        market_event_key="ev_bound_1",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED",
        price=Decimal("25000.00"),
        reason="Boundary test signal"
    )
    db_session.add(signal)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=signal.id, strategy_id=strategy.id, strategy_version_id=version.id, trading_date=date.today(), total_users=1, status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    # Risk approved trace
    trace = StrategyUserExecutionTrace(
        execution_batch_id=batch.id,
        signal_id=signal.id,
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        user_id=user.id,
        status="PENDING", # Approved status
        correlation_id=f"BOUND-SIG-{signal.id}-USR-{user.id}"
    )
    db_session.add(trace)
    await db_session.flush()

    return {
        "user": user,
        "inactive_user": inactive_user,
        "strategy": strategy,
        "version": version,
        "signal": signal,
        "batch": batch,
        "trace": trace
    }

def _make_valid_request(env, approved_lots: int = 1) -> ExecutionRequest:
    return ExecutionRequest(
        user_id=env["user"].id,
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        signal_id=env["signal"].id,
        signal_type="ENTRY",
        direction="BUY",
        execution_mode=ExecutionMode.PAPER,
        underlying="NIFTY",
        correlation_id="BOUND-CORR-01",
        approved_lots=approved_lots,
        required_capital=Decimal("50000.00"),
        legs=[
            LogicalLeg(
                leg_id=1,
                sequence=1,
                role=LegRole.PRIMARY,
                side="BUY",
                option_type="CE",
                strike_policy=OptionStrikePolicy.ATM,
                lots=approved_lots
            )
        ]
    )

# --- 1. Valid Request Tests ---

@pytest.mark.asyncio
async def test_valid_approved_request_passes(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    req = _make_valid_request(env)
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is True
    assert res.failure_code is None
    assert res.signal.id == env["signal"].id
    assert res.trace.id == env["trace"].id

# --- 2. Signal Verification Tests ---

@pytest.mark.asyncio
async def test_nonexistent_signal_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    req = _make_valid_request(env)
    req.signal_id = 999999
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "SIGNAL_NOT_FOUND"

@pytest.mark.asyncio
async def test_signal_strategy_mismatch_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    req = _make_valid_request(env)
    req.strategy_id = 88888
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "SIGNAL_STRATEGY_MISMATCH"

@pytest.mark.asyncio
async def test_signal_version_mismatch_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    req = _make_valid_request(env)
    req.strategy_version_id = 77777
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "SIGNAL_VERSION_MISMATCH"

@pytest.mark.asyncio
async def test_invalid_signal_status_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    env["signal"].status = "CANCELLED"
    db_session.add(env["signal"])
    await db_session.flush()

    req = _make_valid_request(env)
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "INVALID_SIGNAL_STATUS"

# --- 3. User Verification Tests ---

@pytest.mark.asyncio
async def test_missing_user_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    req = _make_valid_request(env)
    req.user_id = 66666
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "USER_NOT_FOUND"

@pytest.mark.asyncio
async def test_ineligible_inactive_user_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    req = _make_valid_request(env)
    req.user_id = env["inactive_user"].id
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "USER_NOT_ELIGIBLE"

# --- 4. Risk Approval Verification Tests ---

@pytest.mark.asyncio
async def test_missing_risk_approval_trace_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    # Create signal without trace for user
    sig2 = StrategySignal(strategy_id=env["strategy"].id, strategy_version_id=env["version"].id, trading_date=date.today(), entry_time="10:00", signal_key="k2", signal_type="ENTRY", direction="BUY", status="CREATED")
    db_session.add(sig2)
    await db_session.flush()

    req = _make_valid_request(env)
    req.signal_id = sig2.id
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "RISK_APPROVAL_MISSING"

@pytest.mark.asyncio
async def test_rejected_risk_approval_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    env["trace"].status = "NOT_EXECUTED"
    env["trace"].failure_code = "DAILY_LOSS_LIMIT_REACHED"
    env["trace"].failure_reason = "Loss limit exceeded"
    db_session.add(env["trace"])
    await db_session.flush()

    req = _make_valid_request(env)
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "RISK_APPROVAL_REJECTED"

@pytest.mark.asyncio
async def test_risk_approval_mismatch_strategy_version_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    v2 = StrategyVersion(strategy_id=env["strategy"].id, version_number=2, underlying="NIFTY", capital=Decimal("60000.00"))
    db_session.add(v2)
    await db_session.flush()

    env["trace"].strategy_version_id = v2.id
    db_session.add(env["trace"])
    await db_session.flush()

    req = _make_valid_request(env)
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "RISK_APPROVAL_MISMATCH"

# --- 5. Approved Quantity & Multi-Leg Consistency Tests ---

@pytest.mark.asyncio
async def test_requested_lots_exceeding_approved_lots_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    req = _make_valid_request(env, approved_lots=1)
    req.legs[0].lots = 3 # Exceeds approved 1 lot
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "APPROVED_QUANTITY_EXCEEDED"

@pytest.mark.asyncio
async def test_strategy_3_incomplete_multi_leg_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    req = _make_valid_request(env)
    # Multi-leg with missing hedge
    req.legs = [
        LogicalLeg(leg_id=1, sequence=1, role=LegRole.PRIMARY, side="SELL", option_type="CE", strike_policy=OptionStrikePolicy.OTM, lots=1),
        LogicalLeg(leg_id=2, sequence=2, role=LegRole.PRIMARY, side="SELL", option_type="CE", strike_policy=OptionStrikePolicy.OTM, lots=1)
    ]
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "INVALID_EXECUTION_PACKAGE"

@pytest.mark.asyncio
async def test_strategy_3_valid_hedged_multi_leg_passes(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    req = _make_valid_request(env)
    req.legs = [
        LogicalLeg(leg_id=1, sequence=1, role=LegRole.HEDGE, side="BUY", option_type="CE", strike_policy=OptionStrikePolicy.OTM, strike_offset=Decimal("200.0"), lots=1),
        LogicalLeg(leg_id=2, sequence=2, role=LegRole.PRIMARY, side="SELL", option_type="CE", strike_policy=OptionStrikePolicy.OTM, lots=1)
    ]
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is True
    assert res.failure_code is None

# --- 6. Idempotency and Mode Tests ---

@pytest.mark.asyncio
async def test_duplicate_execution_fails(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    # Simulate already running / executed StrategyExecution
    exec_record = StrategyExecution(
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        user_id=env["user"].id,
        execution_trace_id=env["trace"].id,
        status="RUNNING"
    )
    db_session.add(exec_record)
    await db_session.flush()

    req = _make_valid_request(env)
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "EXECUTION_DUPLICATE"

@pytest.mark.asyncio
async def test_frontend_cannot_force_live_execution(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    req = _make_valid_request(env)
    req.execution_mode = ExecutionMode.LIVE
    res = await ExecutionValidator.validate_execution_request(db_session, req)
    assert res.is_valid is False
    assert res.failure_code == "INVALID_EXECUTION_MODE"

@pytest.mark.asyncio
async def test_rejection_paths_make_zero_broker_calls(db_session, setup_boundary_environment):
    env = setup_boundary_environment
    req = _make_valid_request(env)
    req.signal_id = 999999 # Invalid signal

    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_place_order:
        res = await ExecutionValidator.validate_execution_request(db_session, req)
        assert res.is_valid is False
        mock_place_order.assert_not_called()
