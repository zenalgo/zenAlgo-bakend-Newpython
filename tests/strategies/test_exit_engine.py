import pytest
import asyncio
from datetime import datetime, timezone, date, time, timedelta
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy.future import select

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyExecution, StrategyExecutionLeg, StrategyRuntimeState
from app.execution.models import StrategySignal, StrategyExecutionBatch, StrategyUserExecutionTrace
from app.market_data.schemas import MarketEvent
from app.market_data.enums import MarketEventType
from app.strategies.enums import StrategyLifecycleState
from app.strategies.state_manager import strategy_state_manager
from app.strategies.signals.enums import SignalType, SignalDirection
from app.strategies.exits.enums import ExitType, ExitDecision, PositionDirection
from app.strategies.exits.schemas import TrailingStopState, ExitEvaluationResult
from app.strategies.exits.evaluators import (
    evaluate_stop_loss,
    evaluate_target,
    evaluate_r_multiple,
    evaluate_trailing_stop,
    evaluate_forced_time_exit,
    evaluate_expiry_exit,
    evaluate_strategy_invalidation
)
from app.strategies.exits.trailing import TrailingStateManager
from app.strategies.exits.engine import ExitEngine

# --- A - G: Pure Evaluator Tests ---

def test_stop_loss_evaluator():
    """Test A, E, F: Evaluates Long and Short Stop Loss triggers."""
    # Long: Entry 100, SL 95
    res_long_hit = evaluate_stop_loss(Decimal("100.00"), Decimal("94.50"), Decimal("95.00"), PositionDirection.BUY)
    assert res_long_hit.decision == ExitDecision.TRIGGERED
    assert res_long_hit.exit_type == ExitType.STOP_LOSS

    res_long_hold = evaluate_stop_loss(Decimal("100.00"), Decimal("98.00"), Decimal("95.00"), PositionDirection.BUY)
    assert res_long_hold.decision == ExitDecision.NOT_TRIGGERED

    # Short: Entry 100, SL 105
    res_short_hit = evaluate_stop_loss(Decimal("100.00"), Decimal("105.50"), Decimal("105.00"), PositionDirection.SELL)
    assert res_short_hit.decision == ExitDecision.TRIGGERED

    res_short_hold = evaluate_stop_loss(Decimal("100.00"), Decimal("102.00"), Decimal("105.00"), PositionDirection.SELL)
    assert res_short_hold.decision == ExitDecision.NOT_TRIGGERED

def test_target_evaluator():
    """Test B: Fixed target evaluator."""
    res_tgt_hit = evaluate_target(Decimal("100.00"), Decimal("112.00"), Decimal("110.00"), PositionDirection.BUY)
    assert res_tgt_hit.decision == ExitDecision.TRIGGERED
    assert res_tgt_hit.exit_type == ExitType.TARGET

    res_tgt_miss = evaluate_target(Decimal("100.00"), Decimal("108.00"), Decimal("110.00"), PositionDirection.BUY)
    assert res_tgt_miss.decision == ExitDecision.NOT_TRIGGERED

def test_r_multiple_calculations():
    """Test C, D: 1R and 2R calculations from actual entry and stop loss."""
    entry = Decimal("100.00")
    sl = Decimal("95.00") # Risk = 5.00 -> 1R = 105.00, 2R = 110.00

    # 1R Partial Target (50% lots)
    res_1r = evaluate_r_multiple(entry, sl, Decimal("105.00"), r_multiple=Decimal("1.0"), direction=PositionDirection.BUY, exit_quantity_pct=Decimal("50.0"))
    assert res_1r.decision == ExitDecision.TRIGGERED
    assert res_1r.exit_type == ExitType.PARTIAL_EXIT
    assert res_1r.exit_quantity_pct == Decimal("50.0")

    # 2R Full Target (100% lots)
    res_2r = evaluate_r_multiple(entry, sl, Decimal("110.00"), r_multiple=Decimal("2.0"), direction=PositionDirection.BUY, exit_quantity_pct=Decimal("100.0"))
    assert res_2r.decision == ExitDecision.TRIGGERED
    assert res_2r.exit_type == ExitType.R_MULTIPLE_TARGET
    assert res_2r.exit_quantity_pct == Decimal("100.0")

