import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.market_data.enums import MarketEventType, FeedConnectionState
from app.market_data.schemas import MarketEvent
from app.market_data.adapter import DhanMarketDataAdapter, build_deterministic_event_id
from app.market_data.candle_aggregator import CandleAggregator
from app.market_data.service import MarketDataService
from app.core.exceptions import ValidationError

# --- Test 4-01: Normalize Valid Tick ---

def test_normalize_valid_tick():
    """Test 4-01: Converts raw Dhan market feed dictionary into canonical MarketEvent."""
    adapter = DhanMarketDataAdapter()
    raw_tick = {
        "tradingSymbol": "NIFTY",
        "ltp": 24500.75,
        "securityId": "13",
        "exchangeSegment": "NSE_FNO",
        "timestamp": 1756708200, # Epoch seconds
        "volume": 500
    }
    events = adapter.normalize_raw_feed_frame(raw_tick)
    assert len(events) == 1
    event = events[0]
    
    assert event.symbol == "NIFTY"
    assert event.security_id == "13"
    assert event.exchange == "NFO"
    assert event.price == Decimal("24500.75")
    assert event.event_type == MarketEventType.TICK
    assert event.timeframe == "TICK"
    assert event.volume == 500
    assert event.timestamp.tzinfo is not None

# --- Test 4-02: Invalid Payload ---

def test_normalize_invalid_payload_raises_error():
    """Test 4-02: Missing required fields (price/symbol) raises ValidationError."""
    adapter = DhanMarketDataAdapter()
    
    # Missing price
    with pytest.raises(ValidationError, match="missing price"):
        adapter.normalize_raw_feed_frame({"symbol": "NIFTY"})

    # Missing symbol
    with pytest.raises(ValidationError, match="missing required symbol"):
        adapter.normalize_raw_feed_frame({"ltp": 24500.0})

# --- Test 4-03: Timestamp Conversion ---

def test_timestamp_conversion_formats():
    """Test 4-03: Supports epoch seconds, epoch milliseconds, and ISO timestamps."""
    adapter = DhanMarketDataAdapter()

    # 1. Epoch seconds
    res_sec = adapter.normalize_raw_feed_frame({"symbol": "NIFTY", "price": 24500, "timestamp": 1700000000})[0]
    assert res_sec.timestamp == datetime.fromtimestamp(1700000000, tz=timezone.utc)

    # 2. Epoch milliseconds
    res_ms = adapter.normalize_raw_feed_frame({"symbol": "NIFTY", "price": 24500, "timestamp": 1700000000000})[0]
    assert res_ms.timestamp == datetime.fromtimestamp(1700000000, tz=timezone.utc)

    # 3. ISO format with timezone
    res_iso = adapter.normalize_raw_feed_frame({"symbol": "NIFTY", "price": 24500, "timestamp": "2026-08-31T09:30:00+05:30"})[0]
    assert res_iso.timestamp.tzinfo == timezone.utc
    assert res_iso.timestamp.hour == 4 # 09:30 IST is 04:00 UTC
    assert res_iso.timestamp.minute == 0

# --- Test 4-04: Deterministic Event ID ---

def test_deterministic_event_id():
    """Test 4-04: Identical inputs produce identical event_id; different timestamps produce distinct IDs."""
    ts1 = datetime(2026, 8, 31, 4, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 8, 31, 4, 0, 1, tzinfo=timezone.utc)

    id1_a = build_deterministic_event_id("NIFTY", "TICK", MarketEventType.TICK, ts1)
    id1_b = build_deterministic_event_id("NIFTY", "TICK", MarketEventType.TICK, ts1)
    id2 = build_deterministic_event_id("NIFTY", "TICK", MarketEventType.TICK, ts2)

    assert id1_a == id1_b
    assert id1_a != id2

# --- Test 4-05: Duplicate Event Ingestion ---

@pytest.mark.asyncio
async def test_duplicate_event_ingestion_dropped():
    """Test 4-05: Duplicate raw frames with the same event_id are dropped without re-dispatching."""
    service = MarketDataService()
    received_by_listener = []

    async def listener(event: MarketEvent):
        received_by_listener.append(event)

    service.add_listener(listener)

    raw_frame = {
        "symbol": "NIFTY",
        "price": 24500,
        "timestamp": 1756708200
    }

    # First ingest
    res1 = await service.ingest_raw_frame(raw_frame)
    assert len(res1) == 1
    assert len(received_by_listener) == 1

    # Second ingest of the exact same event
    res2 = await service.ingest_raw_frame(raw_frame)
    assert len(res2) == 0 # Dropped
    assert len(received_by_listener) == 1 # Listener was not called again

    status = service.get_status()
    assert status.total_events_received == 2
    assert status.total_events_dropped == 1

# --- Test 4-06: Multiple Symbols Handling ---

@pytest.mark.asyncio
async def test_multiple_symbols_isolation():
    """Test 4-06: Events from different symbols remain isolated."""
    service = MarketDataService()
    events = []
    service.add_listener(lambda e: events.append(e))

    await service.ingest_raw_frame({"symbol": "NIFTY", "price": 24500, "timestamp": 1756708200})
    await service.ingest_raw_frame({"symbol": "BANKNIFTY", "price": 52000, "timestamp": 1756708200})

    assert len(events) == 2
    symbols = [e.symbol for e in events]
    assert "NIFTY" in symbols
    assert "BANKNIFTY" in symbols

# --- Test 4-07: Timeframe Event IDs ---

