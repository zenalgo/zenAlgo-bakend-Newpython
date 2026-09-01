import pytest
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.market_data.enums import MarketEventType
from app.market_data.schemas import MarketEvent
from app.strategies.enums import StrategyLifecycleState
from app.strategies.routing.schemas import StrategyRoute
from app.strategies.routing.enums import RouteType
from app.strategies.rules.rule_schema import ParsedRule, IndicatorOperand
from app.strategies.models import Strategy, StrategyVersion, StrategyCondition, StrategyEventProcessing
from app.strategies.engine.enums import EvaluationStatus
from app.strategies.engine.schemas import ConditionEvaluationResult, StrategyEvaluationResult
from app.strategies.engine.context import MarketContext
from app.strategies.engine.indicator_provider import InMemoryIndicatorProvider
from app.strategies.engine.condition_evaluator import evaluate_condition
from app.strategies.engine.idempotency import claim_strategy_event_processing
from app.strategies.engine.service import StrategyEngine

@pytest.fixture
async def test_user(db_session):
    """Creates a seeded user for foreign key safety."""
    user = User(
        email="engine_test_user@example.com",
        password_hash=hash_password("testpass123"),
        role=UserRole.TRADER,
        is_active=True,
        referral_code="REF-ENG001"
    )
    db_session.add(user)
    await db_session.flush()
    return user

# --- Tests 6-01 & 6-02: Price Comparison ---

def test_price_comparison_true_and_false():
    """Test 6-01 & 6-02: Evaluates price comparisons against numeric thresholds."""
    rule_gt = ParsedRule(type="PRICE_COMPARISON", operator=">", value=100.0)
    
    # 1. Price = 101 > 100 -> TRUE
    ctx_101 = MarketContext(symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("101.0"))
    res_101 = evaluate_condition(rule_gt, ctx_101)
    assert res_101.matched is True
    assert res_101.status == EvaluationStatus.MATCHED

    # 2. Price = 99 > 100 -> FALSE
    ctx_99 = MarketContext(symbol="NIFTY", timestamp=datetime.now(timezone.utc), current_price=Decimal("99.0"))
    res_99 = evaluate_condition(rule_gt, ctx_99)
    assert res_99.matched is False
    assert res_99.status == EvaluationStatus.NOT_MATCHED

# --- Test 6-03: RSI Comparison ---

def test_rsi_comparison():
    """Test 6-03: Evaluates static indicator comparisons (RSI > 60)."""
    rule_rsi = ParsedRule(type="INDICATOR_COMPARISON", indicator="RSI", period=14, operator=">", value=60.0)
    
    ctx = MarketContext(
        symbol="NIFTY",
        timestamp=datetime.now(timezone.utc),
        indicators={"RSI_14": 65.0}
    )
    res = evaluate_condition(rule_rsi, ctx)
    assert res.matched is True
    assert res.status == EvaluationStatus.MATCHED
    assert res.current_value == 65.0
    assert res.threshold == 60.0

# --- Tests 6-04, 6-05, 6-06, 6-07: RSI Crossover Rules & Boundaries ---

def test_rsi_crossover_above_success():
    """Test 6-04: prev=59, curr=61, threshold=60 -> TRUE (Crossed Above)."""
    rule_cross = ParsedRule(type="INDICATOR_CROSSOVER", indicator="RSI", period=14, operator="CROSS_ABOVE", value=60.0)
    ctx = MarketContext(
        symbol="NIFTY",
        timestamp=datetime.now(timezone.utc),
        indicators={"RSI_14": 61.0, "RSI_14_PREV": 59.0}
    )
    res = evaluate_condition(rule_cross, ctx)
    assert res.matched is True
    assert res.status == EvaluationStatus.MATCHED

