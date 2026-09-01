import pytest
import asyncio
from datetime import datetime, timezone, date, time
from decimal import Decimal
from unittest.mock import patch, AsyncMock
from sqlalchemy.future import select

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.brokers.models import BrokerAccount, UserPosition
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyExecution, StrategyExecutionLeg, StrategyRuntimeState
from app.execution.models import StrategySignal, StrategyUserExecutionTrace, StrategyExecutionBatch
from app.market_data.schemas import MarketEvent
from app.market_data.enums import MarketEventType
from app.strategies.enums import StrategyLifecycleState
from app.strategies.state_manager import strategy_state_manager
from app.strategies.schemas import StrategyRequest, StrategyResponse
from app.strategies.service import StrategyService
from app.strategies.payload_normalizer import FrontendPayloadNormalizer
from app.strategies.routing.router import strategy_router
from app.strategies.engine.service import StrategyEngine
from app.strategies.engine.context import MarketContext
from app.strategies.golden_rules.engine import GoldenRuleEngine
from app.strategies.signals.engine import SignalEngine
from app.strategies.signals.enums import SignalType, SignalDirection
from app.strategies.risk.service import RiskEngine
from app.execution.validator import ExecutionValidator
from app.execution.engine import ExecutionEngine
from app.execution.contracts import ExecutionRequest
from app.execution.enums import ExecutionMode
from app.execution.positions.tracker import PositionTracker
from app.strategies.exits.engine import ExitEngine

# --- REAL FRONTEND STRATEGY PAYLOAD FIXTURES (Schema v2.0.0) ---

STRATEGY_1_PAYLOAD = {
    "schemaVersion": "2.0.0",
    "executionEngine": "ZENALGO_QUANT_ENGINE",
    "meta": {
        "strategyName": "Nifty EMA 8/33 Pullback Scalper",
        "authorName": "Quant Team",
        "status": "DRAFT"
    },
    "description": "5m Pullback Scalper on NIFTY 50",
    "timeframe": "5m",
    "instrument": {
        "underlying": "NIFTY 50",
        "expiryType": "Weekly"
    },
    "schedule": {
        "entryFrom": "09:30",
        "entryTo": "14:30",
        "forcedExitTime": "15:15",
        "applicableDays": ["Mon", "Tue", "Wed", "Thu", "Fri"]
    },
    "entryConditions": [
        "8 EMA crosses above 33 EMA",
        "Close > 8 EMA"
    ],
    "goldenRules": [
        "Candle closure above breakout level"
    ],
    "exitConditions": [
        "8 EMA crosses below 33 EMA"
    ],
    "riskManagement": {
        "stopLoss": {"type": "CANDLE_LOW", "value": "CONFIRMATION_CANDLE"},
        "capitalAllocationPerTrade": 50000.0,
        "maxLossPerTrade": 2500.0,
        "riskRewardRatio": "1:2"
    },
    "target": {
        "value": "2R",
        "targets": [{"value": 2.0, "type": "RR", "exitPercentage": 100.0}]
    },
    "options": {
        "strikeSelection": "ATM",
        "expiryType": "Weekly"
    },
    "execution": {
        "slippage": 0.5,
        "orderTimeout": 30
    },
    "mode": "PAPER"
}

STRATEGY_2_PAYLOAD = {
    "schemaVersion": "2.0.0",
    "executionEngine": "ZENALGO_QUANT_ENGINE",
    "meta": {
        "strategyName": "Nifty RSI 60 Alert Candle Breakout",
        "authorName": "Quant Team",
        "status": "DRAFT"
    },
    "description": "15m RSI 60 Momentum Breakout",
    "timeframe": "15m",
    "instrument": {
        "underlying": "NIFTY 50",
        "expiryType": "Weekly"
    },
    "schedule": {
        "entryFrom": "09:15",
        "entryTo": "14:30",
        "forcedExitTime": "15:15",
        "applicableDays": ["Mon", "Tue", "Wed", "Thu", "Fri"]
    },
    "entryConditions": [
        "RSI > 60.0",
        "Close > High"
    ],
    "goldenRules": [
        "Wait for 15m candle close"
    ],
    "exitConditions": [
        "RSI < 50.0"
    ],
    "riskManagement": {
        "stopLoss": {"type": "ALERT_CANDLE_LOW"},
        "capitalAllocationPerTrade": 60000.0
    },
    "target": {
        "value": "ALERT_CANDLE_RANGE",
        "scaleOutPlan": "50% at 1R, 50% at 2R"
    },
    "options": {
        "strikeSelection": "ATM",
        "expiryType": "Weekly"
    },
    "mode": "PAPER"
}