def test_timeframe_event_ids():
    """Test 4-07: Event ID reflects the timeframe."""
    ts = datetime(2026, 8, 31, 4, 0, 0, tzinfo=timezone.utc)
    id_1m = build_deterministic_event_id("NIFTY", "1m", MarketEventType.CANDLE_CLOSED, ts)
    id_5m = build_deterministic_event_id("NIFTY", "5m", MarketEventType.CANDLE_CLOSED, ts)
    id_15m = build_deterministic_event_id("NIFTY", "15m", MarketEventType.CANDLE_CLOSED, ts)

    assert ":1m:" in id_1m
    assert ":5m:" in id_5m
    assert ":15m:" in id_15m
    assert len({id_1m, id_5m, id_15m}) == 3

# --- Test 4-08 & 4-09: Candle Aggregator & Boundary Crossing ---

def test_candle_aggregator_boundary_and_single_close():
    """Test 4-08 & 4-09: Aggregator completes a 5m candle when boundary is crossed and emits once."""
    aggregator = CandleAggregator(supported_timeframes=["5m"])
    
    # 09:15:10 IST (03:45:10 UTC) -> Tick 1 (Open: 24500)
    t1 = datetime(2026, 8, 31, 3, 45, 10, tzinfo=timezone.utc)
    ev1 = MarketEvent(
        event_id="e1", symbol="NIFTY", event_type=MarketEventType.TICK,
        timestamp=t1, timeframe="TICK", price=Decimal("24500.0")
    )
    closed = aggregator.process_tick(ev1)
    assert len(closed) == 0

    # 09:17:30 IST (03:47:30 UTC) -> Tick 2 (High: 24550, Low: 24480)
    t2 = datetime(2026, 8, 31, 3, 47, 30, tzinfo=timezone.utc)
    ev2 = MarketEvent(
        event_id="e2", symbol="NIFTY", event_type=MarketEventType.TICK,
        timestamp=t2, timeframe="TICK", price=Decimal("24550.0")
    )
    aggregator.process_tick(ev2)
    ev3 = MarketEvent(
        event_id="e3", symbol="NIFTY", event_type=MarketEventType.TICK,
        timestamp=t2, timeframe="TICK", price=Decimal("24480.0")
    )
    aggregator.process_tick(ev3)

    # 09:20:01 IST (03:50:01 UTC) -> Crosses 5m boundary! (09:15-09:20 closed)
    t4 = datetime(2026, 8, 31, 3, 50, 1, tzinfo=timezone.utc)
    ev4 = MarketEvent(
        event_id="e4", symbol="NIFTY", event_type=MarketEventType.TICK,
        timestamp=t4, timeframe="TICK", price=Decimal("24520.0")
    )
    closed_candles = aggregator.process_tick(ev4)
    assert len(closed_candles) == 1
    candle = closed_candles[0]
    
    assert candle.symbol == "NIFTY"
    assert candle.timeframe == "5m"
    assert candle.event_type == MarketEventType.CANDLE_CLOSED
    assert candle.open == Decimal("24500.0")
    assert candle.high == Decimal("24550.0")
    assert candle.low == Decimal("24480.0")
    assert candle.close == Decimal("24480.0") # Last price before boundary
    assert candle.timestamp == datetime(2026, 8, 31, 3, 50, 0, tzinfo=timezone.utc)

    # Send another tick within the 09:20-09:25 candle -> No new candle closed
    ev5 = MarketEvent(
        event_id="e5", symbol="NIFTY", event_type=MarketEventType.TICK,
        timestamp=t4 + timedelta(seconds=10), timeframe="TICK", price=Decimal("24530.0")
    )
    closed_again = aggregator.process_tick(ev5)
    assert len(closed_again) == 0

# --- Test 4-10: Feed Connection & Disconnection ---

@pytest.mark.asyncio
async def test_feed_connection_lifecycle():
    """Test 4-10: Connect and disconnect state transitions."""
    service = MarketDataService()
    assert service.get_status().state == FeedConnectionState.DISCONNECTED

    await service.connect()
    assert service.get_status().state == FeedConnectionState.CONNECTED
    assert service.get_status().connected_at is not None

    await service.disconnect()
    assert service.get_status().state == FeedConnectionState.DISCONNECTED

# --- Test 4-11: Feed Reconnect & Subscription Retention ---

@pytest.mark.asyncio
async def test_feed_reconnect_preserves_subscriptions():
    """Test 4-11: Reconnection preserves subscribed symbols."""
    service = MarketDataService()
    await service.subscribe(["NIFTY", "BANKNIFTY"])
    await service.connect()

    await service.handle_disconnect("Simulated Network Drop")
    assert service.get_status().state == FeedConnectionState.DISCONNECTED

    reconnect_ok = await service.reconnect()
    assert reconnect_ok is True
    assert service.get_status().state == FeedConnectionState.CONNECTED
    assert service.get_subscribed_symbols() == ["BANKNIFTY", "NIFTY"]

# --- Test 4-12: Multi-Subscriber Listener Dispatch ---

@pytest.mark.asyncio
async def test_multi_subscriber_dispatch():
    """Test 4-12: Dispatches events to multiple registered engine subscribers."""
    service = MarketDataService()
    subscriber_a_events = []
    subscriber_b_events = []

    service.add_listener(lambda e: subscriber_a_events.append(e))
    service.add_listener(lambda e: subscriber_b_events.append(e))

    await service.ingest_raw_frame({"symbol": "NIFTY", "price": 24500, "timestamp": 1756708200})

    assert len(subscriber_a_events) == 1
    assert len(subscriber_b_events) == 1
    assert subscriber_a_events[0].event_id == subscriber_b_events[0].event_id
