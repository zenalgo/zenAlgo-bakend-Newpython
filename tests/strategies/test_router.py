import pytest
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from app.market_data.enums import MarketEventType
from app.market_data.schemas import MarketEvent
from app.strategies.enums import StrategyLifecycleState
from app.strategies.routing.enums import RouteType, RouteSkipReason
from app.strategies.routing.schemas import CandidateStrategy, StrategyRoute
from app.strategies.routing.router import StrategyRouter
from app.strategies.routing.index import StrategyRoutingIndex

@pytest.fixture
def clean_router():
    index = StrategyRoutingIndex()
    router = StrategyRouter(index=index)
    return router

def make_market_event(symbol: str = "NIFTY", timeframe: str = "5m", event_type: MarketEventType = MarketEventType.CANDLE_CLOSED) -> MarketEvent:
    return MarketEvent(
        event_id=f"{symbol}:{timeframe}:{event_type.value}:2026-08-31T03:50:00.000000Z",
        symbol=symbol,
        exchange="NSE",
        event_type=event_type,
        timestamp=datetime(2026, 8, 31, 3, 50, 0, tzinfo=timezone.utc),
        timeframe=timeframe,
        price=Decimal("24500.0"),
        close=Decimal("24500.0")
    )

# --- Test 5-01: Correct Symbol + Timeframe + Monitoring State ---

@pytest.mark.asyncio
async def test_route_correct_symbol_timeframe_monitoring_entry(clean_router):
    """Test 5-01: Strategy in MONITORING_ENTRY matching symbol & timeframe produces ENTRY route."""
    candidate = CandidateStrategy(
        strategy_id=101,
        strategy_version_id=501,
        symbol="NIFTY",
        timeframe="5m",
        lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY
    )
    await clean_router.index.register_candidate(candidate)

    event = make_market_event(symbol="NIFTY", timeframe="5m")
    result = await clean_router.route_market_event(event)

    assert len(result.matched_routes) == 1
    assert len(result.skipped_routes) == 0
    route = result.matched_routes[0]
    assert route.strategy_id == 101
    assert route.strategy_version_id == 501
    assert route.route_type == RouteType.ENTRY
    assert route.symbol == "NIFTY"
    assert route.timeframe == "5m"

# --- Test 5-02: Symbol Mismatch ---

@pytest.mark.asyncio
async def test_route_symbol_mismatch_skipped(clean_router):
    """Test 5-02: Strategy requiring BANKNIFTY is skipped when NIFTY event arrives."""
    candidate = CandidateStrategy(
        strategy_id=102,
        strategy_version_id=502,
        symbol="BANKNIFTY",
        timeframe="5m",
        lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY
    )
    await clean_router.index.register_candidate(candidate)

    event = make_market_event(symbol="NIFTY", timeframe="5m")
    result = await clean_router.route_market_event(event)

    assert len(result.matched_routes) == 0

# --- Test 5-03: Timeframe Mismatch ---

@pytest.mark.asyncio
async def test_route_timeframe_mismatch_skipped(clean_router):
    """Test 5-03: Strategy on 15m is skipped when a 5m candle event arrives."""
    candidate = CandidateStrategy(
        strategy_id=103,
        strategy_version_id=503,
        symbol="NIFTY",
        timeframe="15m",
        lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY
    )
    await clean_router.index.register_candidate(candidate)

    event = make_market_event(symbol="NIFTY", timeframe="5m")
    result = await clean_router.route_market_event(event)

    # 15m strategy does not match 5m event
    assert len(result.matched_routes) == 0

# --- Test 5-04 & 5-05: Non-Monitoring Lifecycle States ---

@pytest.mark.asyncio
async def test_route_waiting_state_skipped(clean_router):
    """Test 5-04: Strategy in WAITING state is skipped."""
    candidate = CandidateStrategy(
        strategy_id=104,
        strategy_version_id=504,
        symbol="NIFTY",
        timeframe="5m",
        lifecycle_state=StrategyLifecycleState.WAITING
    )
    await clean_router.index.register_candidate(candidate)

    event = make_market_event(symbol="NIFTY", timeframe="5m")
    result = await clean_router.route_market_event(event)

    assert len(result.matched_routes) == 0
    assert len(result.skipped_routes) == 1
    assert result.skipped_routes[0].reason == RouteSkipReason.NOT_MONITORING