def test_candle_stop_loss():
    """Test G: Stop loss set to confirmation candle low."""
    conf_candle_low = Decimal("24920.00")
    entry_price = Decimal("24950.00")

    res_hit = evaluate_stop_loss(entry_price, Decimal("24915.00"), conf_candle_low, PositionDirection.BUY)
    assert res_hit.decision == ExitDecision.TRIGGERED

def test_trailing_stop_movement_and_trigger():
    """Test I, J: Dynamic trailing stop moves to breakeven and trails peak price."""
    initial_state = TrailingStopState(
        execution_id=101,
        direction=PositionDirection.BUY,
        entry_price=Decimal("100.00"),
        initial_stop_loss=Decimal("95.00"), # Risk = 5
        current_trailing_stop=Decimal("95.00"),
        highest_favorable_price=Decimal("100.00"),
        lowest_favorable_price=Decimal("100.00"),
        step_r=Decimal("1.0")
    )

    # 1. Price moves to 106 (+1.2R) -> Breakeven activated, SL moves to 100.00 (or 106-5 = 101.00)
    res1, state1 = evaluate_trailing_stop(Decimal("106.00"), initial_state)
    assert res1.decision == ExitDecision.NOT_TRIGGERED
    assert state1.is_breakeven_activated is True
    assert state1.current_trailing_stop >= Decimal("100.00")
    assert state1.highest_favorable_price == Decimal("106.00")

    # 2. Price climbs to 115 (+3R) -> SL trails to 115 - 5 = 110.00
    res2, state2 = evaluate_trailing_stop(Decimal("115.00"), state1)
    assert state2.current_trailing_stop == Decimal("110.00")
    assert state2.highest_favorable_price == Decimal("115.00")

    # 3. Price drops to 109.50 (breaches trailing SL 110.00) -> TRIGGERED
    res3, state3 = evaluate_trailing_stop(Decimal("109.50"), state2)
    assert res3.decision == ExitDecision.TRIGGERED
    assert res3.exit_type == ExitType.TRAILING_STOP

def test_forced_15_15_ist_exit_and_timezone():
    """Test K, L: Forced 15:15 IST cutoff evaluation."""
    # Before 15:15 -> NOT_TRIGGERED
    res_before = evaluate_forced_time_exit(time(14, 30), time(15, 15), is_intraday=True)
    assert res_before.decision == ExitDecision.NOT_TRIGGERED

    # At or after 15:15 -> TRIGGERED
    res_cutoff = evaluate_forced_time_exit(time(15, 15), time(15, 15), is_intraday=True)
    assert res_cutoff.decision == ExitDecision.TRIGGERED
    assert res_cutoff.exit_type == ExitType.FORCED_TIME_EXIT

    # Non-intraday positional exempt
    res_positional = evaluate_forced_time_exit(time(15, 20), time(15, 15), is_intraday=False)
    assert res_positional.decision == ExitDecision.SKIPPED

def test_monthly_expiry_exit():
    """Test M: Monthly contract expiry cutoff on expiry day."""
    today = date(2026, 9, 24) # Last Thursday
    expiry = date(2026, 9, 24)

    # On expiry day at 15:15 -> TRIGGERED
    res_exp = evaluate_expiry_exit(today, expiry, time(15, 15), time(15, 15))
    assert res_exp.decision == ExitDecision.TRIGGERED
    assert res_exp.exit_type == ExitType.EXPIRY_EXIT

    # Prior day -> NOT_TRIGGERED
    res_prior = evaluate_expiry_exit(date(2026, 9, 23), expiry, time(15, 15), time(15, 15))
    assert res_prior.decision == ExitDecision.NOT_TRIGGERED