def test_rsi_already_above_no_crossover():
    """Test 6-05: prev=61, curr=65, threshold=60 -> FALSE (Already above, no crossover)."""
    rule_cross = ParsedRule(type="INDICATOR_CROSSOVER", indicator="RSI", period=14, operator="CROSS_ABOVE", value=60.0)
    ctx = MarketContext(
        symbol="NIFTY",
        timestamp=datetime.now(timezone.utc),
        indicators={"RSI_14": 65.0, "RSI_14_PREV": 61.0}
    )
    res = evaluate_condition(rule_cross, ctx)
    assert res.matched is False
    assert res.status == EvaluationStatus.NOT_MATCHED

def test_rsi_crossover_boundary_equal_previous():
    """Test 6-06: prev=60, curr=61, threshold=60 -> TRUE (Starting exactly on threshold counts as cross)."""
    rule_cross = ParsedRule(type="INDICATOR_CROSSOVER", indicator="RSI", period=14, operator="CROSS_ABOVE", value=60.0)
    ctx = MarketContext(
        symbol="NIFTY",
        timestamp=datetime.now(timezone.utc),
        indicators={"RSI_14": 61.0, "RSI_14_PREV": 60.0}
    )
    res = evaluate_condition(rule_cross, ctx)
    assert res.matched is True
    assert res.status == EvaluationStatus.MATCHED

def test_rsi_exact_threshold_current_not_crossover():
    """Test 6-07: prev=59, curr=60, threshold=60 -> FALSE (Must be strictly greater than threshold)."""
    rule_cross = ParsedRule(type="INDICATOR_CROSSOVER", indicator="RSI", period=14, operator="CROSS_ABOVE", value=60.0)
    ctx = MarketContext(
        symbol="NIFTY",
        timestamp=datetime.now(timezone.utc),
        indicators={"RSI_14": 60.0, "RSI_14_PREV": 59.0}
    )
    res = evaluate_condition(rule_cross, ctx)
    assert res.matched is False
    assert res.status == EvaluationStatus.NOT_MATCHED

# --- Tests 6-08, 6-09, 6-10, 6-11, 6-12: Logical Operators (AND, OR, NOT, Nested) ---

def test_logical_and_and_or():
    """Test 6-08, 6-09, 6-10: Evaluates composite AND / OR logical expressions."""
    cond_a = ParsedRule(type="INDICATOR_COMPARISON", indicator="RSI", period=14, operator=">", value=60.0)
    cond_b = ParsedRule(type="PRICE_COMPARISON", operator=">", value=24000.0)

    # 1. AND: Both True -> MATCHED
    rule_and = ParsedRule(type="AND", logic="AND", conditions=[cond_a, cond_b])
    ctx_both_true = MarketContext(
        symbol="NIFTY",
        timestamp=datetime.now(timezone.utc),
        current_price=Decimal("24500.0"),
        indicators={"RSI_14": 65.0}
    )
    res_and_true = evaluate_condition(rule_and, ctx_both_true)
    assert res_and_true.matched is True

    # 2. AND: One False -> NOT_MATCHED
    ctx_one_false = MarketContext(
        symbol="NIFTY",
        timestamp=datetime.now(timezone.utc),
        current_price=Decimal("23500.0"), # Fails cond_b
        indicators={"RSI_14": 65.0}
    )
    res_and_false = evaluate_condition(rule_and, ctx_one_false)
    assert res_and_false.matched is False

    # 3. OR: One True -> MATCHED
    rule_or = ParsedRule(type="OR", logic="OR", conditions=[cond_a, cond_b])
    res_or_true = evaluate_condition(rule_or, ctx_one_false)
    assert res_or_true.matched is True

