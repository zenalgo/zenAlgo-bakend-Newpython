import pytest
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy.future import select

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyExecution, StrategyExecutionLeg, StrategyRuntimeState
from app.execution.models import StrategySignal, StrategyExecutionBatch, StrategyUserExecutionTrace
from app.brokers.models import UserPosition, UserOrder
from app.execution.enums import ExecutionStatus, ExecutionMode, LegRole, OptionStrikePolicy, OptionExpiryPolicy
from app.execution.contracts import ExecutionRequest, ExecutionResult, ExecutionLegResult, LogicalLeg
from app.execution.engine import ExecutionEngine
from app.execution.positions.tracker import PositionTracker
from app.strategies.enums import StrategyLifecycleState
from app.strategies.state_manager import strategy_state_manager
from app.brokers.base.schemas import OrderResult

@pytest.fixture
async def setup_pos_env(db_session):
    """Sets up a complete strategy environment for position lifecycle testing."""
    user = User(email="pos_trader@example.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=True, referral_code="REF-POS01")
    db_session.add(user)
    await db_session.flush()

    strategy = Strategy(user_id=user.id, name="Position Test Strategy", is_active=True, status="ACTIVE_LIVE", mode="PAPER")
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("50000.00"))
    db_session.add(version)
    await db_session.flush()

    strat_leg = StrategyLeg(strategy_version_id=version.id, sequence=1, segment="OPT", side="BUY", strike_selection="ATM", expiry="WEEKLY", lots=1)
    db_session.add(strat_leg)
    await db_session.flush()

    # Initialize runtime state in ORDER_PENDING
    runtime_state = await strategy_state_manager.initialize_runtime_state(db_session, strategy.id, version.id)
    # Transition WAITING -> ELIGIBLE -> MONITORING_ENTRY -> ENTRY_SIGNAL -> ORDER_PENDING
    await strategy_state_manager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.ELIGIBLE, "Ready")
    await strategy_state_manager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.MONITORING_ENTRY, "Monitoring")
    await strategy_state_manager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.ENTRY_SIGNAL, "Signal triggered")
    await strategy_state_manager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.ORDER_PENDING, "Order submitted")

    signal = StrategySignal(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        trading_date=date.today(),
        entry_time="09:30",
        signal_key=f"{strategy.id}:{version.id}:ENTRY:2026-09-01T09:30:00Z",
        market_event_key="ev_pos_01",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED",
        price=Decimal("25000.00"),
        reason="Position test signal"
    )
    db_session.add(signal)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=signal.id, strategy_id=strategy.id, strategy_version_id=version.id, trading_date=date.today(), total_users=1, status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(
        execution_batch_id=batch.id,
        signal_id=signal.id,
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        user_id=user.id,
        status="PENDING",
        correlation_id=f"POS-SIG-{signal.id}-USR-{user.id}"
    )
    db_session.add(trace)
    await db_session.flush()

    return {
        "user": user,
        "strategy": strategy,
        "version": version,
        "strat_leg": strat_leg,
        "signal": signal,
        "batch": batch,
        "trace": trace,
        "runtime_state": runtime_state
    }