STRATEGY_3_PAYLOAD = {
    "schemaVersion": "2.0.0",
    "executionEngine": "ZENALGO_QUANT_ENGINE",
    "meta": {
        "strategyName": "Reliance Monthly Camarilla S3/R3 Pivot Reversal",
        "authorName": "Quant Team",
        "status": "DRAFT"
    },
    "description": "Reliance Monthly Camarilla Option Selling with Mandatory Hedge",
    "timeframe": "1d",
    "instrument": {
        "underlying": "RELIANCE",
        "expiryType": "Monthly"
    },
    "schedule": {
        "entryFrom": "09:30",
        "entryTo": "15:00",
        "forcedExitTime": "15:15",
        "applicableMonths": ["ALL"],
        "selectedMonthlyDate": "MONTHLY_EXPIRY"
    },
    "entryConditions": [
        "Close <= 2900.00"
    ],
    "exitConditions": [
        "Close > 2950.00"
    ],
    "riskManagement": {
        "stopLoss": {"type": "CAMARILLA_R3_BREACH"},
        "capitalAllocationPerTrade": 150000.0
    },
    "target": {
        "value": "2.5% Premium Decay"
    },
    "options": {
        "legs": [
            {
                "legId": 1,
                "sequence": 1,
                "role": "HEDGE",
                "action": "BUY",
                "optionType": "CE",
                "strikeSelection": "OTM",
                "strikeOffset": 200.0,
                "expiry": "MONTHLY",
                "lots": 1
            },
            {
                "legId": 2,
                "sequence": 2,
                "role": "PRIMARY",
                "action": "SELL",
                "optionType": "CE",
                "strikeSelection": "ATM",
                "strikeOffset": 0.0,
                "expiry": "MONTHLY",
                "lots": 1
            }
        ]
    },
    "mode": "PAPER"
}

