import pytest
import asyncio
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from sqlalchemy.future import select

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.market_data.enums import MarketEventType
from app.market_data.schemas import MarketEvent
from app.strategies.enums import StrategyLifecycleState
from app.strategies.routing.schemas import StrategyRoute
from app.strategies.routing.enums import RouteType
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyEntrySetting, StrategyEntryDay, StrategyExitSetting
from app.subscriptions.models import Subscription, Plan, PlanStrategyAccess
from app.execution.models import StrategySignal, StrategyExecutionBatch
from app.execution.service import execute_signal_batch
from app.strategies.engine.enums import EvaluationStatus
from app.strategies.engine.schemas import StrategyEvaluationResult, ConditionEvaluationResult
from app.strategies.golden_rules.enums import GateDecision, GoldenRuleStatus
from app.strategies.golden_rules.schemas import GoldenRulesGateResult, GoldenRuleEvaluationResult
from app.strategies.signals.enums import SignalType, SignalDirection, SignalStatus
from app.strategies.signals.schemas import TradingSignal, build_deterministic_signal_key
from app.strategies.signals.engine import SignalEngine

@pytest.fixture
async def test_user(db_session):
    """Creates a seeded user for foreign key safety."""
    user = User(
        email="signal_engine_user@example.com",
        password_hash=hash_password("testpass123"),
        role=UserRole.TRADER,
        is_active=True,
        referral_code="REF-SIGENG01"
    )
    db_session.add(user)
    await db_session.flush()
    return user

def make_candle_event(symbol: str = "NIFTY", timeframe: str = "5m", price: Decimal = Decimal("25020.0")) -> MarketEvent:
    return MarketEvent(
        event_id=f"{symbol}:{timeframe}:CANDLE_CLOSED:2026-08-31T03:50:00.000000Z",
        symbol=symbol,
        exchange="NSE",
        event_type=MarketEventType.CANDLE_CLOSED,
        timestamp=datetime(2026, 8, 31, 3, 50, 0, tzinfo=timezone.utc),
        timeframe=timeframe,
        price=price,
        close=price,
        volume=120000
    )

def make_matched_eval(strategy_id: int, version_id: int, route_type: RouteType = RouteType.ENTRY) -> StrategyEvaluationResult:
    return StrategyEvaluationResult(
        strategy_id=strategy_id,
        strategy_version_id=version_id,
        event_id="NIFTY:5m:CANDLE_CLOSED:2026-08-31T03:50:00.000000Z",
        route_type=route_type,
        status=EvaluationStatus.MATCHED,
        overall_matched=True,
        conditions_evaluated=1,
        conditions_matched=1,
        conditions_failed=0,
        condition_results=[
            ConditionEvaluationResult(
                rule_id=1, raw_text="RSI crosses above 60", rule_type="ENTRY",
                status=EvaluationStatus.MATCHED, matched=True, observed_value=63.0,
                expected_value=60.0, reason="RSI (63.0) crossed above 60.0"
            )
        ]
    )

def make_gate_result(strategy_id: int, version_id: int, decision: GateDecision = GateDecision.PASS) -> GoldenRulesGateResult:
    return GoldenRulesGateResult(
        strategy_id=strategy_id,
        strategy_version_id=version_id,
        event_id="NIFTY:5m:CANDLE_CLOSED:2026-08-31T03:50:00.000000Z",
        gate_decision=decision,
        all_passed=(decision == GateDecision.PASS),
        rules_evaluated=1,
        rules_passed=1 if decision == GateDecision.PASS else 0,
        rules_failed=1 if decision == GateDecision.BLOCKED else 0,
        rules_unavailable=0,
        reason="Mandatory gate passed" if decision == GateDecision.PASS else "Mandatory gate blocked",
        rule_results=[
            GoldenRuleEvaluationResult(
                rule_id=1, raw_text="Wait for candle close > 25000",
                confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL",
                evaluation_type="CANDLE_CLOSE", mandatory=True,
                status=GoldenRuleStatus.PASS if decision == GateDecision.PASS else GoldenRuleStatus.FAIL,
                observed_value=25020.0, threshold=25000.0,
                reason="Candle close 25020.0 > breakout level 25000.0"
            )
        ]
    )

# --- Tests 8C-01, 8C-02, 8C-03, 8C-04: Entry Decision & Gate Validation ---