@pytest.mark.asyncio
async def test_route_paused_state_skipped(clean_router):
    """Test 5-05: Strategy in PAUSED state is skipped."""
    candidate = CandidateStrategy(
        strategy_id=105,
        strategy_version_id=505,
        symbol="NIFTY",
        timeframe="5m",
        lifecycle_state=StrategyLifecycleState.PAUSED
    )
    await clean_router.index.register_candidate(candidate)

    event = make_market_event(symbol="NIFTY", timeframe="5m")
    result = await clean_router.route_market_event(event)

    assert len(result.matched_routes) == 0
    assert len(result.skipped_routes) == 1
    assert result.skipped_routes[0].reason == RouteSkipReason.NOT_MONITORING

# --- Test 5-06 & 5-07: Entry vs Exit Routing ---

@pytest.mark.asyncio
async def test_route_entry_and_exit_types(clean_router):
    """Test 5-06 & 5-07: Differentiates MONITORING_ENTRY (ENTRY) and MONITORING_EXIT (EXIT)."""
    strat_entry = CandidateStrategy(
        strategy_id=106, strategy_version_id=506, symbol="NIFTY", timeframe="5m",
        lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY
    )
    strat_exit = CandidateStrategy(
        strategy_id=107, strategy_version_id=507, symbol="NIFTY", timeframe="5m",
        lifecycle_state=StrategyLifecycleState.MONITORING_EXIT
    )
    await clean_router.index.register_candidate(strat_entry)
    await clean_router.index.register_candidate(strat_exit)

    event = make_market_event(symbol="NIFTY", timeframe="5m")
    result = await clean_router.route_market_event(event)

    assert len(result.matched_routes) == 2
    route_map = {r.strategy_id: r.route_type for r in result.matched_routes}
    assert route_map[106] == RouteType.ENTRY
    assert route_map[107] == RouteType.EXIT

# --- Test 5-08: Multi-Strategy Fan-Out ---