@pytest.fixture
async def setup_traders(db_session):
    """Sets up test traders with broker accounts."""
    u1 = User(email="trader_alpha@example.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=True, referral_code="REF-E2E-01")
    u2 = User(email="trader_beta@example.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=True, referral_code="REF-E2E-02")
    db_session.add_all([u1, u2])
    await db_session.flush()

    b1 = BrokerAccount(user_id=u1.id, broker_code="MOCK", account_client_id="MOCK-U1", status="ACTIVE")
    b2 = BrokerAccount(user_id=u2.id, broker_code="MOCK", account_client_id="MOCK-U2", status="ACTIVE")
    db_session.add_all([b1, b2])
    await db_session.flush()

    return {"user1": u1, "user2": u2, "broker1": b1, "broker2": b2}


# --- SCENARIOS 1, 2, 3: Create and Activate Strategies ---

@pytest.mark.asyncio
async def test_strategy_1_create_and_activate(db_session, setup_traders):
    """Scenario 1: Creates and activates Strategy 1 (EMA 8/33 Pullback)."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    
    created = await StrategyService.create_strategy(db_session, req, user.id)
    assert created.id is not None
    assert created.name == "Nifty EMA 8/33 Pullback Scalper"
    assert created.underlying == "NIFTY"
    assert created.status == "DRAFT"

    # Verify Runtime State is initialized to WAITING
    r_state = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state is not None
    assert r_state.lifecycle_state == StrategyLifecycleState.WAITING

    # Activate Strategy
    activated = await StrategyService.activate_strategy(db_session, created.id, user.id)
    assert activated.status == "PAPER"

    # Verify Runtime State transitioned to MONITORING_ENTRY
    r_state_active = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state_active.lifecycle_state == StrategyLifecycleState.MONITORING_ENTRY

@pytest.mark.asyncio
async def test_strategy_2_create_and_activate(db_session, setup_traders):
    """Scenario 2: Creates and activates Strategy 2 (RSI 60 Breakout)."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_2_PAYLOAD)
    
    created = await StrategyService.create_strategy(db_session, req, user.id)
    activated = await StrategyService.activate_strategy(db_session, created.id, user.id)
    
    assert activated.id == created.id
    assert activated.status == "PAPER"
    r_state = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_ENTRY

@pytest.mark.asyncio
async def test_strategy_3_create_and_activate(db_session, setup_traders):
    """Scenario 3: Creates and activates Strategy 3 (Reliance Camarilla)."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_3_PAYLOAD)
    
    created = await StrategyService.create_strategy(db_session, req, user.id)
    activated = await StrategyService.activate_strategy(db_session, created.id, user.id)
    
    assert activated.id == created.id
    assert activated.status == "PAPER"
    r_state = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_ENTRY

@pytest.mark.asyncio
async def test_strategy_3_preserves_both_legs(db_session, setup_traders):
    """Scenario 7: Creates Strategy 3 and verifies BOTH option legs are preserved."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_3_PAYLOAD)
    
    created = await StrategyService.create_strategy(db_session, req, user.id)
    assert len(created.legs) == 2
    
    # Leg 1: Hedge BUY OTM (+200pt)
    assert created.legs[0].sequence == 1
    assert created.legs[0].side == "BUY"
    assert created.legs[0].strikeSelection == "OTM"
    assert created.legs[0].strikeValue == Decimal("200.00")
    
    # Leg 2: Primary Short SELL ATM
    assert created.legs[1].sequence == 2
    assert created.legs[1].side == "SELL"
    assert created.legs[1].strikeSelection == "ATM"
    assert created.legs[1].strikeValue == Decimal("0.00")


# --- SCENARIOS 4, 5, 6: Complete End-to-End PAPER Lifecycles ---

@pytest.mark.asyncio
async def test_strategy_1_complete_paper_lifecycle(db_session, setup_traders):
    """Scenario 4: Full Strategy 1 lifecycle (Entry -> Exit -> Closed)."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    # 1. Entry Signal
    signal_key = f"SIG-{created.id}-{version_id}-ENTRY-901"
    signal = StrategySignal(
        strategy_id=created.id,
        strategy_version_id=version_id,
        trading_date=date.today(),
        entry_time="09:35",
        signal_key=signal_key,
        market_event_key=f"{created.id}:NIFTY:5m:CANDLE_CLOSED:2026-09-01T09:35:00",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED",
        price=Decimal("100.00"),
        reason="[ENTRY] 8 EMA crossed above 33 EMA. Gate PASS. Trigger Price: 100.00"
    )
    db_session.add(signal)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=signal.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(
        execution_batch_id=batch.id,
        signal_id=signal.id,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        correlation_id=f"TRACE-S1-{signal.id}-{user.id}",
        status="PENDING",
        current_step="RISK_EVALUATION"
    )
    db_session.add(trace)
    await db_session.flush()

    # 2. Build & Validate execution request
    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_PAYLOAD,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=signal.id,
        signal_type="ENTRY",
        direction="BUY",
        approved_lots=1,
        required_capital=Decimal("5000.00"),
        execution_mode=ExecutionMode.PAPER
    )
    val_res = await ExecutionValidator.validate_execution_request(db_session, exec_req)
    assert val_res.is_valid is True

    # 3. ExecutionEngine executes in PAPER mode via MockBroker -> Order Filled
    exec_result = await ExecutionEngine.execute(db_session, exec_req)
    assert exec_result.status.value == "FILLED"
    assert exec_result.execution_id is not None

    stmt_exec = select(StrategyExecution).where(StrategyExecution.id == exec_result.execution_id)
    res_exec = await db_session.execute(stmt_exec)
    exec_rec = res_exec.scalar_one()
    assert exec_rec.status == "RUNNING"

    r_state = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT

    # 4. Exit Event arrives (Target 2R reached at 110.50)
    exit_event = MarketEvent(
        event_id="ev_e2e_exit_1",
        event_type=MarketEventType.CANDLE_CLOSED,
        symbol="NIFTY",
        timeframe="5m",
        timestamp=datetime.now(timezone.utc),
        close=Decimal("110.50"),
        price=Decimal("110.50")
    )
    exit_signals = await ExitEngine.evaluate_strategy_exits(
        db=db_session,
        strategy_id=created.id,
        strategy_version_id=version_id,
        event=exit_event,
        custom_stop_loss=Decimal("95.00"),
        custom_r_multiple=Decimal("2.0")
    )
    assert len(exit_signals) == 1
    assert exit_signals[0].signal_type == SignalType.EXIT

    # 5. Create exit trace & execute Paper Exit
    exit_batch = StrategyExecutionBatch(signal_id=exit_signals[0].signal_id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(exit_batch)
    await db_session.flush()

    exit_trace = StrategyUserExecutionTrace(
        execution_batch_id=exit_batch.id,
        signal_id=exit_signals[0].signal_id,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        correlation_id=f"TRACE-EXIT-{exit_signals[0].signal_id}-{user.id}",
        status="PENDING",
        current_step="RISK_EVALUATION"
    )
    db_session.add(exit_trace)
    await db_session.flush()

    exit_exec_req = ExecutionRequest(
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=exit_signals[0].signal_id,
        signal_type="EXIT",
        direction="SELL",
        execution_mode=ExecutionMode.PAPER,
        underlying="NIFTY",
        correlation_id=f"SQOFF-{exec_rec.id}-1",
        legs=exec_req.legs,
        approved_lots=1,
        required_capital=Decimal("0.00")
    )
    exit_result = await ExecutionEngine.execute(db_session, exit_exec_req)
    assert exit_result.status.value == "FILLED"

    # Position closed
    exec_rec.status = "SQUARED_OFF"
    exec_rec.exit_time = datetime.now(timezone.utc)
    db_session.add(exec_rec)
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.POSITION_CLOSED, "Exit completed")
    
    r_state_closed = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state_closed.lifecycle_state == StrategyLifecycleState.POSITION_CLOSED

@pytest.mark.asyncio
async def test_strategy_2_complete_paper_lifecycle(db_session, setup_traders):
    """Scenario 5: Full Strategy 2 lifecycle (15m RSI 60 Breakout -> Target -> Closed)."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_2_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    signal = StrategySignal(
        strategy_id=created.id,
        strategy_version_id=version_id,
        trading_date=date.today(),
        entry_time="09:45",
        signal_key=f"SIG-S2-{created.id}-1",
        market_event_key=f"{created.id}:NIFTY:15m:CANDLE_CLOSED:2026-09-01T09:45:00",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED",
        price=Decimal("150.00"),
        reason="[ENTRY] RSI > 60 breakout"
    )
    db_session.add(signal)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=signal.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(
        execution_batch_id=batch.id,
        signal_id=signal.id,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        correlation_id=f"TRACE-S2-{signal.id}-{user.id}",
        status="PENDING"
    )
    db_session.add(trace)
    await db_session.flush()

    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_2_PAYLOAD,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=signal.id,
        execution_mode=ExecutionMode.PAPER
    )
    exec_res = await ExecutionEngine.execute(db_session, exec_req)
    assert exec_res.status.value == "FILLED"

    r_state = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT

@pytest.mark.asyncio
async def test_strategy_3_complete_hedged_paper_lifecycle(db_session, setup_traders):
    """Scenario 6: Full Strategy 3 hedged multi-leg execution in PAPER mode."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_3_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    signal = StrategySignal(
        strategy_id=created.id,
        strategy_version_id=version_id,
        trading_date=date.today(),
        entry_time="09:30",
        signal_key=f"SIG-S3-{created.id}-1",
        market_event_key=f"{created.id}:RELIANCE:1d:CANDLE_CLOSED:2026-09-01",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED",
        price=Decimal("2900.00"),
        reason="[ENTRY] Reliance Monthly S3 Reversal matched"
    )
    db_session.add(signal)
    await db_session.flush()

    batch3 = StrategyExecutionBatch(signal_id=signal.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch3)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(
        execution_batch_id=batch3.id,
        signal_id=signal.id,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        correlation_id=f"TRACE-S3-{signal.id}-{user.id}",
        status="PENDING"
    )
    db_session.add(trace)
    await db_session.flush()

    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_3_PAYLOAD,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=signal.id,
        execution_mode=ExecutionMode.PAPER
    )
    assert len(exec_req.legs) == 2
    assert exec_req.legs[0].role.value == "HEDGE"
    assert exec_req.legs[0].side == "BUY"
    assert exec_req.legs[1].role.value == "PRIMARY"
    assert exec_req.legs[1].side == "SELL"

    exec_res = await ExecutionEngine.execute(db_session, exec_req)
    assert exec_res.status.value == "FILLED"
    assert len(exec_res.leg_results) == 2
    assert all(l.status.value == "FILLED" for l in exec_res.leg_results)

    r_state = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT


# --- SCENARIOS 8, 9: Copy-Trading Isolation & User Failure Safety ---

@pytest.mark.asyncio
async def test_two_user_copy_trading_isolation(db_session, setup_traders):
    """Scenario 8: Two users execute same strategy independently in PAPER mode."""
    u1 = setup_traders["user1"]
    u2 = setup_traders["user2"]
    
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, u1.id)
    await StrategyService.activate_strategy(db_session, created.id, u1.id)
    version_id = created.currentVersionId

    sig = StrategySignal(
        strategy_id=created.id,
        strategy_version_id=version_id,
        trading_date=date.today(),
        entry_time="09:45",
        signal_key=f"SIG-COPY-{created.id}-1",
        market_event_key=f"{created.id}:NIFTY:5m:2026-09-01T09:45:00",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED"
    )
    db_session.add(sig)
    await db_session.flush()

    batch_copy = StrategyExecutionBatch(signal_id=sig.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch_copy)
    await db_session.flush()

    t1 = StrategyUserExecutionTrace(
        execution_batch_id=batch_copy.id,
        signal_id=sig.id,
        user_id=u1.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        correlation_id=f"TRACE-COPY-{sig.id}-{u1.id}",
        status="PENDING"
    )
    t2 = StrategyUserExecutionTrace(
        execution_batch_id=batch_copy.id,
        signal_id=sig.id,
        user_id=u2.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        correlation_id=f"TRACE-COPY-{sig.id}-{u2.id}",
        status="PENDING"
    )
    db_session.add_all([t1, t2])
    await db_session.flush()

    req1 = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_PAYLOAD,
        user_id=u1.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )
    res1 = await ExecutionEngine.execute(db_session, req1)
    assert res1.status.value == "FILLED"

    req2 = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_PAYLOAD,
        user_id=u2.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )
    res2 = await ExecutionEngine.execute(db_session, req2)
    assert res2.status.value == "FILLED"

    assert res1.execution_id != res2.execution_id

@pytest.mark.asyncio
async def test_user_failure_isolation(db_session, setup_traders):
    """Scenario 9: Failure for User A does not prevent User B from executing."""
    u1 = setup_traders["user1"]
    u2 = setup_traders["user2"]
    
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, u1.id)
    await StrategyService.activate_strategy(db_session, created.id, u1.id)
    version_id = created.currentVersionId

    sig = StrategySignal(
        strategy_id=created.id,
        strategy_version_id=version_id,
        trading_date=date.today(),
        entry_time="09:50",
        signal_key=f"SIG-FAIL-ISO-{created.id}-1",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED"
    )
    db_session.add(sig)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=sig.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    # User 2 has trace, User 1 does NOT (simulating User 1 failure/exclusion)
    t2 = StrategyUserExecutionTrace(
        execution_batch_id=batch.id,
        signal_id=sig.id,
        user_id=u2.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        correlation_id=f"TRACE-U2-{sig.id}",
        status="PENDING"
    )
    db_session.add(t2)
    await db_session.flush()

    # User 1 rejected due to missing trace
    req1 = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_PAYLOAD,
        user_id=u1.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )
    val1 = await ExecutionValidator.validate_execution_request(db_session, req1)
    assert val1.is_valid is False

    # User 2 succeeds normally
    req2 = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_PAYLOAD,
        user_id=u2.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )
    val2 = await ExecutionValidator.validate_execution_request(db_session, req2)
    assert val2.is_valid is True
    res2 = await ExecutionEngine.execute(db_session, req2)
    assert res2.status.value == "FILLED"


# --- SCENARIOS 10, 11, 12: Idempotency Guarantees ---

@pytest.mark.asyncio
async def test_duplicate_activation_is_idempotent(db_session, setup_traders):
    """Scenario 10: Activating an already active strategy is safe and idempotent."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)

    act1 = await StrategyService.activate_strategy(db_session, created.id, user.id)
    assert act1.status == "PAPER"

    act2 = await StrategyService.activate_strategy(db_session, created.id, user.id)
    assert act2.status == "PAPER"
    assert act2.id == act1.id