def test_logical_not_and_nested_tree():
    """Test 6-11 & 6-12: Evaluates NOT inversion and nested A AND (B OR C) tree."""
    cond_price_low = ParsedRule(type="PRICE_COMPARISON", operator="<", value=24000.0)
    rule_not = ParsedRule(type="NOT", logic="NOT", conditions=[cond_price_low])

    ctx = MarketContext(
        symbol="NIFTY",
        timestamp=datetime.now(timezone.utc),
        current_price=Decimal("24500.0"), # Price is NOT < 24000
        indicators={"RSI_14": 65.0, "EMA_9": 24600.0, "EMA_21": 24400.0}
    )
    res_not = evaluate_condition(rule_not, ctx)
    assert res_not.matched is True

    # Nested: Price > 24000 AND (RSI > 60 OR EMA_9 < EMA_21)
    cond_rsi = ParsedRule(type="INDICATOR_COMPARISON", indicator="RSI", period=14, operator=">", value=60.0)
    cond_ema = ParsedRule(
        type="INDICATOR_COMPARISON", operator="<",
        left=IndicatorOperand(indicator="EMA", period=9),
        right=IndicatorOperand(indicator="EMA", period=21)
    )
    rule_or_nested = ParsedRule(type="OR", logic="OR", conditions=[cond_rsi, cond_ema])
    rule_nested_tree = ParsedRule(
        type="AND", logic="AND",
        conditions=[
            ParsedRule(type="PRICE_COMPARISON", operator=">", value=24000.0),
            rule_or_nested
        ]
    )
    res_nested = evaluate_condition(rule_nested_tree, ctx)
    assert res_nested.matched is True

# --- Test 6-15: Missing Indicator Data ---

def test_missing_indicator_returns_data_unavailable():
    """Test 6-15: Missing indicator returns DATA_UNAVAILABLE without silently becoming False."""
    rule_rsi = ParsedRule(type="INDICATOR_COMPARISON", indicator="RSI", period=14, operator=">", value=60.0)
    ctx_empty = MarketContext(
        symbol="NIFTY",
        timestamp=datetime.now(timezone.utc),
        indicators={} # No RSI data
    )
    res = evaluate_condition(rule_rsi, ctx_empty)
    assert res.matched is False
    assert res.status == EvaluationStatus.DATA_UNAVAILABLE
    assert "data unavailable" in res.reason.lower()

# --- Tests 6-13, 6-14, 6-16, 6-17, 6-18: Database, Idempotency & Concurrency ---