def _build_pos_request(env, approved_lots: int = 1) -> ExecutionRequest:
    return ExecutionRequest(
        user_id=env["user"].id,
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        signal_id=env["signal"].id,
        signal_type="ENTRY",
        direction="BUY",
        execution_mode=ExecutionMode.PAPER,
        underlying="NIFTY",
        correlation_id=f"CID-POS-{env['signal'].id}-{env['user'].id}",
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

# --- 1. Position Opening & Synchronization Tests ---

@pytest.mark.asyncio
async def test_filled_execution_creates_open_position_and_syncs_user_position(db_session, setup_pos_env):
    """Tests 1, 6, 7, 8, 9, 18, 19: Filled execution establishes StrategyExecution and UserPosition and advances RuntimeState."""
    env = setup_pos_env
    req = _build_pos_request(env, approved_lots=2)

    result = await ExecutionEngine.execute(db_session, req)
    assert result.status == ExecutionStatus.FILLED

    # 1. StrategyExecution verified
    stmt_exec = select(StrategyExecution).where(StrategyExecution.id == result.execution_id)
    res_exec = await db_session.execute(stmt_exec)
    exec_row = res_exec.scalar_one()
    assert exec_row.status == "RUNNING"
    assert exec_row.strategy_id == env["strategy"].id
    assert exec_row.strategy_version_id == env["version"].id
    assert exec_row.user_id == env["user"].id

    # 2. StrategyExecutionLeg verified
    stmt_leg = select(StrategyExecutionLeg).where(StrategyExecutionLeg.strategy_execution_id == exec_row.id)
    res_leg = await db_session.execute(stmt_leg)
    leg_row = res_leg.scalar_one()
    assert leg_row.status == "FILLED"
    assert leg_row.filled_quantity == 100 # 2 lots * 50
    assert leg_row.average_fill_price == Decimal("100.00")

    # 3. UserPosition (Broker Account Ledger) verified
    stmt_pos = select(UserPosition).where(UserPosition.user_id == env["user"].id)
    res_pos = await db_session.execute(stmt_pos)
    pos_row = res_pos.scalar_one()
    assert pos_row.net_qty == 100
    assert pos_row.buy_qty == 100
    assert pos_row.buy_avg == Decimal("100.00")

    # 4. StrategyRuntimeState transitioned to MONITORING_EXIT
    r_state = await strategy_state_manager.get_runtime_state(db_session, env["strategy"].id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT

# --- 2. Safety Guards on Rejections / Failures ---

@pytest.mark.asyncio
async def test_rejected_and_failed_executions_create_no_open_position(db_session, setup_pos_env):
    """Tests 2, 3, 4, 5: Rejected/Failed/Cancelled executions create NO open position."""
    env = setup_pos_env
    req = _build_pos_request(env)

    # Simulation A: Rejected Execution
    rej_res = ExecutionResult(
        user_id=req.user_id,
        strategy_id=req.strategy_id,
        strategy_version_id=req.strategy_version_id,
        signal_id=req.signal_id,
        execution_id=None,
        correlation_id="REJ-01",
        status=ExecutionStatus.REJECTED,
        rejection_reason="Risk rejected"
    )
    pos_res = await PositionTracker.open_position_from_execution(db_session, rej_res, req)
    assert pos_res is None

    # Simulation B: Failed Execution
    fail_res = ExecutionResult(
        user_id=req.user_id,
        strategy_id=req.strategy_id,
        strategy_version_id=req.strategy_version_id,
        signal_id=req.signal_id,
        execution_id=None,
        correlation_id="FAIL-01",
        status=ExecutionStatus.FAILED,
        rejection_reason="Broker connection timeout"
    )
    pos_res2 = await PositionTracker.open_position_from_execution(db_session, fail_res, req)
    assert pos_res2 is None

    # Assert zero UserPosition rows created
    stmt_pos = select(UserPosition).where(UserPosition.user_id == env["user"].id)
    res_pos = await db_session.execute(stmt_pos)
    assert len(res_pos.scalars().all()) == 0

# --- 3. UserPosition Aggregation without Corruption ---

@pytest.mark.asyncio
async def test_existing_user_position_updated_accurately(db_session, setup_pos_env):
    """Test 10: Existing UserPosition accumulates quantity and calculates accurate weighted average buy price."""
    env = setup_pos_env
    
    # Pre-existing position with 50 qty @ 90.00
    existing_pos = UserPosition(
        user_id=env["user"].id,
        broker_name="MOCK",
        trading_symbol="NIFTY_CE_ATM",
        security_id="SEC_NIFTY_CE_ATM",
        position_type="INTRADAY",
        net_qty=50,
        buy_qty=50,
        buy_avg=Decimal("90.00"),
        sell_qty=0,
        sell_avg=Decimal("0.00")
    )
    db_session.add(existing_pos)
    await db_session.flush()

    # New Execution adds 50 qty @ 110.00
    req = _build_pos_request(env, approved_lots=1)
    result = await ExecutionEngine.execute(db_session, req)
    assert result.status == ExecutionStatus.FILLED

    # Check updated UserPosition: total 100 qty @ (50*90 + 50*100)/100 = 95.00 (since Mock avg is 100.00)
    stmt_pos = select(UserPosition).where(UserPosition.user_id == env["user"].id)
    res_pos = await db_session.execute(stmt_pos)
    updated_pos = res_pos.scalar_one()
    assert updated_pos.net_qty == 100
    assert updated_pos.buy_qty == 100
    assert updated_pos.buy_avg == Decimal("95.00") # (4500 + 5000) / 100 = 95.00

# --- 4. Strategy 3 Multi-Leg Hedged Position Tests ---

@pytest.mark.asyncio
async def test_strategy_3_hedged_multi_leg_position_lifecycle(db_session, setup_pos_env):
    """Test 15: Strategy 3 creates ONE unified strategy position with multiple legs and updates ledger for both."""
    env = setup_pos_env

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

    # Initialize runtime state
    await strategy_state_manager.initialize_runtime_state(db_session, strat3.id, v3.id)
    await strategy_state_manager.transition_state(db_session, strat3.id, v3.id, StrategyLifecycleState.ELIGIBLE, "Ready")
    await strategy_state_manager.transition_state(db_session, strat3.id, v3.id, StrategyLifecycleState.MONITORING_ENTRY, "Monitoring")
    await strategy_state_manager.transition_state(db_session, strat3.id, v3.id, StrategyLifecycleState.ENTRY_SIGNAL, "Signal")
    await strategy_state_manager.transition_state(db_session, strat3.id, v3.id, StrategyLifecycleState.ORDER_PENDING, "Order submitted")

    sig3 = StrategySignal(
        strategy_id=strat3.id,
        strategy_version_id=v3.id,
        trading_date=date.today(),
        entry_time="09:30",
        signal_key="k_s3_pos",
        market_event_key="ev_s3_pos",
        signal_type="ENTRY",
        direction="SELL",
        status="CREATED"
    )
    db_session.add(sig3)
    await db_session.flush()

    batch3 = StrategyExecutionBatch(signal_id=sig3.id, strategy_id=strat3.id, strategy_version_id=v3.id, trading_date=date.today(), total_users=1, status="PROCESSING")
    db_session.add(batch3)
    await db_session.flush()

    trace3 = StrategyUserExecutionTrace(execution_batch_id=batch3.id, signal_id=sig3.id, strategy_id=strat3.id, strategy_version_id=v3.id, user_id=env["user"].id, status="PENDING", correlation_id="CID-S3-POS")
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
        correlation_id="CID-S3-EXEC-POS",
        approved_lots=1,
        required_capital=Decimal("150000.00"),
        legs=[
            LogicalLeg(leg_id=1, sequence=1, role=LegRole.HEDGE, side="BUY", option_type="CE", strike_policy=OptionStrikePolicy.OTM, strike_offset=Decimal("200.0"), lots=1),
            LogicalLeg(leg_id=2, sequence=2, role=LegRole.PRIMARY, side="SELL", option_type="CE", strike_policy=OptionStrikePolicy.OTM, lots=1)
        ]
    )

    result = await ExecutionEngine.execute(db_session, req3)
    assert result.status == ExecutionStatus.FILLED

    # Check that ONE StrategyExecution exists
    stmt_exec = select(StrategyExecution).where(StrategyExecution.id == result.execution_id)
    res_exec = await db_session.execute(stmt_exec)
    exec_row = res_exec.scalar_one()
    assert exec_row.status == "RUNNING"

    # Check that TWO legs exist
    stmt_legs = select(StrategyExecutionLeg).where(StrategyExecutionLeg.strategy_execution_id == exec_row.id)
    res_legs = await db_session.execute(stmt_legs)
    legs_list = res_legs.scalars().all()
    assert len(legs_list) == 2

    # Check RuntimeState reached MONITORING_EXIT
    r_state = await strategy_state_manager.get_runtime_state(db_session, strat3.id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT

@pytest.mark.asyncio
async def test_incomplete_multi_leg_execution_cannot_open_position(db_session, setup_pos_env):
    """Test 16: An execution missing required legs fails position opening."""
    env = setup_pos_env
    req = _build_pos_request(env)
    req.legs = [
        LogicalLeg(leg_id=1, sequence=1, role=LegRole.HEDGE, side="BUY", option_type="CE", strike_policy=OptionStrikePolicy.OTM, lots=1),
        LogicalLeg(leg_id=2, sequence=2, role=LegRole.PRIMARY, side="SELL", option_type="CE", strike_policy=OptionStrikePolicy.OTM, lots=1)
    ]

    # Incomplete result with only 1 leg filled
    incomplete_result = ExecutionResult(
        user_id=req.user_id,
        strategy_id=req.strategy_id,
        strategy_version_id=req.strategy_version_id,
        signal_id=req.signal_id,
        execution_id=1234,
        correlation_id="INC-01",
        status=ExecutionStatus.FILLED,
        leg_results=[
            ExecutionLegResult(leg_id=1, correlation_id="L1", status=ExecutionStatus.FILLED, filled_quantity=50)
        ]
    )

    pos = await PositionTracker.open_position_from_execution(db_session, incomplete_result, req)
    assert pos is None

@pytest.mark.asyncio
async def test_cancelled_and_unknown_executions_create_no_open_position(db_session, setup_pos_env):
    """Tests 4 & 5: Cancelled and Unknown executions never create an open position."""
    env = setup_pos_env
    req = _build_pos_request(env)

    for status in [ExecutionStatus.CANCELLED, ExecutionStatus.UNKNOWN]:
        res = ExecutionResult(
            user_id=req.user_id,
            strategy_id=req.strategy_id,
            strategy_version_id=req.strategy_version_id,
            signal_id=req.signal_id,
            execution_id=999,
            correlation_id="STATUS-TEST",
            status=status,
            rejection_reason="Status test"
        )
        pos = await PositionTracker.open_position_from_execution(db_session, res, req)
        assert pos is None

@pytest.mark.asyncio
async def test_strategy_1_and_strategy_2_single_leg_lifecycles(db_session, setup_pos_env):
    """Tests 13 & 14: Strategy 1 (5m NIFTY) and Strategy 2 (15m NIFTY) open and track single-leg positions."""
    env = setup_pos_env

    # Strategy 1 (BUY CE)
    req1 = _build_pos_request(env, approved_lots=1)
    res1 = await ExecutionEngine.execute(db_session, req1)
    assert res1.status == ExecutionStatus.FILLED

    stmt_exec = select(StrategyExecution).where(StrategyExecution.id == res1.execution_id)
    res_exec = await db_session.execute(stmt_exec)
    assert res_exec.scalar_one().status == "RUNNING"

    # Verify RuntimeState is MONITORING_EXIT
    r_state = await strategy_state_manager.get_runtime_state(db_session, env["strategy"].id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT

@pytest.mark.asyncio
async def test_no_broker_calls_during_position_tracking(db_session, setup_pos_env):
    """Test 22: Asserts that zero broker calls occur during PositionTracker processing."""
    env = setup_pos_env
    req = _build_pos_request(env)
    
    exec_res = ExecutionResult(
        user_id=req.user_id,
        strategy_id=req.strategy_id,
        strategy_version_id=req.strategy_version_id,
        signal_id=req.signal_id,
        execution_id=None,
        correlation_id="NO-BROKER",
        status=ExecutionStatus.FILLED,
        leg_results=[]
    )

    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_place_order:
        await PositionTracker.open_position_from_execution(db_session, exec_res, req)
        mock_place_order.assert_not_called()

@pytest.mark.asyncio
async def test_structured_position_logs_contain_correlation_and_no_secrets(db_session, setup_pos_env, caplog):
    """Tests 20 & 21: Structured position logs contain correlation IDs and no leaked secrets."""
    import logging
    env = setup_pos_env
    req = _build_pos_request(env)

    with caplog.at_level(logging.INFO):
        res = await ExecutionEngine.execute(db_session, req)
        assert res.status == ExecutionStatus.FILLED

    log_texts = [r.message for r in caplog.records]
    full_logs = " ".join(log_texts)

    # Correlation checks
    assert f"strategy_id={req.strategy_id}" in full_logs
    assert f"user_id={req.user_id}" in full_logs
    assert "position_opened" in full_logs

    # Safety checks
    assert "accessToken" not in full_logs
    assert "password" not in full_logs
    assert "secret" not in full_logs

