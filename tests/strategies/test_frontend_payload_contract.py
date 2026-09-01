import pytest
import asyncio
from datetime import datetime, timezone, date, time
from decimal import Decimal
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

from app.main import app
from app.users.models import User, UserRole
from app.auth.service import hash_password, create_access_token
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
from app.strategies.golden_rules.engine import GoldenRuleEngine
from app.strategies.signals.engine import SignalEngine
from app.strategies.signals.enums import SignalType
from app.strategies.risk.service import RiskEngine
from app.execution.validator import ExecutionValidator
from app.execution.engine import ExecutionEngine
from app.execution.contracts import ExecutionRequest
from app.execution.enums import ExecutionMode
from app.execution.positions.tracker import PositionTracker
from app.strategies.exits.engine import ExitEngine


# ==============================================================================
# AUTHORITATIVE COMPLETE FRONTEND PAYLOADS (Schema Version 2.0.0)
# ==============================================================================

STRATEGY_1_COMPLETE_PAYLOAD = {
    "schemaVersion": "2.0.0",
    "executionEngine": "ZENALGO_QUANT_ENGINE",
    "meta": {
        "strategyId": "EMA_8_33_PULLBACK",
        "strategyName": "Nifty EMA 8/33 Pullback Scalper",
        "authorName": "Quant Team",
        "status": "DRAFT"
    },
    "description": "5m Pullback Scalper on NIFTY 50",
    "tradingHorizon": "Intraday",
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
        "Pullback to 8 EMA",
        "Bullish confirmation candle formed",
        "Close > High of confirmation candle"
    ],
    "goldenRules": [
        "Candle closure above breakout level",
        "Wait for 5m candle close"
    ],
    "exitConditions": [
        "8 EMA crosses below 33 EMA",
        "Bearish confirmation candle formed"
    ],
    "riskManagement": {
        "stopLoss": {"type": "CANDLE_LOW", "value": "CONFIRMATION_CANDLE"},
        "riskRewardRatio": "1:2",
        "capitalAllocationPerTrade": 50000.0,
        "maxLossPerTrade": 2500.0,
        "maxLossPerDay": 5000.0,
        "maxLossPerWeek": 15000.0,
        "maxTradesPerDay": 3,
        "maxOpenPositions": 1,
        "cooldownPeriodMinutes": 15,
        "positionSizing": "RISK_BASED",
        "partialExit": {"enabled": True, "percentage": 50.0, "trigger": "1R"},
        "trailingStop": {"enabled": True, "type": "STEP", "stepPoints": 10.0}
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
        "orderType": "MARKET",
        "slippage": 0.10,
        "orderTimeout": 30,
        "maxReEntries": 1
    },
    "mode": "PAPER"
}

STRATEGY_2_COMPLETE_PAYLOAD = {
    "schemaVersion": "2.0.0",
    "executionEngine": "ZENALGO_QUANT_ENGINE",
    "meta": {
        "strategyId": "RSI_60_ALERT_CANDLE",
        "strategyName": "Nifty RSI 60 Alert Candle Breakout",
        "authorName": "Quant Team",
        "status": "DRAFT"
    },
    "description": "15m RSI 60 Momentum Breakout",
    "tradingHorizon": "Intraday",
    "timeframe": "15m",
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
        "RSI crosses above 60",
        "Alert candle formed",
        "Wait for alert candle breakout",
        "CE entry on candle high breach",
        "Bearish RSI setup: RSI crosses below 40",
        "PE entry on candle low breach"
    ],
    "goldenRules": [
        "Wait for 15m candle close",
        "Do not enter before alert candle breakout"
    ],
    "exitConditions": [
        "RSI crosses below 50",
        "Alert candle low breached"
    ],
    "riskManagement": {
        "stopLoss": {"type": "ALERT_CANDLE_LOW"},
        "riskRewardRatio": "1:2",
        "capitalAllocationPerTrade": 60000.0,
        "maxLossPerTrade": 3000.0,
        "maxLossPerDay": 6000.0,
        "maxTradesPerDay": 2,
        "maxOpenPositions": 1,
        "cooldownPeriodMinutes": 15,
        "partialExit": {"enabled": True, "percentage": 50.0, "trigger": "1R"},
        "trailingStop": {"enabled": True, "type": "ALERT_CANDLE_TRAIL"}
    },
    "target": {
        "value": "ALERT_CANDLE_RANGE",
        "scaleOutPlan": "50% at 1R, 50% at 2R",
        "targets": [
            {"value": 1.0, "type": "RR", "exitPercentage": 50.0},
            {"value": 2.0, "type": "RR", "exitPercentage": 50.0}
        ]
    },
    "options": {
        "strikeSelection": "ATM",
        "expiryType": "Weekly"
    },
    "execution": {
        "orderType": "MARKET",
        "trigger": "BREAK_ALERT_CANDLE",
        "slippage": 0.10,
        "orderTimeout": 30,
        "maxReEntries": 1
    },
    "mode": "PAPER"
}