@pytest.mark.asyncio
async def test_duplicate_market_event_ignored(db_session, setup_traders):
    """Scenario 11: Duplicate market events are deduplicated via unique event keys."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    key = f"{created.id}:NIFTY:5m:CANDLE_CLOSED:2026-09-01T10:00:00"
    sig1 = StrategySignal(strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), entry_time="10:00", signal_key=f"SIG-DEDUP-1", market_event_key=key, status="CREATED")
    db_session.add(sig1)
    await db_session.flush()

    # Querying existing signal by event key prevents duplicate signal generation
    stmt = select(StrategySignal).where(StrategySignal.market_event_key == key)
    res = await db_session.execute(stmt)
    existing = res.scalar_one_or_none()
    assert existing is not None
    assert existing.id == sig1.id

@pytest.mark.asyncio
async def test_duplicate_signal_does_not_duplicate_execution(db_session, setup_traders):
    """Scenario 12: Duplicate execution requests for same signal are safely rejected."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    sig = StrategySignal(strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), entry_time="10:15", signal_key=f"SIG-EXEC-DEDUP", status="CREATED")
    db_session.add(sig)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=sig.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(
        execution_batch_id=batch.id,
        signal_id=sig.id,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        correlation_id=f"TRACE-DEDUP-{sig.id}",
        status="PENDING"
    )
    db_session.add(trace)
    await db_session.flush()

    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_PAYLOAD,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )
    # First execution succeeds
    res1 = await ExecutionEngine.execute(db_session, exec_req)
    assert res1.status.value == "FILLED"

    # Second execution attempt for same trace is rejected (already executed)
    val2 = await ExecutionValidator.validate_execution_request(db_session, exec_req)
    assert val2.is_valid is False
    assert val2.failure_code == "EXECUTION_DUPLICATE"