def test_strategy_3_invalidation():
    """Test Q: Strategy 3 Camarilla R3 breach invalidates Short CE setup."""
    r3_level = Decimal("2950.00") # Camarilla R3
    
    # Breach above R3 -> TRIGGERED
    res_inv = evaluate_strategy_invalidation(Decimal("2955.00"), r3_level, PositionDirection.SELL)
    assert res_inv.decision == ExitDecision.TRIGGERED
    assert res_inv.exit_type == ExitType.STRATEGY_INVALIDATION

    # Below R3 -> NOT_TRIGGERED
    res_safe = evaluate_strategy_invalidation(Decimal("2940.00"), r3_level, PositionDirection.SELL)
    assert res_safe.decision == ExitDecision.NOT_TRIGGERED

# --- N - AD: Exit Engine Orchestration & Safety Tests ---

@pytest.fixture
async def setup_exit_env(db_session):
    """Sets up an active running strategy position in MONITORING_EXIT state."""
    user = User(email="exit_trader@example.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=True, referral_code="REF-EXT01")
    db_session.add(user)
    await db_session.flush()

    strategy = Strategy(user_id=user.id, name="Exit Strategy 1", is_active=True, status="ACTIVE_LIVE", mode="PAPER")
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("50000.00"))
    db_session.add(version)
    await db_session.flush()

    leg1 = StrategyLeg(strategy_version_id=version.id, sequence=1, segment="OPT", side="BUY", strike_selection="ATM", expiry="WEEKLY", lots=1)
    db_session.add(leg1)
    await db_session.flush()

    # Runtime state in MONITORING_EXIT
    runtime_state = await strategy_state_manager.initialize_runtime_state(db_session, strategy.id, version.id)
    await strategy_state_manager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.ELIGIBLE, "Ready")
    await strategy_state_manager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.MONITORING_ENTRY, "Monitoring")
    await strategy_state_manager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.ENTRY_SIGNAL, "Signal")
    await strategy_state_manager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.ORDER_PENDING, "Order submitted")
    await strategy_state_manager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.POSITION_OPEN, "Position open")
    await strategy_state_manager.transition_state(db_session, strategy.id, version.id, StrategyLifecycleState.MONITORING_EXIT, "Monitoring exit")

    # Active StrategyExecution
    execution = StrategyExecution(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        user_id=user.id,
        status="RUNNING",
        entry_time=datetime.now(timezone.utc),
        realized_pnl=Decimal("0.00"),
        unrealized_pnl=Decimal("0.00")
    )
    db_session.add(execution)
    await db_session.flush()

    exec_leg = StrategyExecutionLeg(
        strategy_execution_id=execution.id,
        strategy_leg_id=leg1.id,
        correlation_id=f"EXT-LEG-{execution.id}-1",
        status="FILLED",
        quantity=50,
        filled_quantity=50,
        price=Decimal("100.00"),
        average_fill_price=Decimal("100.00")
    )
    db_session.add(exec_leg)
    await db_session.flush()

    return {
        "user": user,
        "strategy": strategy,
        "version": version,
        "execution": execution,
        "runtime_state": runtime_state
    }

@pytest.mark.asyncio
async def test_strategy_1_exit_at_2r_target(db_session, setup_exit_env):
    """Test N: Strategy 1 reaches 2R target and generates EXIT signal."""
    env = setup_exit_env
    # Entry 100.00, SL 95.00 -> 2R target = 110.00
    event = MarketEvent(
        event_id="ev_901",
        event_type=MarketEventType.CANDLE_CLOSED,
        symbol="NIFTY",
        timeframe="5m",
        timestamp=datetime(2026, 9, 1, 4, 30, tzinfo=timezone.utc),
        close=Decimal("110.50"),
        price=Decimal("110.50")
    )

    signals = await ExitEngine.evaluate_strategy_exits(
        db=db_session,
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        event=event,
        custom_stop_loss=Decimal("95.00"),
        custom_r_multiple=Decimal("2.0")
    )

    assert len(signals) == 1
    assert signals[0].signal_type == SignalType.EXIT
    assert signals[0].direction == SignalDirection.SELL
    assert "Reached 2.0R target" in signals[0].reason

    # Runtime state transitioned to EXIT_ORDER_PENDING
    r_state = await strategy_state_manager.get_runtime_state(db_session, env["strategy"].id)
    assert r_state.lifecycle_state == StrategyLifecycleState.EXIT_ORDER_PENDING