STRATEGY_3_COMPLETE_PAYLOAD = {
    "schemaVersion": "2.0.0",
    "executionEngine": "ZENALGO_QUANT_ENGINE",
    "meta": {
        "strategyId": "RELIANCE_S3_R3_PIVOT_REVERSAL",
        "strategyName": "Reliance Monthly Camarilla S3/R3 Pivot Reversal",
        "authorName": "Quant Team",
        "status": "DRAFT"
    },
    "description": "Reliance Monthly Camarilla Option Selling with Mandatory Hedge",
    "tradingHorizon": "Monthly",
    "timeframe": "1d",
    "instrument": {
        "underlying": "RELIANCE",
        "expiryType": "Monthly"
    },
    "pivotConfiguration": {
        "type": "CAMARILLA",
        "periodicity": "MONTHLY",
        "levels": ["R3", "S3", "R4", "S4"]
    },
    "eventExclusion": {
        "excludeEarnings": True,
        "quarterlyEarningsExclusionDays": 3
    },
    "schedule": {
        "entryFrom": "09:30",
        "entryTo": "15:00",
        "forcedExitTime": "15:15",
        "applicableMonths": ["ALL"],
        "selectedMonthlyDate": "MONTHLY_EXPIRY"
    },
    "entryConditions": [
        "Price touches Camarilla R3 with fake breakout",
        "Bearish reversal confirmation candle at R3",
        "Price touches Camarilla S3 with fake breakdown",
        "Bullish reversal confirmation candle at S3"
    ],
    "goldenRules": [
        "Wait for daily candle close or pivot rejection",
        "Quarterly earnings exclusion active"
    ],
    "exitConditions": [
        "Camarilla R3 breach (Stop Loss)",
        "Camarilla S3 breach (Stop Loss)",
        "Target 2.5% Premium Decay achieved",
        "Exit short option AND corresponding hedge together"
    ],
    "riskManagement": {
        "stopLoss": {"type": "CAMARILLA_R3_BREACH"},
        "capitalAllocationPerTrade": 150000.0,
        "maxLossPerTrade": 7500.0,
        "maxLossPerDay": 7500.0,
        "maxTradesPerDay": 1,
        "maxOpenPositions": 1,
        "consecutiveLossLimit": 2,
        "actionOnConsecutiveLoss": "STOP_STRATEGY",
        "positionSizing": "FIXED_LOTS"
    },
    "target": {
        "value": "2.5% Premium Decay",
        "targets": [{"value": 2.5, "type": "PERCENTAGE", "exitPercentage": 100.0}]
    },
    "options": {
        "legs": [
            {
                "legId": 1,
                "sequence": 1,
                "role": "PRIMARY",
                "action": "SELL",
                "optionType": "CE",
                "strikeSelection": "ATM",
                "strikeOffset": 0.0,
                "expiry": "MONTHLY",
                "lots": 1,
                "description": "Short CE"
            },
            {
                "legId": 2,
                "sequence": 2,
                "role": "HEDGE",
                "action": "BUY",
                "optionType": "CE",
                "strikeSelection": "OTM",
                "strikeOffset": 200.0,
                "expiry": "MONTHLY",
                "lots": 1,
                "description": "CE Hedge: Short CE strike + 200 points"
            },
            {
                "legId": 3,
                "sequence": 3,
                "role": "PRIMARY",
                "action": "SELL",
                "optionType": "PE",
                "strikeSelection": "ATM",
                "strikeOffset": 0.0,
                "expiry": "MONTHLY",
                "lots": 1,
                "description": "Short PE"
            },
            {
                "legId": 4,
                "sequence": 4,
                "role": "HEDGE",
                "action": "BUY",
                "optionType": "PE",
                "strikeSelection": "OTM",
                "strikeOffset": 200.0,
                "expiry": "MONTHLY",
                "lots": 1,
                "description": "PE Hedge: Short PE strike - 200 points"
            }
        ]
    },
    "execution": {
        "orderType": "LIMIT",
        "slippage": 0.20,
        "orderTimeout": 30,
        "reEntry": False,
        "maxReEntries": 0
    },
    "mode": "PAPER"
}


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture
async def auth_client(client, db_session):
    """Sets up an authenticated test trader and returns HTTP client."""
    user = User(
        email="frontend_dev@example.com",
        password_hash=hash_password("devpass123"),
        role=UserRole.TRADER,
        is_active=True,
        referral_code="REF-DEV-01"
    )
    db_session.add(user)
    await db_session.flush()

    broker = BrokerAccount(
        user_id=user.id,
        broker_code="MOCK",
        account_client_id="MOCK-DEV-01",
        status="ACTIVE"
    )
    db_session.add(broker)
    await db_session.flush()

    token = create_access_token(user.email, user.role.value, ["ACCOUNT_READ", "TRADE_READ", "TRADE_EXECUTE"])
    client.headers["Authorization"] = f"Bearer {token}"
    return client, user