@pytest.mark.asyncio
async def test_multi_strategy_fan_out(clean_router):
    """Test 5-08: Dispatches events to multiple handlers registered downstream."""
    strat1 = CandidateStrategy(strategy_id=201, strategy_version_id=601, symbol="NIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY)
    strat2 = CandidateStrategy(strategy_id=202, strategy_version_id=602, symbol="NIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY)
    strat3 = CandidateStrategy(strategy_id=203, strategy_version_id=603, symbol="BANKNIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY)

    await clean_router.index.register_candidate(strat1)
    await clean_router.index.register_candidate(strat2)
    await clean_router.index.register_candidate(strat3)

    dispatched = []
    async def downstream_engine(route: StrategyRoute, ev: MarketEvent):
        dispatched.append(route.strategy_id)

    clean_router.add_handler(downstream_engine)

    event = make_market_event(symbol="NIFTY", timeframe="5m")
    result = await clean_router.route_market_event(event)

    assert len(result.matched_routes) == 2
    assert 201 in dispatched
    assert 202 in dispatched
    assert 203 not in dispatched

# --- Test 5-09: Failure Isolation ---

@pytest.mark.asyncio
async def test_failure_isolation_between_strategies(clean_router):
    """Test 5-09: If handler throws exception for strategy A, strategy B still receives event."""
    strat_fail = CandidateStrategy(strategy_id=301, strategy_version_id=701, symbol="NIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY)
    strat_ok = CandidateStrategy(strategy_id=302, strategy_version_id=702, symbol="NIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY)

    await clean_router.index.register_candidate(strat_fail)
    await clean_router.index.register_candidate(strat_ok)

    successfully_handled = []

    async def flaky_handler(route: StrategyRoute, ev: MarketEvent):
        if route.strategy_id == 301:
            raise RuntimeError("Database connection timed out for Strategy 301")
        successfully_handled.append(route.strategy_id)

    clean_router.add_handler(flaky_handler)

    event = make_market_event(symbol="NIFTY", timeframe="5m")
    # Must not raise RuntimeError
    result = await clean_router.route_market_event(event)

    assert len(result.matched_routes) == 2
    assert 302 in successfully_handled

# --- Test 5-11: Strategy Version Safety ---

@pytest.mark.asyncio
async def test_strategy_version_safety(clean_router):
    """Test 5-11: Routes strictly using the candidate's active strategy_version_id."""
    strat_v2 = CandidateStrategy(
        strategy_id=401,
        strategy_version_id=2, # Active runtime version is 2
        symbol="NIFTY",
        timeframe="5m",
        lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY
    )
    await clean_router.index.register_candidate(strat_v2)

    event = make_market_event(symbol="NIFTY", timeframe="5m")
    result = await clean_router.route_market_event(event)

    assert len(result.matched_routes) == 1
    assert result.matched_routes[0].strategy_version_id == 2

# --- Test 5-12: Ten-Strategy Comprehensive Scenario ---

@pytest.mark.asyncio
async def test_ten_strategy_routing_matrix(clean_router):
    """
    Test 5-12: 10 active strategies across diverse symbols, timeframes, and states:
    1. Strat 1: NIFTY 5m MONITORING_ENTRY -> MATCH (ENTRY)
    2. Strat 2: NIFTY 5m MONITORING_EXIT  -> MATCH (EXIT)
    3. Strat 3: NIFTY 15m MONITORING_ENTRY -> SKIP (Timeframe)
    4. Strat 4: NIFTY 1m MONITORING_ENTRY  -> SKIP (Timeframe)
    5. Strat 5: BANKNIFTY 5m MONITORING_ENTRY -> SKIP (Symbol)
    6. Strat 6: BANKNIFTY 15m MONITORING_ENTRY -> SKIP (Symbol)
    7. Strat 7: NIFTY 5m WAITING -> SKIP (State)
    8. Strat 8: NIFTY 5m PAUSED -> SKIP (State)
    9. Strat 9: NIFTY 5m ERROR -> SKIP (State)
    10. Strat 10: NIFTY 5m MONITORING_ENTRY -> MATCH (ENTRY)
    """
    strategies = [
        CandidateStrategy(strategy_id=1, strategy_version_id=10, symbol="NIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY),
        CandidateStrategy(strategy_id=2, strategy_version_id=20, symbol="NIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.MONITORING_EXIT),
        CandidateStrategy(strategy_id=3, strategy_version_id=30, symbol="NIFTY", timeframe="15m", lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY),
        CandidateStrategy(strategy_id=4, strategy_version_id=40, symbol="NIFTY", timeframe="1m", lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY),
        CandidateStrategy(strategy_id=5, strategy_version_id=50, symbol="BANKNIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY),
        CandidateStrategy(strategy_id=6, strategy_version_id=60, symbol="BANKNIFTY", timeframe="15m", lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY),
        CandidateStrategy(strategy_id=7, strategy_version_id=70, symbol="NIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.WAITING),
        CandidateStrategy(strategy_id=8, strategy_version_id=80, symbol="NIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.PAUSED),
        CandidateStrategy(strategy_id=9, strategy_version_id=90, symbol="NIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.ERROR),
        CandidateStrategy(strategy_id=10, strategy_version_id=100, symbol="NIFTY", timeframe="5m", lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY),
    ]

    for strat in strategies:
        await clean_router.index.register_candidate(strat)

    # Incoming Event: NIFTY 5m CANDLE_CLOSED
    event = make_market_event(symbol="NIFTY", timeframe="5m")
    result = await clean_router.route_market_event(event)

    # Strategies 1, 2, 10 match
    matched_ids = [r.strategy_id for r in result.matched_routes]
    assert sorted(matched_ids) == [1, 2, 10]

    # Verify Route Types
    routes_by_id = {r.strategy_id: r for r in result.matched_routes}
    assert routes_by_id[1].route_type == RouteType.ENTRY
    assert routes_by_id[2].route_type == RouteType.EXIT
    assert routes_by_id[10].route_type == RouteType.ENTRY

@pytest.mark.asyncio
async def test_market_data_service_pub_sub_to_strategy_router():
    """Test 5-13: Verifies MarketDataService automatically publishes events to StrategyRouter."""
    from app.market_data.service import MarketDataService

    market_service = MarketDataService()
    index = StrategyRoutingIndex()
    router = StrategyRouter(index=index)

    # Register router as a listener of MarketDataService
    market_service.add_listener(router.route_market_event)

    # Register Candidate Strategy
    strat = CandidateStrategy(
        strategy_id=500,
        strategy_version_id=1,
        symbol="NIFTY",
        timeframe="TICK",
        lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY
    )
    await index.register_candidate(strat)

    # Capture routes received by downstream engine
    received_routes = []
    router.add_handler(lambda route, ev: received_routes.append(route))

    # Ingest raw broker frame
    raw_frame = {
        "tradingSymbol": "NIFTY",
        "price": 24510.0,
        "timestamp": 1756708200
    }
    await market_service.ingest_raw_frame(raw_frame)

    assert len(received_routes) == 1
    assert received_routes[0].strategy_id == 500
    assert received_routes[0].route_type == RouteType.ENTRY

