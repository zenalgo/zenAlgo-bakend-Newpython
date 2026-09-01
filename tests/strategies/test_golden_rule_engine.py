import pytest
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.market_data.enums import MarketEventType
from app.market_data.schemas import MarketEvent
from app.strategies.enums import StrategyLifecycleState
from app.strategies.routing.schemas import StrategyRoute
from app.strategies.routing.enums import RouteType
from app.strategies.rules.rule_schema import ParsedRule
from app.strategies.models import Strategy, StrategyVersion, StrategyCondition, StrategyGoldenRule
from app.strategies.engine.context import MarketContext
from app.strategies.engine.enums import EvaluationStatus
from app.strategies.engine.schemas import StrategyEvaluationResult
from app.strategies.engine.service import StrategyEngine
from app.strategies.golden_rules.enums import GoldenRuleStatus, GateDecision
from app.strategies.golden_rules.schemas import GoldenRuleEvaluationResult, GoldenRulesGateResult
from app.strategies.golden_rules.evaluator import evaluate_single_golden_rule
from app.strategies.golden_rules.engine import GoldenRuleEngine

@pytest.fixture
async def test_user(db_session):
    """Creates a seeded user for foreign key safety."""
    user = User(
        email="golden_rule_user@example.com",
        password_hash=hash_password("testpass123"),
        role=UserRole.TRADER,
        is_active=True,
        referral_code="REF-GLD001"
    )
    db_session.add(user)
    await db_session.flush()
    return user

def make_candle_event(symbol: str = "NIFTY", timeframe: str = "5m", close: Decimal = Decimal("25020.0"), event_type: MarketEventType = MarketEventType.CANDLE_CLOSED) -> MarketEvent:
    return MarketEvent(
        event_id=f"{symbol}:{timeframe}:{event_type.value}:2026-08-31T03:50:00.000000Z",
        symbol=symbol,
        exchange="NSE",
        event_type=event_type,
        timestamp=datetime(2026, 8, 31, 3, 50, 0, tzinfo=timezone.utc),
        timeframe=timeframe,
        price=close,
        close=close,
        volume=120000
    )

# --- Tests 7-01, 7-02, 7-03: Candle Close Above / Below / Boundary ---

def test_candle_closure_above_breakout_level_pass():
    """Test 7-01: Candle close (25020) > breakout level (25000) on CANDLE_CLOSED -> PASS."""
    rule = ParsedRule(
        type="GOLDEN_RULE",
        evaluation="CANDLE_CLOSE",
        confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL",
        value=25000.0
    )
    candle = make_candle_event(close=Decimal("25020.0"), event_type=MarketEventType.CANDLE_CLOSED)
    ctx = MarketContext(symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("25020.0"), candle=candle)

    res = evaluate_single_golden_rule(rule, ctx)
    assert res.status == GoldenRuleStatus.PASS
    assert res.observed_value == 25020.0
    assert res.threshold == 25000.0

def test_candle_closure_above_breakout_level_fail():
    """Test 7-02: Candle close (24990) <= breakout level (25000) -> FAIL."""
    rule = ParsedRule(
        type="GOLDEN_RULE",
        evaluation="CANDLE_CLOSE",
        confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL",
        value=25000.0
    )
    candle = make_candle_event(close=Decimal("24990.0"), event_type=MarketEventType.CANDLE_CLOSED)
    ctx = MarketContext(symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("24990.0"), candle=candle)

    res = evaluate_single_golden_rule(rule, ctx)
    assert res.status == GoldenRuleStatus.FAIL
    assert res.observed_value == 24990.0

def test_candle_closure_exact_boundary_fail():
    """Test 7-03: Candle close (25000) exactly at level (25000) -> FAIL (Must be strictly greater)."""
    rule = ParsedRule(
        type="GOLDEN_RULE",
        evaluation="CANDLE_CLOSE",
        confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL",
        value=25000.0
    )
    candle = make_candle_event(close=Decimal("25000.0"), event_type=MarketEventType.CANDLE_CLOSED)
    ctx = MarketContext(symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("25000.0"), candle=candle)

    res = evaluate_single_golden_rule(rule, ctx)
    assert res.status == GoldenRuleStatus.FAIL

# --- Test 7-04: Incomplete Candle (TICK) Enforcement ---

def test_incomplete_candle_tick_returns_data_unavailable():
    """Test 7-04: Golden rule requiring candle closure returns DATA_UNAVAILABLE when fed a TICK event."""
    rule = ParsedRule(
        type="GOLDEN_RULE",
        evaluation="CANDLE_CLOSE",
        confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL",
        value=25000.0
    )
    tick = make_candle_event(close=Decimal("25050.0"), event_type=MarketEventType.TICK)
    ctx = MarketContext(symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("25050.0"), candle=tick)

    res = evaluate_single_golden_rule(rule, ctx)
    assert res.status == GoldenRuleStatus.DATA_UNAVAILABLE
    assert "requires candle_closed" in res.reason.lower()