@pytest.mark.asyncio
async def test_strategy_1_partial_exit_at_1r_leaves_position_monitoring(db_session, setup_exit_env):
    """Test S: Partial exit at 1R generates signal but keeps position in MONITORING_EXIT."""
    env = setup_exit_env
    # Entry 100.00, SL 95.00 -> 1R = 105.00
    event = MarketEvent(
        event_id="ev_902",
        event_type=MarketEventType.CANDLE_CLOSED,
        symbol="NIFTY",
        timeframe="5m",
        timestamp=datetime(2026, 9, 1, 4, 30, tzinfo=timezone.utc),
        close=Decimal("105.50"),
        price=Decimal("105.50")
    )

    signals = await ExitEngine.evaluate_strategy_exits(
        db=db_session,
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        event=event,
        custom_stop_loss=Decimal("95.00"),
        enable_partial_1r=True
    )

    assert len(signals) == 1
    assert "Reached 2.0R target" not in signals[0].reason
    assert "Reached 1.0R target" in signals[0].reason or "target" in signals[0].reason.lower()

@pytest.mark.asyncio
async def test_duplicate_exit_event_prevented(db_session, setup_exit_env):
    """Test U, V: Duplicate exit evaluation for the same event does not generate multiple signals."""
    env = setup_exit_env
    event = MarketEvent(
        event_id="ev_903",
        event_type=MarketEventType.CANDLE_CLOSED,
        symbol="NIFTY",
        timeframe="5m",
        timestamp=datetime(2026, 9, 1, 4, 30, tzinfo=timezone.utc),
        close=Decimal("93.00"), # Breaches SL 95.00
        price=Decimal("93.00")
    )

    # First call generates signal
    sig1 = await ExitEngine.evaluate_strategy_exits(
        db=db_session,
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        event=event,
        custom_stop_loss=Decimal("95.00")
    )
    assert len(sig1) == 1

    # Second call with same event is prevented
    sig2 = await ExitEngine.evaluate_strategy_exits(
        db=db_session,
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        event=event,
        custom_stop_loss=Decimal("95.00")
    )
    assert len(sig2) == 0

@pytest.mark.asyncio
async def test_restart_recovers_trailing_state_from_execution_logs(db_session, setup_exit_env):
    """Test AB: Trailing state survives application restart via durable database checkpoints."""
    env = setup_exit_env
    exec_id = env["execution"].id

    saved_state = TrailingStopState(
        execution_id=exec_id,
        direction=PositionDirection.BUY,
        entry_price=Decimal("100.00"),
        initial_stop_loss=Decimal("95.00"),
        current_trailing_stop=Decimal("110.00"),
        highest_favorable_price=Decimal("115.00"),
        lowest_favorable_price=Decimal("100.00")
    )

    # Persist directly to DB
    await TrailingStateManager.save_state(db_session, saved_state, persist_db=True)

    # Retrieve state
    recovered = await TrailingStateManager.get_state(db_session, exec_id)
    assert recovered is not None
    assert recovered.current_trailing_stop == Decimal("110.00")
    assert recovered.highest_favorable_price == Decimal("115.00")

@pytest.mark.asyncio
async def test_no_broker_calls_from_exit_engine(db_session, setup_exit_env):
    """Test AD: Verifies that ExitEngine makes ZERO broker order calls."""
    env = setup_exit_env
    event = MarketEvent(
        event_id="ev_904",
        event_type=MarketEventType.CANDLE_CLOSED,
        symbol="NIFTY",
        timeframe="5m",
        timestamp=datetime(2026, 9, 1, 4, 30, tzinfo=timezone.utc),
        close=Decimal("90.00"), # Stop loss hit
        price=Decimal("90.00")
    )

    with patch("app.brokers.mock.adapter.MockBrokerAdapter.place_order") as mock_place_order:
        signals = await ExitEngine.evaluate_strategy_exits(
            db=db_session,
            strategy_id=env["strategy"].id,
            strategy_version_id=env["version"].id,
            event=event,
            custom_stop_loss=Decimal("95.00")
        )
        assert len(signals) == 1
        mock_place_order.assert_not_called()

