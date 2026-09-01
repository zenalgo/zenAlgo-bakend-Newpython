import pytest
import asyncio
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.subscriptions.models import Subscription, Plan, PlanStrategyAccess
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyExecution, StrategyExecutionLeg
from app.execution.models import StrategySignal, StrategyExecutionBatch, StrategyUserExecutionTrace
from app.brokers.models import UserOrder
from app.execution.enums import ExecutionStatus, ExecutionMode, LegRole, OptionStrikePolicy, OptionExpiryPolicy
from app.execution.contracts import ExecutionRequest, LogicalLeg
from app.execution.engine import ExecutionEngine
from app.brokers.base.schemas import OrderResult
from sqlalchemy.future import select

@pytest.fixture
async def setup_execution_env(db_session):
    """Sets up a complete strategy execution environment."""
    user = User(email="exec_trader@example.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=True, referral_code="REF-EXEC01")
    inactive_user = User(email="exec_inactive@example.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=False, referral_code="REF-EXEC02")
    db_session.add_all([user, inactive_user])
    await db_session.flush()

    strategy = Strategy(user_id=user.id, name="Exec Test Strategy", is_active=True, status="ACTIVE_LIVE", mode="PAPER")
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("50000.00"))
    db_session.add(version)
    await db_session.flush()

    strat_leg = StrategyLeg(strategy_version_id=version.id, sequence=1, segment="OPT", side="BUY", strike_selection="ATM", expiry="WEEKLY", lots=1)
    db_session.add(strat_leg)
    await db_session.flush()

    signal = StrategySignal(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        trading_date=date.today(),
        entry_time="09:30",
        signal_key=f"{strategy.id}:{version.id}:ENTRY:2026-09-01T09:30:00Z",
        market_event_key="ev_exec_01",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED",
        price=Decimal("25000.00"),
        reason="Execution test signal"
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
        status="PENDING",
        correlation_id=f"EXEC-SIG-{signal.id}-USR-{user.id}"
    )
    db_session.add(trace)
    await db_session.flush()

    return {
        "user": user,
        "inactive_user": inactive_user,
        "strategy": strategy,
        "version": version,
        "strat_leg": strat_leg,
        "signal": signal,
        "batch": batch,
        "trace": trace
    }

def _build_request(env, approved_lots: int = 1) -> ExecutionRequest:
    return ExecutionRequest(
        user_id=env["user"].id,
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        signal_id=env["signal"].id,
        signal_type="ENTRY",
        direction="BUY",
        execution_mode=ExecutionMode.PAPER,
        underlying="NIFTY",
        correlation_id=f"CID-EXEC-{env['signal'].id}-{env['user'].id}",
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

# --- 1. Happy Path Execution Tests ---

@pytest.mark.asyncio
async def test_valid_approved_request_executes_on_mock_broker(db_session, setup_execution_env):
    """Test 1: Valid approved request reaches MockBroker, places order, and returns FILLED."""
    env = setup_execution_env
    req = _build_request(env)

    result = await ExecutionEngine.execute(db_session, req)

    assert result.status == ExecutionStatus.FILLED
    assert result.execution_id is not None
    assert len(result.leg_results) == 1
    assert result.leg_results[0].status == ExecutionStatus.FILLED
    assert result.leg_results[0].broker_order_id.startswith("MOCK_ORD_")
    assert result.total_filled_quantity == 50 # 1 lot * 50

    # Verify database records
    stmt_exec = select(StrategyExecution).where(StrategyExecution.id == result.execution_id)
    res_exec = await db_session.execute(stmt_exec)
    exec_row = res_exec.scalar_one()
    assert exec_row.status == "RUNNING"
    assert exec_row.user_id == env["user"].id

    stmt_order = select(UserOrder).where(UserOrder.user_id == env["user"].id)
    res_order = await db_session.execute(stmt_order)
    order_row = res_order.scalar_one()
    assert order_row.order_status == "FILLED"
    assert order_row.quantity == 50

# --- 2. Zero Broker Calls on Validation Failure ---

@pytest.mark.asyncio
async def test_validator_rejection_causes_zero_broker_calls(db_session, setup_execution_env):
    """Test 2: When ExecutionValidator fails (missing signal), zero broker orders are placed."""
    env = setup_execution_env
    req = _build_request(env)
    req.signal_id = 999999 # Nonexistent signal

    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_place_order:
        result = await ExecutionEngine.execute(db_session, req)
        assert result.status == ExecutionStatus.REJECTED
        assert "SIGNAL_NOT_FOUND" in result.rejection_reason
        mock_place_order.assert_not_called()

# --- 3. Mock Broker Rejection Handling ---

@pytest.mark.asyncio
async def test_mock_broker_rejection_persists_failure(db_session, setup_execution_env):
    """Test 4: When MockBroker rejects order, ExecutionEngine persists FAILED status."""
    env = setup_execution_env
    req = _build_request(env)

    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order", return_value=OrderResult(broker_order_id="MOCK_REJ_01", order_status="REJECTED", message="RMS Margin Exceeded")):
        result = await ExecutionEngine.execute(db_session, req)
        assert result.status == ExecutionStatus.FAILED
        assert "RMS Margin Exceeded" in result.rejection_reason

        # Trace marked failed
        stmt_trace = select(StrategyUserExecutionTrace).where(StrategyUserExecutionTrace.id == env["trace"].id)
        res_trace = await db_session.execute(stmt_trace)
        trace_row = res_trace.scalar_one()
        assert trace_row.status == "FAILED"
        assert trace_row.failure_code == "BROKER_REJECTION"

# --- 4. Idempotency & Duplicate Execution Protection ---

@pytest.mark.asyncio
async def test_duplicate_execution_cannot_create_another_broker_order(db_session, setup_execution_env):
    """Test 5: Executing the same request twice returns REJECTED on the second attempt with zero extra broker calls."""
    env = setup_execution_env
    req = _build_request(env)

    # First execution succeeds
    res1 = await ExecutionEngine.execute(db_session, req)
    assert res1.status == ExecutionStatus.FILLED

    # Second execution attempt is rejected by idempotency check
    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_place_order:
        res2 = await ExecutionEngine.execute(db_session, req)
        assert res2.status == ExecutionStatus.REJECTED
        assert "EXECUTION_DUPLICATE" in res2.rejection_reason
        mock_place_order.assert_not_called()

# --- 5. Strategy 3 Multi-Leg Package Execution ---

@pytest.mark.asyncio
async def test_strategy_3_hedged_multi_leg_executes_in_order(db_session, setup_execution_env):
    """Test 11: Strategy 3 submits HEDGE leg first, then PRIMARY short leg as a unified package."""
    env = setup_execution_env
    
    # Create Strategy 3 version for RELIANCE
    strat3 = Strategy(user_id=env["user"].id, name="Strategy 3 Camarilla", is_active=True, status="ACTIVE_LIVE", mode="PAPER")
    db_session.add(strat3)
    await db_session.flush()

    v3 = StrategyVersion(strategy_id=strat3.id, version_number=1, underlying="RELIANCE", capital=Decimal("150000.00"))
    db_session.add(v3)
    await db_session.flush()

    leg1 = StrategyLeg(strategy_version_id=v3.id, sequence=1, segment="OPT", side="BUY", strike_selection="OTM", expiry="MONTHLY", lots=1)
    leg2 = StrategyLeg(strategy_version_id=v3.id, sequence=2, segment="OPT", side="SELL", strike_selection="OTM", expiry="MONTHLY", lots=1)
    db_session.add_all([leg1, leg2])
    await db_session.flush()

    sig3 = StrategySignal(
        strategy_id=strat3.id,
        strategy_version_id=v3.id,
        trading_date=date.today(),
        entry_time="09:30",
        signal_key="k_strat3",
        market_event_key="ev_strat3",
        signal_type="ENTRY",
        direction="SELL",
        status="CREATED"
    )
    db_session.add(sig3)
    await db_session.flush()

    batch3 = StrategyExecutionBatch(signal_id=sig3.id, strategy_id=strat3.id, strategy_version_id=v3.id, trading_date=date.today(), total_users=1, status="PROCESSING")
    db_session.add(batch3)
    await db_session.flush()

    trace3 = StrategyUserExecutionTrace(execution_batch_id=batch3.id, signal_id=sig3.id, strategy_id=strat3.id, strategy_version_id=v3.id, user_id=env["user"].id, status="PENDING", correlation_id="CID-S3")
    db_session.add(trace3)
    await db_session.flush()

    req3 = ExecutionRequest(
        user_id=env["user"].id,
        strategy_id=strat3.id,
        strategy_version_id=v3.id,
        signal_id=sig3.id,
        signal_type="ENTRY",
        direction="SELL",
        execution_mode=ExecutionMode.PAPER,
        underlying="RELIANCE",
        correlation_id="CID-S3-EXEC",
        approved_lots=1,
        required_capital=Decimal("150000.00"),
        legs=[
            LogicalLeg(leg_id=1, sequence=1, role=LegRole.HEDGE, side="BUY", option_type="CE", strike_policy=OptionStrikePolicy.OTM, strike_offset=Decimal("200.0"), lots=1),
            LogicalLeg(leg_id=2, sequence=2, role=LegRole.PRIMARY, side="SELL", option_type="CE", strike_policy=OptionStrikePolicy.OTM, lots=1)
        ]
    )

    result = await ExecutionEngine.execute(db_session, req3)
    assert result.status == ExecutionStatus.FILLED
    assert len(result.leg_results) == 2
    # Leg 1 is HEDGE (BUY)
    assert result.leg_results[0].status == ExecutionStatus.FILLED
    # Leg 2 is SHORT (SELL)
    assert result.leg_results[1].status == ExecutionStatus.FILLED
    assert result.total_filled_quantity == 500 # 2 legs * 250 multiplier for RELIANCE

@pytest.mark.asyncio
async def test_strategy_3_incomplete_hedge_rejected_before_broker(db_session, setup_execution_env):
    """Test 12: Strategy 3 with missing hedge leg fails validation with zero broker calls."""
    env = setup_execution_env
    req = _build_request(env)
    # Naked short without hedge
    req.legs = [
        LogicalLeg(leg_id=1, sequence=1, role=LegRole.PRIMARY, side="SELL", option_type="CE", strike_policy=OptionStrikePolicy.OTM, lots=1),
        LogicalLeg(leg_id=2, sequence=2, role=LegRole.PRIMARY, side="SELL", option_type="CE", strike_policy=OptionStrikePolicy.OTM, lots=1)
    ]

    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_place_order:
        result = await ExecutionEngine.execute(db_session, req)
        assert result.status == ExecutionStatus.REJECTED
        assert "INVALID_EXECUTION_PACKAGE" in result.rejection_reason
        mock_place_order.assert_not_called()

@pytest.mark.asyncio
async def test_strategy_version_mismatch_never_reaches_broker(db_session, setup_execution_env):
    """Test 7: Strategy version mismatch fails before broker call."""
    env = setup_execution_env
    req = _build_request(env)
    req.strategy_version_id = 99999

    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_place_order:
        res = await ExecutionEngine.execute(db_session, req)
        assert res.status == ExecutionStatus.REJECTED
        assert "SIGNAL_VERSION_MISMATCH" in res.rejection_reason
        mock_place_order.assert_not_called()

@pytest.mark.asyncio
async def test_missing_risk_approval_never_reaches_broker(db_session, setup_execution_env):
    """Test 8: Unapproved signal/user trace fails before broker call."""
    env = setup_execution_env
    req = _build_request(env)
    env["trace"].status = "NOT_EXECUTED"
    env["trace"].failure_code = "MAX_POSITIONS_REACHED"
    db_session.add(env["trace"])
    await db_session.flush()

    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_place_order:
        res = await ExecutionEngine.execute(db_session, req)
        assert res.status == ExecutionStatus.REJECTED
        assert "RISK_APPROVAL_REJECTED" in res.rejection_reason
        mock_place_order.assert_not_called()

@pytest.mark.asyncio
async def test_inactive_user_never_reaches_broker(db_session, setup_execution_env):
    """Test 9: Inactive user request fails before broker call."""
    env = setup_execution_env
    req = _build_request(env)
    req.user_id = env["inactive_user"].id

    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_place_order:
        res = await ExecutionEngine.execute(db_session, req)
        assert res.status == ExecutionStatus.REJECTED
        assert "USER_NOT_ELIGIBLE" in res.rejection_reason
        mock_place_order.assert_not_called()

@pytest.mark.asyncio
async def test_frontend_cannot_force_live_execution_through_engine(db_session, setup_execution_env):
    """Test 10: Unauthorized LIVE execution mode fails before broker call."""
    env = setup_execution_env
    req = _build_request(env)
    req.execution_mode = ExecutionMode.LIVE

    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_place_order:
        res = await ExecutionEngine.execute(db_session, req)
        assert res.status == ExecutionStatus.REJECTED
        assert "INVALID_EXECUTION_MODE" in res.rejection_reason
        mock_place_order.assert_not_called()

@pytest.mark.asyncio
async def test_structured_logs_contain_correlation_and_no_secrets(db_session, setup_execution_env, caplog):
    """Test 13 & 14: Validates structured logs emit correlation IDs and do not leak credentials."""
    import logging
    env = setup_execution_env
    req = _build_request(env)

    with caplog.at_level(logging.INFO):
        res = await ExecutionEngine.execute(db_session, req)
        assert res.status == ExecutionStatus.FILLED

    log_texts = [r.message for r in caplog.records]
    full_logs = " ".join(log_texts)
    
    # Assert correlation metadata present
    assert f"strategy_id={req.strategy_id}" in full_logs
    assert f"signal_id={req.signal_id}" in full_logs
    assert f"user_id={req.user_id}" in full_logs

    # Assert no secrets leaked
    assert "accessToken" not in full_logs
    assert "password" not in full_logs
    assert "secret" not in full_logs