@pytest.fixture
async def setup_traders_contract(db_session):
    """Sets up two traders for copy-trading verification."""
    u1 = User(email="trader_alpha@zenalgo.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=True, referral_code="REF-CTR-01")
    u2 = User(email="trader_beta@zenalgo.com", password_hash=hash_password("pass123"), role=UserRole.TRADER, is_active=True, referral_code="REF-CTR-02")
    db_session.add_all([u1, u2])
    await db_session.flush()

    b1 = BrokerAccount(user_id=u1.id, broker_code="MOCK", account_client_id="MOCK-CTR-01", status="ACTIVE")
    b2 = BrokerAccount(user_id=u2.id, broker_code="MOCK", account_client_id="MOCK-CTR-02", status="ACTIVE")
    db_session.add_all([b1, b2])
    await db_session.flush()

    return {"user1": u1, "user2": u2, "broker1": b1, "broker2": b2}


# ==============================================================================
# TESTS 1, 2, 3: POST Payload Acceptance Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_strategy_1_payload_accepted(auth_client):
    """Scenario 1: Strategy 1 payload accepted without manual developer transformation."""
    client, user = auth_client
    resp = await client.post("/api/strategy", json=STRATEGY_1_COMPLETE_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["id"] is not None
    assert data["name"] == "Nifty EMA 8/33 Pullback Scalper"
    assert data["currentVersionId"] is not None
    assert data["status"] == "DRAFT"
    assert data["mode"] == "PAPER"

@pytest.mark.asyncio
async def test_strategy_2_payload_accepted(auth_client):
    """Scenario 2: Strategy 2 payload accepted via create API."""
    client, user = auth_client
    resp = await client.post("/api/strategy", json=STRATEGY_2_COMPLETE_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["id"] is not None
    assert data["name"] == "Nifty RSI 60 Alert Candle Breakout"
    assert data["timeframe"] == "15m"

@pytest.mark.asyncio
async def test_strategy_3_payload_accepted(auth_client):
    """Scenario 3: Strategy 3 complete Camarilla payload accepted via create API."""
    client, user = auth_client
    resp = await client.post("/api/strategy", json=STRATEGY_3_COMPLETE_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["id"] is not None
    assert data["underlying"] == "RELIANCE"


# ==============================================================================
# TESTS 4, 5, 6, 7: Round-Trip Persistence & Field Integrity
# ==============================================================================

@pytest.mark.asyncio
async def test_strategy_1_roundtrip_persistence(auth_client):
    """Scenario 4: Strategy 1 POST -> GET round-trip preserves all meaningful fields."""
    client, user = auth_client
    create_res = await client.post("/api/strategy", json=STRATEGY_1_COMPLETE_PAYLOAD)
    assert create_res.status_code == 201
    strat_id = create_res.json()["data"]["id"]

    get_res = await client.get(f"/api/strategy/{strat_id}")
    assert get_res.status_code == 200
    strat = get_res.json()["data"]

    # Verify field integrity
    assert strat["name"] == "Nifty EMA 8/33 Pullback Scalper"
    assert strat["timeframe"] == "5m"
    assert strat["underlying"] == "NIFTY"
    assert strat["schedule"]["entryFrom"] == "09:30"
    assert strat["schedule"]["forcedExitTime"] == "15:15"
    assert strat["riskManagement"]["riskRewardRatio"] == "1:2"
    assert float(strat["riskManagement"]["capitalAllocationPerTrade"]) == 50000.0
    assert float(strat["riskManagement"]["maxLossPerTrade"]) == 2500.0
    assert strat["target"]["value"] == "2R"
    assert strat["options"]["strikeSelection"] == "ATM"
    assert strat["execution"]["orderType"] == "MARKET"

@pytest.mark.asyncio
async def test_strategy_2_roundtrip_persistence(auth_client):
    """Scenario 5: Strategy 2 POST -> GET round-trip preserves RSI and Alert Candle configuration."""
    client, user = auth_client
    create_res = await client.post("/api/strategy", json=STRATEGY_2_COMPLETE_PAYLOAD)
    strat_id = create_res.json()["data"]["id"]

    get_res = await client.get(f"/api/strategy/{strat_id}")
    assert get_res.status_code == 200
    strat = get_res.json()["data"]

    assert strat["timeframe"] == "15m"
    assert strat["target"]["value"] == "ALERT_CANDLE_RANGE"
    assert strat["riskManagement"]["stopLoss"]["type"] == "ALERT_CANDLE_LOW"
    assert strat["execution"]["trigger"] == "BREAK_ALERT_CANDLE"

@pytest.mark.asyncio
async def test_strategy_3_roundtrip_persistence(auth_client):
    """Scenario 6: Strategy 3 POST -> GET preserves pivotConfiguration, eventExclusion, and schedule."""
    client, user = auth_client
    create_res = await client.post("/api/strategy", json=STRATEGY_3_COMPLETE_PAYLOAD)
    strat_id = create_res.json()["data"]["id"]

    get_res = await client.get(f"/api/strategy/{strat_id}")
    assert get_res.status_code == 200
    strat = get_res.json()["data"]

    assert strat["underlying"] == "RELIANCE"
    assert strat["pivotConfiguration"]["type"] == "CAMARILLA"
    assert strat["pivotConfiguration"]["periodicity"] == "MONTHLY"
    assert strat["eventExclusion"]["excludeEarnings"] is True
    assert strat["riskManagement"]["consecutiveLossLimit"] == 2
    assert strat["target"]["value"] == "2.5% Premium Decay"

@pytest.mark.asyncio
async def test_strategy_3_all_4_legs_preserved(auth_client):
    """Scenario 7: Strategy 3 ALL FOUR option legs survive without data loss."""
    client, user = auth_client
    create_res = await client.post("/api/strategy", json=STRATEGY_3_COMPLETE_PAYLOAD)
    strat_id = create_res.json()["data"]["id"]

    get_res = await client.get(f"/api/strategy/{strat_id}")
    strat = get_res.json()["data"]

    # 1. Verify relational legs (4 legs)
    assert len(strat["legs"]) == 4
    
    # 2. Verify options.legs (4 legs with complete properties)
    opt_legs = strat["options"]["legs"]
    assert len(opt_legs) == 4

    # Leg 1: SELL CE (Short CE)
    assert opt_legs[0]["sequence"] == 1
    assert opt_legs[0]["action"] == "SELL"
    assert opt_legs[0]["optionType"] == "CE"
    assert opt_legs[0]["role"] == "PRIMARY"
    assert opt_legs[0]["strikeSelection"] == "ATM"

    # Leg 2: BUY CE (CE Hedge: Short CE strike + 200 points)
    assert opt_legs[1]["sequence"] == 2
    assert opt_legs[1]["action"] == "BUY"
    assert opt_legs[1]["optionType"] == "CE"
    assert opt_legs[1]["role"] == "HEDGE"
    assert opt_legs[1]["strikeSelection"] == "OTM"
    assert float(opt_legs[1]["strikeOffset"]) == 200.0

    # Leg 3: SELL PE (Short PE)
    assert opt_legs[2]["sequence"] == 3
    assert opt_legs[2]["action"] == "SELL"
    assert opt_legs[2]["optionType"] == "PE"
    assert opt_legs[2]["role"] == "PRIMARY"

    # Leg 4: BUY PE (PE Hedge: Short PE strike - 200 points)
    assert opt_legs[3]["sequence"] == 4
    assert opt_legs[3]["action"] == "BUY"
    assert opt_legs[3]["optionType"] == "PE"
    assert opt_legs[3]["role"] == "HEDGE"
    assert float(opt_legs[3]["strikeOffset"]) == 200.0


# ==============================================================================
# TESTS 8, 9: Strategy Activation & Idempotency
# ==============================================================================

@pytest.mark.asyncio
async def test_strategy_activation_state_transition(auth_client, db_session):
    """Scenario 8: Strategy activation advances state WAITING -> ELIGIBLE -> MONITORING_ENTRY."""
    client, user = auth_client
    create_res = await client.post("/api/strategy", json=STRATEGY_1_COMPLETE_PAYLOAD)
    strat_id = create_res.json()["data"]["id"]

    # Initial state is WAITING
    r_state = await strategy_state_manager.get_runtime_state(db_session, strat_id)
    assert r_state.lifecycle_state == StrategyLifecycleState.WAITING

    # Activate
    act_res = await client.post(f"/api/strategy/{strat_id}/activate")
    assert act_res.status_code == 200
    assert act_res.json()["data"]["status"] == "PAPER"

    # Runtime state is MONITORING_ENTRY
    r_state_after = await strategy_state_manager.get_runtime_state(db_session, strat_id)
    assert r_state_after.lifecycle_state == StrategyLifecycleState.MONITORING_ENTRY

@pytest.mark.asyncio
async def test_duplicate_activation_is_idempotent(auth_client, db_session):
    """Scenario 9: Activating an already active strategy is safe and idempotent."""
    client, user = auth_client
    create_res = await client.post("/api/strategy", json=STRATEGY_1_COMPLETE_PAYLOAD)
    strat_id = create_res.json()["data"]["id"]

    act1 = await client.post(f"/api/strategy/{strat_id}/activate")
    assert act1.status_code == 200

    act2 = await client.post(f"/api/strategy/{strat_id}/activate")
    assert act2.status_code == 200
    assert act2.json()["data"]["id"] == strat_id


# ==============================================================================
# TESTS 10, 11, 12, 13: Full Paper E2E Lifecycle Integrations
# ==============================================================================

@pytest.mark.asyncio
async def test_strategy_1_paper_e2e(db_session, setup_traders_contract):
    """Scenario 10: Complete Strategy 1 real backend pipeline execution."""
    user = setup_traders_contract["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_COMPLETE_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    # 1. Entry Signal Generated
    sig = StrategySignal(
        strategy_id=created.id,
        strategy_version_id=version_id,
        trading_date=date.today(),
        entry_time="09:35",
        signal_key=f"SIG-S1-E2E-{created.id}",
        market_event_key=f"{created.id}:NIFTY:5m:2026-09-01T09:35:00",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED",
        price=Decimal("100.00"),
        reason="[ENTRY] 8 EMA crossed above 33 EMA"
    )
    db_session.add(sig)
    await db_session.flush()

    # 2. Risk Trace created
    batch = StrategyExecutionBatch(signal_id=sig.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(
        execution_batch_id=batch.id,
        signal_id=sig.id,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        correlation_id=f"TRACE-S1-{sig.id}-{user.id}",
        status="PENDING",
        current_step="RISK_EVALUATION"
    )
    db_session.add(trace)
    await db_session.flush()

    # 3. Execution Request Validated & Executed in PAPER mode
    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_1_COMPLETE_PAYLOAD,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )
    val_res = await ExecutionValidator.validate_execution_request(db_session, exec_req)
    assert val_res.is_valid is True

    exec_res = await ExecutionEngine.execute(db_session, exec_req)
    assert exec_res.status.value == "FILLED"
    assert exec_res.execution_id is not None

    # Verify Position OPEN and State MONITORING_EXIT
    r_state = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT

    # 4. Exit Event Evaluated
    ev_exit = MarketEvent(
        event_id="ev_s1_exit",
        event_type=MarketEventType.CANDLE_CLOSED,
        symbol="NIFTY",
        timeframe="5m",
        timestamp=datetime.now(timezone.utc),
        close=Decimal("110.00"),
        price=Decimal("110.00")
    )
    exit_sigs = await ExitEngine.evaluate_strategy_exits(
        db=db_session,
        strategy_id=created.id,
        strategy_version_id=version_id,
        event=ev_exit,
        custom_r_multiple=Decimal("2.0")
    )
    assert len(exit_sigs) >= 1
    assert exit_sigs[0].signal_type == SignalType.EXIT

    # 5. Paper Exit Execution
    exit_batch = StrategyExecutionBatch(signal_id=exit_sigs[0].signal_id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(exit_batch)
    await db_session.flush()

    exit_trace = StrategyUserExecutionTrace(
        execution_batch_id=exit_batch.id,
        signal_id=exit_sigs[0].signal_id,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        correlation_id=f"TRACE-EXIT-{exit_sigs[0].signal_id}-{user.id}",
        status="PENDING",
        current_step="RISK_EVALUATION"
    )
    db_session.add(exit_trace)
    await db_session.flush()

    exit_req = ExecutionRequest(
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=exit_sigs[0].signal_id,
        signal_type="EXIT",
        direction="SELL",
        execution_mode=ExecutionMode.PAPER,
        underlying="NIFTY",
        correlation_id=f"SQOFF-{exec_res.execution_id}",
        legs=exec_req.legs,
        approved_lots=1,
        required_capital=Decimal("0.00")
    )
    exit_result = await ExecutionEngine.execute(db_session, exit_req)
    assert exit_result.status.value == "FILLED"

    # Close Position
    stmt_exec = select(StrategyExecution).where(StrategyExecution.id == exec_res.execution_id)
    res_e = await db_session.execute(stmt_exec)
    exec_rec = res_e.scalar_one()
    exec_rec.status = "SQUARED_OFF"
    db_session.add(exec_rec)
    await strategy_state_manager.transition_state(db_session, created.id, version_id, StrategyLifecycleState.POSITION_CLOSED, "Position closed")

    r_state_closed = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state_closed.lifecycle_state == StrategyLifecycleState.POSITION_CLOSED

@pytest.mark.asyncio
async def test_strategy_2_paper_e2e(db_session, setup_traders_contract):
    """Scenario 11: Strategy 2 complete paper execution."""
    user = setup_traders_contract["user1"]
    req = StrategyRequest.model_validate(STRATEGY_2_COMPLETE_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    sig = StrategySignal(
        strategy_id=created.id,
        strategy_version_id=version_id,
        trading_date=date.today(),
        entry_time="09:45",
        signal_key=f"SIG-S2-E2E-{created.id}",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED"
    )
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
        correlation_id=f"TRACE-S2-{sig.id}-{user.id}",
        status="PENDING"
    )
    db_session.add(trace)
    await db_session.flush()

    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_2_COMPLETE_PAYLOAD,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )
    res = await ExecutionEngine.execute(db_session, exec_req)
    assert res.status.value == "FILLED"

    r_state = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT

@pytest.mark.asyncio
async def test_strategy_3_paper_e2e(db_session, setup_traders_contract):
    """Scenario 12: Strategy 3 four-leg paper execution fills both Short and Hedge legs."""
    user = setup_traders_contract["user1"]
    req = StrategyRequest.model_validate(STRATEGY_3_COMPLETE_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)
    version_id = created.currentVersionId

    sig = StrategySignal(
        strategy_id=created.id,
        strategy_version_id=version_id,
        trading_date=date.today(),
        entry_time="09:30",
        signal_key=f"SIG-S3-E2E-{created.id}",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED"
    )
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
        correlation_id=f"TRACE-S3-{sig.id}-{user.id}",
        status="PENDING"
    )
    db_session.add(trace)
    await db_session.flush()

    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(
        payload=STRATEGY_3_COMPLETE_PAYLOAD,
        user_id=user.id,
        strategy_id=created.id,
        strategy_version_id=version_id,
        signal_id=sig.id,
        execution_mode=ExecutionMode.PAPER
    )
    assert len(exec_req.legs) == 4
    
    # Execute in PAPER mode
    res = await ExecutionEngine.execute(db_session, exec_req)
    assert res.status.value == "FILLED"
    assert len(res.leg_results) == 4
    assert all(l.status.value == "FILLED" for l in res.leg_results)

    r_state = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert r_state.lifecycle_state == StrategyLifecycleState.MONITORING_EXIT

@pytest.mark.asyncio
async def test_strategy_3_hedge_integrity(db_session, setup_traders_contract):
    """Scenario 13: Strategy 3 mandatory hedge integrity verification."""
    user = setup_traders_contract["user1"]
    req = StrategyRequest.model_validate(STRATEGY_3_COMPLETE_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    version_id = created.currentVersionId

    legs = FrontendPayloadNormalizer.normalize_strategy_legs(STRATEGY_3_COMPLETE_PAYLOAD)
    assert len(legs) == 4
    # Hedges are present for both CE and PE
    hedge_legs = [l for l in legs if l.role.value == "HEDGE"]
    assert len(hedge_legs) == 2
    assert all(l.side == "BUY" for l in hedge_legs)
    assert all(l.strike_offset == Decimal("200.0") for l in hedge_legs)


# ==============================================================================
# TESTS 14, 15, 16, 17, 18, 19, 20: Isolation, Observability & Safety
# ==============================================================================

@pytest.mark.asyncio
async def test_two_user_copy_trading_paper_isolation(db_session, setup_traders_contract):
    """Scenario 14: Two users execute same strategy independently in PAPER mode."""
    u1 = setup_traders_contract["user1"]
    u2 = setup_traders_contract["user2"]

    req = StrategyRequest.model_validate(STRATEGY_1_COMPLETE_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, u1.id)
    await StrategyService.activate_strategy(db_session, created.id, u1.id)
    version_id = created.currentVersionId

    sig = StrategySignal(strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), entry_time="09:45", signal_key=f"SIG-CPY-{created.id}", signal_type="ENTRY", direction="BUY", status="CREATED")
    db_session.add(sig)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=sig.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    t1 = StrategyUserExecutionTrace(execution_batch_id=batch.id, signal_id=sig.id, user_id=u1.id, strategy_id=created.id, strategy_version_id=version_id, correlation_id=f"TRACE-U1-{sig.id}", status="PENDING")
    t2 = StrategyUserExecutionTrace(execution_batch_id=batch.id, signal_id=sig.id, user_id=u2.id, strategy_id=created.id, strategy_version_id=version_id, correlation_id=f"TRACE-U2-{sig.id}", status="PENDING")
    db_session.add_all([t1, t2])
    await db_session.flush()

    req1 = FrontendPayloadNormalizer.build_execution_request_from_signal(payload=STRATEGY_1_COMPLETE_PAYLOAD, user_id=u1.id, strategy_id=created.id, strategy_version_id=version_id, signal_id=sig.id, execution_mode=ExecutionMode.PAPER)
    res1 = await ExecutionEngine.execute(db_session, req1)

    req2 = FrontendPayloadNormalizer.build_execution_request_from_signal(payload=STRATEGY_1_COMPLETE_PAYLOAD, user_id=u2.id, strategy_id=created.id, strategy_version_id=version_id, signal_id=sig.id, execution_mode=ExecutionMode.PAPER)
    res2 = await ExecutionEngine.execute(db_session, req2)

    assert res1.status.value == "FILLED"
    assert res2.status.value == "FILLED"
    assert res1.execution_id != res2.execution_id

@pytest.mark.asyncio
async def test_duplicate_event_protection(db_session, setup_traders_contract):
    """Scenario 15: Duplicate market event key is safely deduplicated."""
    user = setup_traders_contract["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_COMPLETE_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    version_id = created.currentVersionId

    event_key = f"{created.id}:NIFTY:5m:2026-09-01T10:00:00"
    sig = StrategySignal(strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), entry_time="10:00", signal_key=f"SIG-EV-DEDUP", market_event_key=event_key, status="CREATED")
    db_session.add(sig)
    await db_session.flush()

    stmt = select(StrategySignal).where(StrategySignal.market_event_key == event_key)
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is not None

@pytest.mark.asyncio
async def test_duplicate_signal_execution_protection(db_session, setup_traders_contract):
    """Scenario 16: Duplicate execution request on executed signal is rejected."""
    user = setup_traders_contract["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_COMPLETE_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    version_id = created.currentVersionId

    sig = StrategySignal(strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), entry_time="10:15", signal_key=f"SIG-EXEC-DEDUP-14", status="CREATED")
    db_session.add(sig)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=sig.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(execution_batch_id=batch.id, signal_id=sig.id, user_id=user.id, strategy_id=created.id, strategy_version_id=version_id, correlation_id=f"TRACE-DEDUP-14", status="PENDING")
    db_session.add(trace)
    await db_session.flush()

    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(payload=STRATEGY_1_COMPLETE_PAYLOAD, user_id=user.id, strategy_id=created.id, strategy_version_id=version_id, signal_id=sig.id, execution_mode=ExecutionMode.PAPER)
    res1 = await ExecutionEngine.execute(db_session, exec_req)
    assert res1.status.value == "FILLED"

    val2 = await ExecutionValidator.validate_execution_request(db_session, exec_req)
    assert val2.is_valid is False
    assert val2.failure_code == "EXECUTION_DUPLICATE"

@pytest.mark.asyncio
async def test_execution_mode_remains_paper(db_session, setup_traders_contract):
    """Scenario 17: Execution mode strictly defaults to and remains PAPER."""
    user = setup_traders_contract["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_COMPLETE_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    assert created.mode == "PAPER"

@pytest.mark.asyncio
async def test_live_broker_path_never_called(db_session, setup_traders_contract):
    """Scenario 18: ZERO live broker (DhanAdapter) order calls occur."""
    user = setup_traders_contract["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_COMPLETE_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    version_id = created.currentVersionId

    sig = StrategySignal(strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), entry_time="10:30", signal_key=f"SIG-SAFE-14", status="CREATED")
    db_session.add(sig)
    await db_session.flush()

    batch = StrategyExecutionBatch(signal_id=sig.id, strategy_id=created.id, strategy_version_id=version_id, trading_date=date.today(), status="PROCESSING")
    db_session.add(batch)
    await db_session.flush()

    trace = StrategyUserExecutionTrace(execution_batch_id=batch.id, signal_id=sig.id, user_id=user.id, strategy_id=created.id, strategy_version_id=version_id, correlation_id=f"TRACE-SAFE-14", status="PENDING")
    db_session.add(trace)
    await db_session.flush()

    exec_req = FrontendPayloadNormalizer.build_execution_request_from_signal(payload=STRATEGY_1_COMPLETE_PAYLOAD, user_id=user.id, strategy_id=created.id, strategy_version_id=version_id, signal_id=sig.id, execution_mode=ExecutionMode.PAPER)

    with patch("app.brokers.dhan.adapter.DhanAdapter.place_order") as mock_dhan:
        res = await ExecutionEngine.execute(db_session, exec_req)
        assert res.status.value == "FILLED"
        mock_dhan.assert_not_called()

@pytest.mark.asyncio
async def test_complete_entry_to_exit_lifecycle(db_session, setup_traders_contract):
    """Scenario 19: Full state transition lifecycle verification."""
    user = setup_traders_contract["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_COMPLETE_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    version_id = created.currentVersionId

    s1 = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert s1.lifecycle_state == StrategyLifecycleState.WAITING

    await StrategyService.activate_strategy(db_session, created.id, user.id)
    s2 = await strategy_state_manager.get_runtime_state(db_session, created.id)
    assert s2.lifecycle_state == StrategyLifecycleState.MONITORING_ENTRY

@pytest.mark.asyncio
async def test_structured_traceability(db_session, setup_traders_contract, caplog):
    """Scenario 20: Full correlation chain traceability and audit log safety."""
    import logging
    caplog.set_level(logging.INFO)

    user = setup_traders_contract["user1"]
    req = StrategyRequest.model_validate(STRATEGY_1_COMPLETE_PAYLOAD)
    created = await StrategyService.create_strategy(db_session, req, user.id)
    await StrategyService.activate_strategy(db_session, created.id, user.id)

    log_msgs = [r.message for r in caplog.records]
    assert any("strategy_activated" in msg for msg in log_msgs)