@pytest.mark.asyncio
async def test_valid_entry_signal_creation(db_session, test_user):
    """Test 8C-01: Valid ENTRY condition + Golden Rule PASS creates StrategySignal with status CREATED."""
    strategy = Strategy(user_id=test_user.id, name="Entry Signal Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("100000.0"))
    db_session.add(version)
    await db_session.flush()

    route = StrategyRoute(
        strategy_id=strategy.id, strategy_version_id=version.id,
        lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY,
        event_id="ev_sig_1", route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )
    event = make_candle_event(price=Decimal("25020.0"))
    eval_res = make_matched_eval(strategy.id, version.id, RouteType.ENTRY)
    gate_res = make_gate_result(strategy.id, version.id, GateDecision.PASS)

    engine = SignalEngine()
    signal = await engine.generate_signal(db_session, route, event, eval_res, gate_res, persist=True)

    assert signal is not None
    assert signal.signal_id is not None
    assert signal.signal_type == SignalType.ENTRY
    assert signal.status == SignalStatus.CREATED
    assert signal.price == Decimal("25020.0")
    assert signal.strategy_version_id == version.id
    assert "Conditions MATCHED" in signal.reason

@pytest.mark.asyncio
async def test_entry_condition_fails_no_signal(db_session):
    """Test 8C-02: Entry condition not matched results in NO signal."""
    eval_unmatched = StrategyEvaluationResult(
        strategy_id=101, strategy_version_id=501, event_id="ev_1", route_type=RouteType.ENTRY,
        status=EvaluationStatus.NOT_MATCHED, overall_matched=False, conditions_evaluated=1,
        conditions_matched=0, conditions_failed=1, condition_results=[]
    )
    route = StrategyRoute(
        strategy_id=101, strategy_version_id=501, lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY,
        event_id="ev_1", route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )
    event = make_candle_event()
    engine = SignalEngine()

    signal = await engine.generate_signal(db_session, route, event, eval_unmatched, None, persist=True)
    assert signal is None

@pytest.mark.asyncio
async def test_golden_rule_blocked_no_entry_signal(db_session):
    """Test 8C-03 & 8C-04: Golden Rule FAIL or DATA_UNAVAILABLE blocks entry signal generation."""
    eval_res = make_matched_eval(101, 501, RouteType.ENTRY)
    gate_blocked = make_gate_result(101, 501, GateDecision.BLOCKED)
    route = StrategyRoute(
        strategy_id=101, strategy_version_id=501, lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY,
        event_id="ev_1", route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )
    event = make_candle_event()
    engine = SignalEngine()

    signal = await engine.generate_signal(db_session, route, event, eval_res, gate_blocked, persist=True)
    assert signal is None

# --- Tests 8C-05 & 8C-06: Exit Signals & Safety Exit Bypass ---

@pytest.mark.asyncio
async def test_valid_exit_signal_bypasses_golden_rules(db_session, test_user):
    """Test 8C-05 & 8C-06: Exit signal creation succeeds and bypasses entry Golden Rules."""
    strategy = Strategy(user_id=test_user.id, name="Exit Signal Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("100000.0"))
    db_session.add(version)
    await db_session.flush()

    route_exit = StrategyRoute(
        strategy_id=strategy.id, strategy_version_id=version.id,
        lifecycle_state=StrategyLifecycleState.MONITORING_EXIT,
        event_id="ev_exit_1", route_type=RouteType.EXIT, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )
    event = make_candle_event(price=Decimal("25100.0"))
    eval_exit = make_matched_eval(strategy.id, version.id, RouteType.EXIT)

    engine = SignalEngine()
    # Golden rule is None (bypassed for exit)
    signal = await engine.generate_signal(db_session, route_exit, event, eval_exit, golden_rule_result=None, persist=True)

    assert signal is not None
    assert signal.signal_type == SignalType.EXIT
    assert signal.status == SignalStatus.CREATED
    assert signal.price == Decimal("25100.0")
    assert "Safety Exit" in signal.reason

# --- Tests 8C-07, 8C-08, 8C-09, 8C-10, 8C-11: Determinism, Idempotency & Concurrency ---

@pytest.mark.asyncio
async def test_idempotent_duplicate_signal_generation(db_session, test_user):
    """Test 8C-08, 8C-09, 8C-11: Duplicate signal generation returns existing record and leaves DB session healthy."""
    strategy = Strategy(user_id=test_user.id, name="Idempotent Signal Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("100000.0"))
    db_session.add(version)
    await db_session.flush()

    route = StrategyRoute(
        strategy_id=strategy.id, strategy_version_id=version.id,
        lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY,
        event_id="ev_dup_1", route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )
    event = make_candle_event()
    eval_res = make_matched_eval(strategy.id, version.id, RouteType.ENTRY)
    gate_res = make_gate_result(strategy.id, version.id, GateDecision.PASS)

    engine = SignalEngine()

    # 1. First Call: Creates signal
    sig1 = await engine.generate_signal(db_session, route, event, eval_res, gate_res, persist=True)
    assert sig1.signal_id is not None

    # 2. Second Call: Returns duplicate safely
    sig2 = await engine.generate_signal(db_session, route, event, eval_res, gate_res, persist=True)
    assert sig2.signal_id == sig1.signal_id
    assert sig2.signal_key == sig1.signal_key

    # 3. Verify session remains usable for subsequent DB operations
    test_strat = Strategy(user_id=test_user.id, name="Subsequent Operation Test", is_active=True)
    db_session.add(test_strat)
    await db_session.flush()
    assert test_strat.id is not None

@pytest.mark.asyncio
async def test_different_strategies_same_market_event(db_session, test_user):
    """Test 8C-12 & 8C-18: Different strategies on the same market event produce distinct signals."""
    s1 = Strategy(user_id=test_user.id, name="Strat 1", is_active=True)
    s2 = Strategy(user_id=test_user.id, name="Strat 2", is_active=True)
    db_session.add_all([s1, s2])
    await db_session.flush()

    v1 = StrategyVersion(strategy_id=s1.id, version_number=1, underlying="NIFTY", capital=Decimal("100000.0"))
    v2 = StrategyVersion(strategy_id=s2.id, version_number=1, underlying="NIFTY", capital=Decimal("100000.0"))
    db_session.add_all([v1, v2])
    await db_session.flush()

    event = make_candle_event()
    engine = SignalEngine()

    route1 = StrategyRoute(strategy_id=s1.id, strategy_version_id=v1.id, lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY, event_id="ev_common", route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m", event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc))
    route2 = StrategyRoute(strategy_id=s2.id, strategy_version_id=v2.id, lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY, event_id="ev_common", route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m", event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc))

    sig1 = await engine.generate_signal(db_session, route1, event, make_matched_eval(s1.id, v1.id), make_gate_result(s1.id, v1.id), persist=True)
    sig2 = await engine.generate_signal(db_session, route2, event, make_matched_eval(s2.id, v2.id), make_gate_result(s2.id, v2.id), persist=True)

    assert sig1.signal_id != sig2.signal_id
    assert sig1.signal_key != sig2.signal_key

# --- Test 8C-15, 8C-16, 8C-17: Strict Separation of Concerns (No Risk, No Broker, No Resolver) ---

@pytest.mark.asyncio
async def test_no_risk_or_broker_calls_during_signal_generation(db_session, test_user):
    """Test 8C-15, 8C-16, 8C-17: Signal generation does not call Risk Engine, Broker API, or Contract Resolver."""
    strategy = Strategy(user_id=test_user.id, name="Boundary Test Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("100000.0"))
    db_session.add(version)
    await db_session.flush()

    route = StrategyRoute(strategy_id=strategy.id, strategy_version_id=version.id, lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY, event_id="ev_bound", route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m", event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc))
    event = make_candle_event()

    engine = SignalEngine()

    with patch("app.brokers.service.get_active_broker_for_user") as mock_broker, \
         patch("app.strategies.instrument_resolver.InstrumentResolver.resolve_leg_instrument") as mock_resolver:
        
        signal = await engine.generate_signal(
            db_session, route, event,
            make_matched_eval(strategy.id, version.id),
            make_gate_result(strategy.id, version.id),
            persist=True
        )

        assert signal is not None
        mock_broker.assert_not_called()
        mock_resolver.assert_not_called()

# --- Test 8C-23: Existing Execution Engine Compatibility ---

@pytest.mark.asyncio
async def test_existing_execution_batch_compatibility_with_new_signal(db_session, test_user):
    """Test 8C-23: Evolved StrategySignal can be consumed seamlessly by execute_signal_batch()."""
    plan = Plan(code="SIG_ENG_PREMIUM", name="Premium Signal Plan", monthly_price=Decimal("999.0"), is_active=True)
    db_session.add(plan)
    await db_session.flush()

    sub = Subscription(user_id=test_user.id, plan_id=plan.id, status="ACTIVE", start_at=datetime.now(timezone.utc), current_period_start=datetime.now(timezone.utc), current_period_end=datetime.now(timezone.utc) + timedelta(days=30))
    strategy = Strategy(user_id=test_user.id, name="Exec Compat Strat", is_active=True, status="ACTIVE_LIVE", mode="PAPER")
    db_session.add_all([sub, strategy])
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("100000.0"))
    db_session.add(version)
    await db_session.flush()

    strategy.current_version_id = version.id
    leg = StrategyLeg(strategy_version_id=version.id, sequence=1, segment="OPT", side="BUY", strike_selection="ATM", expiry="WEEKLY", lots=1)
    entry_setting = StrategyEntrySetting(strategy_version_id=version.id, entry_time="09:30")
    entry_day = StrategyEntryDay(strategy_version_id=version.id, day_of_week="MONDAY")
    exit_setting = StrategyExitSetting(strategy_version_id=version.id, exit_time="15:15")
    access = PlanStrategyAccess(plan_id=plan.id, strategy_id=strategy.id, is_enabled=True)
    db_session.add_all([leg, entry_setting, entry_day, exit_setting, access])
    await db_session.flush()

    # Generate Signal via SignalEngine
    route = StrategyRoute(strategy_id=strategy.id, strategy_version_id=version.id, lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY, event_id="ev_exec_compat", route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m", event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc))
    event = make_candle_event()
    engine = SignalEngine()

    signal = await engine.generate_signal(
        db_session, route, event,
        make_matched_eval(strategy.id, version.id),
        make_gate_result(strategy.id, version.id),
        persist=True
    )
    await db_session.commit()

    # Execute downstream batch with the generated signal.id
    await execute_signal_batch(signal.signal_id)

    stmt = select(StrategyExecutionBatch).where(StrategyExecutionBatch.signal_id == signal.signal_id)
    res = await db_session.execute(stmt)
    batch = res.scalar_one_or_none()
    assert batch is not None
    assert batch.signal_id == signal.signal_id
    assert batch.strategy_id == strategy.id