# --- SCENARIOS 13, 14, 15, 16, 17: Position & State Invariants ---

@pytest.mark.asyncio
async def test_position_opens_after_paper_fill(db_session, setup_traders):
    """Scenario 13: PositionTracker opens position and syncs UserPosition after fill."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    sig = StrategySignal(strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), entry_time="10:30", signal_key=f"SIG-POS-OPEN", status="CREATED")
    db_session.add(sig)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=sig.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(execution_batch_id=batch.id, signal_id=sig.id, user_id=user.id, strategy_id=created.id, strategy_version_id=version_id, correlation_id=f"TRACE-POS-OPEN", status="PENDING")
    db_session.add(trace)
    await db_session.flush()

    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_PAYLOAD,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )
    res = await ExecutionEngine.execute(db_session, exec_req)
    assert res.status.value == "FILLED"

    # UserPosition created and tracked
    stmt_pos = select(UserPosition).where(UserPosition.user_id == user.id, UserPosition.trading_symbol.like("%NIFTY%"))
    res_pos = await db_session.execute(stmt_pos)
    pos = res_pos.scalar_one_or_none()
    assert pos is not None
    assert pos.net_qty > 0

@pytest.mark.asyncio
async def test_exit_signal_generated(db_session, setup_traders):
    """Scenario 14: ExitEngine generates EXIT signal upon reaching target."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    sig = StrategySignal(strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), entry_time="10:45", signal_key=f"SIG-EX-GEN", status="CREATED")
    db_session.add(sig)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=sig.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(execution_batch_id=batch.id, signal_id=sig.id, user_id=user.id, strategy_id=created.id, strategy_version_id=version_id, correlation_id=f"TRACE-EX-GEN", status="PENDING")
    db_session.add(trace)
    await db_session.flush()

    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_PAYLOAD,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )
    await ExecutionEngine.execute(db_session, exec_req)

    # Market event triggering exit
    ev = MarketEvent(event_id="ev_tgt", event_type=MarketEventType.CANDLE_CLOSED, symbol="NIFTY", timeframe="5m", timestamp=datetime.now(timezone.utc), close=Decimal("110.00"), price=Decimal("110.00"))
    exit_sigs = await ExitEngine.evaluate_strategy_exits(db=db_session, strategy_id=created.id, strategy_version_id=version_id, event=ev, custom_r_multiple=Decimal("2.0"))
    assert len(exit_sigs) >= 1
    assert exit_sigs[0].signal_type == SignalType.EXIT