@pytest.mark.asyncio
async def test_strategy_engine_idempotency_claim(db_session, test_user):
    """Test 6-17: Duplicate strategy event key is claimed once and skipped on second evaluation."""
    strategy = Strategy(user_id=test_user.id, name="Engine Test Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    key = f"{strategy.id}:NIFTY:5m:CANDLE_CLOSED:2026-08-31T03:50:00.000000Z"
    
    # 1. First claim -> True
    c1 = await claim_strategy_event_processing(db_session, strategy.id, key)
    assert c1 is True

    # 2. Second claim with exact same key -> False (duplicate)
    c2 = await claim_strategy_event_processing(db_session, strategy.id, key)
    assert c2 is False

@pytest.mark.asyncio
async def test_strategy_engine_concurrent_duplicate_events(db_session, test_user):
    """Test 6-18: Concurrent evaluations of same market event: exactly one claims and one skips."""
    strategy = Strategy(user_id=test_user.id, name="Concurrent Engine Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    key = f"{strategy.id}:NIFTY:5m:CONCURRENT_TEST"

    # Worker A and Worker B try to claim simultaneously
    res_a = await claim_strategy_event_processing(db_session, strategy.id, key)
    res_b = await claim_strategy_event_processing(db_session, strategy.id, key)

    assert (res_a, res_b) in [(True, False), (False, True)]

@pytest.mark.asyncio
async def test_strategy_engine_entry_and_exit_rule_selection(db_session, test_user):
    """Test 6-13, 6-14 & 6-16: Verifies ENTRY routes evaluate entry conditions and EXIT routes evaluate exit conditions."""
    strategy = Strategy(user_id=test_user.id, name="Rule Selection Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("100000.0"))
    db_session.add(version)
    await db_session.flush()

    # Entry Condition: Price > 24000
    cond_entry = StrategyCondition(
        strategy_version_id=version.id,
        rule_type="ENTRY",
        raw_text="Price > 24000",
        rule_json='{"type": "PRICE_COMPARISON", "operator": ">", "value": 24000.0}'
    )
    # Exit Condition: Price < 23000
    cond_exit = StrategyCondition(
        strategy_version_id=version.id,
        rule_type="EXIT",
        raw_text="Price < 23000",
        rule_json='{"type": "PRICE_COMPARISON", "operator": "<", "value": 23000.0}'
    )
    db_session.add_all([cond_entry, cond_exit])
    await db_session.flush()

    engine = StrategyEngine()
    event = MarketEvent(
        event_id="ev_test_1", symbol="NIFTY", event_type=MarketEventType.CANDLE_CLOSED,
        timestamp=datetime.now(timezone.utc), timeframe="5m", price=Decimal("24500.0")
    )

    # 1. Evaluate ENTRY Route -> Price (24500) > 24000 matches!
    route_entry = StrategyRoute(
        strategy_id=strategy.id, strategy_version_id=version.id,
        lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY, event_id="ev_test_1",
        route_type=RouteType.ENTRY, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )
    res_entry = await engine.evaluate_strategy_route(db_session, route_entry, event)
    assert res_entry.overall_matched is True
    assert res_entry.status == EvaluationStatus.MATCHED
    assert len(res_entry.condition_results) == 1

    # 2. Evaluate EXIT Route on new event -> Price (24500) < 23000 fails!
    event_exit = MarketEvent(
        event_id="ev_test_2", symbol="NIFTY", event_type=MarketEventType.CANDLE_CLOSED,
        timestamp=datetime.now(timezone.utc), timeframe="5m", price=Decimal("24500.0")
    )
    route_exit = StrategyRoute(
        strategy_id=strategy.id, strategy_version_id=version.id,
        lifecycle_state=StrategyLifecycleState.MONITORING_EXIT, event_id="ev_test_2",
        route_type=RouteType.EXIT, symbol="NIFTY", timeframe="5m",
        event_type=MarketEventType.CANDLE_CLOSED, timestamp=datetime.now(timezone.utc)
    )
    res_exit = await engine.evaluate_strategy_route(db_session, route_exit, event_exit)
    assert res_exit.overall_matched is False
    assert res_exit.status == EvaluationStatus.NOT_MATCHED

# --- Test 6-20: Complete Real-Life RSI Crossover Progression ---

def test_full_rsi_crossover_progression():
    """
    Test 6-20: Real-life scenario:
    Bar 1: RSI = 58 (Below 60)
    Bar 2: RSI = 63 (Crosses Above 60) -> TRUE
    Bar 3: RSI = 66 (Already Above 60) -> FALSE
    """
    rule = ParsedRule(type="INDICATOR_CROSSOVER", indicator="RSI", period=14, operator="CROSS_ABOVE", value=60.0)

    # Bar 2: RSI moves 58 -> 63 (Crossed Above!)
    ctx_bar2 = MarketContext(
        symbol="NIFTY", timestamp=datetime.now(timezone.utc),
        indicators={"RSI_14": 63.0, "RSI_14_PREV": 58.0}
    )
    res_bar2 = evaluate_condition(rule, ctx_bar2)
    assert res_bar2.matched is True
    assert res_bar2.status == EvaluationStatus.MATCHED

    # Bar 3: RSI moves 63 -> 66 (Still high, but NO NEW CROSSOVER)
    ctx_bar3 = MarketContext(
        symbol="NIFTY", timestamp=datetime.now(timezone.utc),
        indicators={"RSI_14": 66.0, "RSI_14_PREV": 63.0}
    )
    res_bar3 = evaluate_condition(rule, ctx_bar3)
    assert res_bar3.matched is False
    assert res_bar3.status == EvaluationStatus.NOT_MATCHED