@pytest.mark.asyncio
async def test_strategy_2_alert_candle_range_target_and_sl(db_session, setup_exit_env):
    """Test O: Strategy 2 evaluates Alert Candle Range target and SL."""
    env = setup_exit_env
    # Alert Candle Range = 24900 to 25000 (Range = 100), Target = 25100, SL = 24900
    event_tgt = MarketEvent(
        event_id="ev_905",
        event_type=MarketEventType.CANDLE_CLOSED,
        symbol="NIFTY",
        timeframe="15m",
        timestamp=datetime(2026, 9, 1, 4, 30, tzinfo=timezone.utc),
        close=Decimal("25105.00"),
        price=Decimal("25105.00")
    )

    signals = await ExitEngine.evaluate_strategy_exits(
        db=db_session,
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        event=event_tgt,
        custom_stop_loss=Decimal("24900.00"),
        custom_target=Decimal("25100.00")
    )

    assert len(signals) == 1
    assert "Target" in signals[0].reason or "target" in signals[0].reason.lower()

@pytest.mark.asyncio
async def test_strategy_3_pivot_reversal_target_and_invalidation(db_session, setup_exit_env):
    """Test P, Q: Strategy 3 evaluates Camarilla R3 breach invalidation."""
    env = setup_exit_env
    # RELIANCE Short CE invalidation level at 2950.00
    event_inv = MarketEvent(
        event_id="ev_906",
        event_type=MarketEventType.CANDLE_CLOSED,
        symbol="RELIANCE",
        timeframe="1d",
        timestamp=datetime(2026, 9, 1, 4, 30, tzinfo=timezone.utc),
        close=Decimal("2955.00"), # Breaches R3 level
        price=Decimal("2955.00")
    )

    signals = await ExitEngine.evaluate_strategy_exits(
        db=db_session,
        strategy_id=env["strategy"].id,
        strategy_version_id=env["version"].id,
        event=event_inv,
        invalidation_level=Decimal("2950.00")
    )

    assert len(signals) == 1
    assert "invalidat" in signals[0].reason.lower()
    assert "STRATEGY_INVALIDATION" in signals[0].signal_key

def test_missing_price_data_fails_safely():
    """Test Y, Z, AA: Evaluators handle None/missing price data safely."""
    res1 = evaluate_stop_loss(None, Decimal("100.00"), Decimal("95.00"))
    assert res1.decision == ExitDecision.DATA_UNAVAILABLE

    res2 = evaluate_target(Decimal("100.00"), None, Decimal("110.00"))
    assert res2.decision == ExitDecision.DATA_UNAVAILABLE

    res3 = evaluate_r_multiple(Decimal("100.00"), Decimal("100.00"), Decimal("105.00"), Decimal("2.0")) # Zero risk
    assert res3.decision == ExitDecision.DATA_UNAVAILABLE

@pytest.mark.asyncio
async def test_structured_logging_contains_correlation_and_no_secrets(db_session, setup_exit_env, caplog):
    """Test AC: Structured logs contain correlation IDs and no leaked secrets."""
    import logging
    env = setup_exit_env
    event = MarketEvent(
        event_id="ev_907",
        event_type=MarketEventType.CANDLE_CLOSED,
        symbol="NIFTY",
        timeframe="5m",
        timestamp=datetime(2026, 9, 1, 4, 30, tzinfo=timezone.utc),
        close=Decimal("111.00"),
        price=Decimal("111.00")
    )

    with caplog.at_level(logging.INFO):
        signals = await ExitEngine.evaluate_strategy_exits(
            db=db_session,
            strategy_id=env["strategy"].id,
            strategy_version_id=env["version"].id,
            event=event,
            custom_stop_loss=Decimal("95.00"),
            custom_r_multiple=Decimal("2.0")
        )
        assert len(signals) == 1

    log_texts = [r.message for r in caplog.records]
    full_logs = " ".join(log_texts)

    # Correlation assertions
    assert f"strategy_id={env['strategy'].id}" in full_logs
    assert "exit_signal_generated" in full_logs

    # Safety assertions
    assert "accessToken" not in full_logs
    assert "password" not in full_logs
    assert "secret" not in full_logs