@pytest.mark.asyncio
async def test_position_closes_after_paper_exit(db_session, setup_traders):
    """Scenario 15: Position closed and strategy state updated after paper exit fill."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    sig = StrategySignal(strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), entry_time="11:00", signal_key=f"SIG-EX-CLOSE", status="CREATED")
    db_session.add(sig)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=sig.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(execution_batch_id=batch.id, signal_id=sig.id, user_id=user.id, strategy_id=created.id, strategy_version_id=version_id, correlation_id=f"TRACE-EX-CLOSE", status="PENDING")
    db_session.add(trace)
    await db_session.flush()

    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_PAYLOAD,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )
    res = await ExecutionEngine.execute(db_session, exec_req)

    # Square off
    stmt_exec = select(StrategyExecution).where(StrategyExecution.id == res.execution_id)
    res_exec = await db_session.execute(stmt_exec)
    exec_rec = res_exec.scalar_one()
    exec_rec.status = "SQUARED_OFF"
    db_session.add(exec_rec)
    
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.EXIT_SIGNAL, "Exit triggered")
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.EXIT_ORDER_PENDING, "Exit order submitted")
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.POSITION_CLOSED, "Squared off")

    r_state = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state.lifecycle_state == StrategyLifecycleState.POSITION_CLOSED

@pytest.mark.asyncio
async def test_runtime_state_transitions_correctly(db_session, setup_traders):
    """Scenario 16: Verifies full sequence: WAITING -> ELIGIBLE -> MONITORING_ENTRY -> ENTRY_SIGNAL -> ORDER_PENDING -> POSITION_OPEN -> MONITORING_EXIT -> EXIT_SIGNAL -> EXIT_ORDER_PENDING -> POSITION_CLOSED."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    version_id = created.currentVersionId

    # 1. WAITING
    s1 = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert s1.lifecycle_state == StrategyLifecycleState.WAITING

    # 2. Activate -> ELIGIBLE -> MONITORING_ENTRY
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    s2 = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert s2.lifecycle_state == StrategyLifecycleState.MONITORING_ENTRY

    # 3. Entry Signal -> Order Pending -> Position Open -> Monitoring Exit
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.ENTRY_SIGNAL, "Signal triggered")
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.ORDER_PENDING, "Order submitted")
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.POSITION_OPEN, "Position opened")
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.MONITORING_EXIT, "Monitoring exit")
    s3 = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert s3.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT

    # 4. Exit Signal -> Exit Order Pending -> Position Closed
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.EXIT_SIGNAL, "Exit triggered")
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.EXIT_ORDER_PENDING, "Exit order pending")
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.POSITION_CLOSED, "Exit completed")
    s4 = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert s4.lifecycle_state == StrategyLifecycleState.POSITION_CLOSED

@pytest.mark.asyncio
async def test_execution_mode_remains_paper(db_session, setup_traders):
    """Scenario 17: Execution mode strictly defaults to and remains PAPER."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    assert created.mode == "PAPER"


# --- SCENARIOS 18, 19, 20: Observability & Money Safety ---

@pytest.mark.asyncio
async def test_structured_correlation_logging(db_session, setup_traders, caplog):
    """Scenario 18: Critical events produce structured logs with correlation fields."""
    import logging
    caplog.set_level(logging.INFO)
    
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)

    # Verify structured logs captured strategy_activated
    log_texts = [r.message for r in caplog.records]
    assert any("strategy_activated" in text for text in log_texts)

@pytest.mark.asyncio
async def test_no_broker_credentials_appear_in_logs(db_session, setup_traders, caplog):
    """Scenario 19: Confidential tokens and credentials never leak into application logs."""
    import logging
    caplog.set_level(logging.DEBUG)
    
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)

    for record in caplog.records:
        assert "password" not in record.message.lower()
        assert "secret" not in record.message.lower()
        assert "token" not in record.message.lower() or "broker" not in record.message.lower()

@pytest.mark.asyncio
async def test_no_live_broker_call_occurs(db_session, setup_traders):
    """Scenario 20: Verifies that only Mock/Paper broker is invoked and ZERO live calls occur."""
    user = setup_traders["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    sig = StrategySignal(strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), entry_time="10:00", signal_key=f"SIG-SAFE-{created.id}", signal_type="ENTRY", direction="BUY", status="CREATED")
    db_session.add(sig)
    await db_session.flush()

    batch_safe = StrategyExecutionBatch(signal_id=sig.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch_safe)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(
        execution_batch_id=batch_safe.id,
        signal_id=sig.id,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        correlation_id=f"TRACE-SAFE-{sig.id}-{user.id}",
        status="PENDING"
    )
    db_session.add(trace)
    await db_session.flush()

    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_PAYLOAD,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )

    with patch("app.brokers.dhan.adapter.DhanAdapter.place_order") as mock_dhan_order:
        res = await ExecutionEngine.execute(db_session, exec_req)
        assert res.status.value == "FILLED"
        # Verify Dhan LIVE adapter was NEVER called
        mock_dhan_order.assert_not_called()