# --- Tests 7-05 & 7-06: Multiple Golden Rules & Gate Decisions ---

@pytest.mark.asyncio
async def test_multiple_golden_rules_all_pass():
    """Test 7-05: When all mandatory Golden Rules pass, gate decision is PASS."""
    engine = GoldenRuleEngine()
    route = StrategyRoute(
        strategy_id=101, strategy_version_id=501, lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY,
        event_id="ev_1", route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )
    candle = make_candle_event(close=Decimal("25020.0"), event_type=MarketEventType.CANDLE_CLOSED)
    ctx = MarketContext(
        symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("25020.0"),
        candle=candle, indicators={"AVG_VOLUME": 100000.0}
    )

    rule1 = ParsedRule(type="GOLDEN_RULE", evaluation="CANDLE_CLOSE", confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL", value=25000.0)
    rule2 = ParsedRule(type="GOLDEN_RULE", evaluation="CANDLE_CLOSE", confirmation="VOLUME_ABOVE_AVERAGE")

    result = await engine.evaluate_golden_rules(None, route, candle, ctx, explicit_rules=[rule1, rule2])
    assert result.gate_decision == GateDecision.PASS
    assert result.all_passed is True
    assert result.rules_passed == 2
    assert result.rules_failed == 0

@pytest.mark.asyncio
async def test_multiple_golden_rules_one_fails_blocks_gate():
    """Test 7-06: If Rule 1 passes but Rule 2 fails (Volume <= Avg), gate decision is BLOCKED."""
    engine = GoldenRuleEngine()
    route = StrategyRoute(
        strategy_id=101, strategy_version_id=501, lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY,
        event_id="ev_1", route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )
    candle = make_candle_event(close=Decimal("25020.0"), event_type=MarketEventType.CANDLE_CLOSED) # Volume is 120000
    ctx = MarketContext(
        symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("25020.0"),
        candle=candle, indicators={"AVG_VOLUME": 200000.0} # Fails Rule 2 (120000 < 200000)
    )

    rule1 = ParsedRule(type="GOLDEN_RULE", evaluation="CANDLE_CLOSE", confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL", value=25000.0)
    rule2 = ParsedRule(type="GOLDEN_RULE", evaluation="CANDLE_CLOSE", confirmation="VOLUME_ABOVE_AVERAGE")

    result = await engine.evaluate_golden_rules(None, route, candle, ctx, explicit_rules=[rule1, rule2])
    assert result.gate_decision == GateDecision.BLOCKED
    assert result.all_passed is False
    assert result.rules_passed == 1
    assert result.rules_failed == 1

# --- Test 7-07: Missing Data Handling ---

@pytest.mark.asyncio
async def test_missing_data_blocks_gate_safely():
    """Test 7-07: Missing breakout level or volume data returns DATA_UNAVAILABLE and blocks gate."""
    engine = GoldenRuleEngine()
    route = StrategyRoute(
        strategy_id=101, strategy_version_id=501, lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY,
        event_id="ev_1", route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )
    candle = make_candle_event(close=Decimal("25020.0"), event_type=MarketEventType.CANDLE_CLOSED)
    ctx_empty = MarketContext(
        symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("25020.0"),
        candle=candle, indicators={} # No breakout level or volume avg provided
    )

    rule_unavail = ParsedRule(type="GOLDEN_RULE", evaluation="CANDLE_CLOSE", confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL")
    result = await engine.evaluate_golden_rules(None, route, candle, ctx_empty, explicit_rules=[rule_unavail])

    assert result.gate_decision == GateDecision.BLOCKED
    assert result.all_passed is False
    assert result.rules_unavailable == 1

# --- Tests 7-10, 7-11, 7-12, 7-16: End-to-End Pipeline & Safety Exit ---

@pytest.mark.asyncio
async def test_end_to_end_entry_condition_and_golden_rule_pass(db_session, test_user):
    """
    Test 7-11 & 7-12:
    1. Normal Entry Condition (RSI crosses above 60): 58 -> 63 -> TRUE
    2. Golden Rule (Candle close > 25000): 25020 > 25000 -> PASS
    Result: READY_FOR_SIGNAL (NO ORDER)
    """
    strategy = Strategy(user_id=test_user.id, name="E2E Golden Rule Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("100000.0"))
    db_session.add(version)
    await db_session.flush()

    # Normal Entry: RSI crosses above 60
    cond_entry = StrategyCondition(
        strategy_version_id=version.id,
        rule_type="ENTRY",
        raw_text="RSI crosses above 60",
        rule_json='{"type": "INDICATOR_CROSSOVER", "indicator": "RSI", "period": 14, "operator": "CROSS_ABOVE", "value": 60.0}'
    )
    # Golden Rule: Candle must close above 25000
    golden_rule = StrategyGoldenRule(
        strategy_version_id=version.id,
        raw_text="Wait for candle closure above 25000",
        confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL",
        evaluation="CANDLE_CLOSE",
        mandatory=True,
        rule_json='{"value": 25000.0}'
    )
    db_session.add_all([cond_entry, golden_rule])
    await db_session.flush()

    candle = make_candle_event(close=Decimal("25020.0"), event_type=MarketEventType.CANDLE_CLOSED)
    ctx = MarketContext(
        symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("25020.0"),
        candle=candle, indicators={"RSI_14": 63.0, "RSI_14_PREV": 58.0}
    )

    route = StrategyRoute(
        strategy_id=strategy.id, strategy_version_id=version.id,
        lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY, event_id="ev_e2e_1",
        route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )

    # 1. Strategy Engine evaluates normal entry condition
    strat_engine = StrategyEngine()
    entry_eval = await strat_engine.evaluate_strategy_route(db_session, route, candle, context=ctx)
    assert entry_eval.overall_matched is True
    assert entry_eval.status == EvaluationStatus.MATCHED

    # 2. Golden Rule Engine evaluates mandatory gate
    gr_engine = GoldenRuleEngine()
    gate_eval = await gr_engine.evaluate_golden_rules(db_session, route, candle, context=ctx)
    assert gate_eval.gate_decision == GateDecision.PASS
    assert gate_eval.all_passed is True

@pytest.mark.asyncio
async def test_end_to_end_entry_true_but_golden_rule_fails_blocks_signal(db_session, test_user):
    """
    Test 7-10:
    1. Normal Entry Condition: RSI 58 -> 63 -> TRUE
    2. Golden Rule: Candle close (24980) <= 25000 -> FAIL
    Result: Gate BLOCKED, NO SIGNAL.
    """
    strategy = Strategy(user_id=test_user.id, name="Blocked Gate Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("100000.0"))
    db_session.add(version)
    await db_session.flush()

    cond_entry = StrategyCondition(
        strategy_version_id=version.id, rule_type="ENTRY", raw_text="RSI crosses above 60",
        rule_json='{"type": "INDICATOR_CROSSOVER", "indicator": "RSI", "period": 14, "operator": "CROSS_ABOVE", "value": 60.0}'
    )
    golden_rule = StrategyGoldenRule(
        strategy_version_id=version.id, raw_text="Wait for candle closure above 25000",
        confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL", evaluation="CANDLE_CLOSE",
        mandatory=True, rule_json='{"value": 25000.0}'
    )
    db_session.add_all([cond_entry, golden_rule])
    await db_session.flush()

    candle = make_candle_event(close=Decimal("24980.0"), event_type=MarketEventType.CANDLE_CLOSED) # Close fails 25000
    ctx = MarketContext(
        symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("24980.0"),
        candle=candle, indicators={"RSI_14": 63.0, "RSI_14_PREV": 58.0}
    )
    route = StrategyRoute(
        strategy_id=strategy.id, strategy_version_id=version.id,
        lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY, event_id="ev_e2e_2",
        route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )

    # 1. Entry Condition Matches
    strat_engine = StrategyEngine()
    entry_eval = await strat_engine.evaluate_strategy_route(db_session, route, candle, context=ctx)
    assert entry_eval.overall_matched is True

    # 2. Golden Rule Gate Fails -> BLOCKED
    gr_engine = GoldenRuleEngine()
    gate_eval = await gr_engine.evaluate_golden_rules(db_session, route, candle, context=ctx)
    assert gate_eval.gate_decision == GateDecision.BLOCKED
    assert gate_eval.all_passed is False
    assert gate_eval.rules_failed == 1

@pytest.mark.asyncio
async def test_safety_exit_route_bypasses_golden_rules():
    """Test 7-16: Exit routes are not blocked by Golden Rules, preserving safety exits."""
    engine = GoldenRuleEngine()
    route_exit = StrategyRoute(
        strategy_id=201, strategy_version_id=601, lifecycle_state=StrategyLifecycleState.MONITORING_EXIT,
        event_id="ev_exit_1", route_type=RouteType.EXIT, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )
    candle = make_candle_event(close=Decimal("24900.0"))
    ctx = MarketContext(symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("24900.0"), candle=candle)

    # Even if an entry golden rule exists, EXIT route bypasses it
    rule_entry = ParsedRule(type="GOLDEN_RULE", confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL", value=25000.0)
    result = await engine.evaluate_golden_rules(None, route_exit, candle, ctx, explicit_rules=[rule_entry])

    assert result.gate_decision == GateDecision.PASS
    assert result.all_passed is True
    assert "safety exit" in result.reason.lower()
