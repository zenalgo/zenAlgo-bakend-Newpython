import asyncio
from collections import deque
from datetime import datetime, timezone
import logging
from typing import List, Set, Dict, Any, Callable, Awaitable, Optional

from app.market_data.enums import MarketEventType, FeedConnectionState
from app.market_data.schemas import MarketEvent, FeedStatus
from app.market_data.adapter import BaseMarketDataAdapter, DhanMarketDataAdapter
from app.market_data.candle_aggregator import CandleAggregator
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class MarketDataService:
    """
    Centralized Market Data Ingestion & Event Dispatching Service.
    Normalizes broker feeds, generates deterministic events, aggregates candles,
    and publishes canonical events to downstream strategy engine subscribers.
    """
    def __init__(
        self,
        adapter: Optional[BaseMarketDataAdapter] = None,
        aggregator: Optional[CandleAggregator] = None,
        max_dedup_cache_size: int = 50000
    ):
        self.adapter = adapter or DhanMarketDataAdapter()
        self.aggregator = aggregator or CandleAggregator()
        self.max_dedup_cache_size = max_dedup_cache_size

        # In-memory deduplication set and bounded queue
        self._seen_event_ids: Set[str] = set()
        self._event_id_queue: deque = deque()

        # Subscriptions and Listeners
        self._subscribed_symbols: Set[str] = set()
        self._listeners: List[Callable[[MarketEvent], Awaitable[None]]] = []
        self._lock = asyncio.Lock()

        # Connection State & Metrics
        self._state: FeedConnectionState = FeedConnectionState.DISCONNECTED
        self._connected_at: Optional[datetime] = None
        self._last_event_time: Optional[datetime] = None
        self._total_events_received: int = 0
        self._total_events_dropped: int = 0

    # --- Subscription Management ---

    async def subscribe(self, symbols: List[str]) -> None:
        """Registers symbols for market data subscription."""
        async with self._lock:
            for s in symbols:
                if s and isinstance(s, str):
                    self._subscribed_symbols.add(s.strip().upper())
            logger.info(
                f"Market feed subscribed to symbols: {list(self._subscribed_symbols)}",
                extra={
                    "event": "market_subscription_updated",
                    "subscribed_symbols": list(self._subscribed_symbols)
                }
            )

    async def unsubscribe(self, symbols: List[str]) -> None:
        """Removes symbols from market data subscription."""
        async with self._lock:
            for s in symbols:
                if s and isinstance(s, str):
                    self._subscribed_symbols.discard(s.strip().upper())

    def get_subscribed_symbols(self) -> List[str]:
        """Returns the list of currently subscribed asset symbols."""
        return sorted(list(self._subscribed_symbols))

    # --- Listener / Consumer Dispatching ---

    def add_listener(self, listener: Callable[[MarketEvent], Awaitable[None]]) -> None:
        """Registers an asynchronous event listener (e.g. Strategy Router)."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[MarketEvent], Awaitable[None]]) -> None:
        """Unregisters an event listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def _dispatch_event(self, event: MarketEvent) -> None:
        """Dispatches a canonical MarketEvent to all registered listeners asynchronously."""
        for listener in self._listeners:
            try:
                res = listener(event)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.error(
                    f"Error in market event listener for event {event.event_id}: {str(e)}",
                    extra={
                        "event": "market_event_listener_error",
                        "event_id": event.event_id,
                        "error": str(e)
                    }
                )

    # --- Deduplication Helper ---

    def _is_duplicate_and_record(self, event_id: str) -> bool:
        """Checks if an event_id was already processed; records it if not seen."""
        if event_id in self._seen_event_ids:
            return True

        self._seen_event_ids.add(event_id)
        self._event_id_queue.append(event_id)

        # Evict oldest event if queue exceeds max cache size
        if len(self._event_id_queue) > self.max_dedup_cache_size:
            oldest = self._event_id_queue.popleft()
            self._seen_event_ids.discard(oldest)

        return False

    # --- Feed Ingest Pipeline ---

    async def ingest_raw_frame(self, raw_frame: Dict[str, Any]) -> List[MarketEvent]:
        """
        Main ingestion entry point:
        1. Normalizes raw broker frame into MarketEvent(s).
        2. Deduplicates incoming ticks in-memory (0 DB queries).
        3. Dispatches valid ticks to listeners.
        4. Updates CandleAggregator and dispatches any closed candles.
        """
        self._total_events_received += 1
        self._last_event_time = datetime.now(timezone.utc)

        # 1. Normalize
        normalized_events = self.adapter.normalize_raw_feed_frame(raw_frame)
        published_events: List[MarketEvent] = []

        for event in normalized_events:
            # 2. Check Deduplication
            if self._is_duplicate_and_record(event.event_id):
                self._total_events_dropped += 1
                logger.debug(
                    f"Duplicate market event dropped: {event.event_id}",
                    extra={
                        "event": "market_event_dropped",
                        "event_id": event.event_id,
                        "symbol": event.symbol,
                        "reason": "DUPLICATE_EVENT_ID"
                    }
                )
                continue

            # 3. Publish canonical tick event
            published_events.append(event)
            await self._dispatch_event(event)

            # 4. Feed to Candle Aggregator
            closed_candles = self.aggregator.process_tick(event)
            for candle_event in closed_candles:
                if not self._is_duplicate_and_record(candle_event.event_id):
                    published_events.append(candle_event)
                    await self._dispatch_event(candle_event)

        return published_events

    # --- Lifecycle & Connection Handling ---

    async def connect(self) -> None:
        """Marks connection state as CONNECTED."""
        async with self._lock:
            self._state = FeedConnectionState.CONNECTED
            self._connected_at = datetime.now(timezone.utc)
            logger.info(
                "Market data feed connected successfully.",
                extra={
                    "event": "market_feed_connected",
                    "state": self._state.value,
                    "connected_at": self._connected_at.isoformat()
                }
            )

    async def disconnect(self) -> None:
        """Marks connection state as DISCONNECTED."""
        async with self._lock:
            self._state = FeedConnectionState.DISCONNECTED
            logger.info(
                "Market data feed disconnected.",
                extra={
                    "event": "market_feed_disconnected",
                    "state": self._state.value
                }
            )

    async def handle_disconnect(self, reason: Optional[str] = None) -> None:
        """Handles unexpected feed disconnection."""
        async with self._lock:
            self._state = FeedConnectionState.DISCONNECTED
            logger.warning(
                f"Market feed disconnected unexpectedly: {reason}",
                extra={
                    "event": "market_feed_disconnected",
                    "reason": reason or "CONNECTION_LOST"
                }
            )

    async def reconnect(self) -> bool:
        """Simulates reconnection sequence and restores subscriptions."""
        async with self._lock:
            self._state = FeedConnectionState.RECONNECTING
            logger.info(
                "Market data feed reconnecting...",
                extra={"event": "market_feed_reconnecting"}
            )
            # Simulated reconnect success
            self._state = FeedConnectionState.CONNECTED
            self._connected_at = datetime.now(timezone.utc)
            logger.info(
                f"Market data feed reconnected. Restored {len(self._subscribed_symbols)} subscriptions.",
                extra={
                    "event": "market_feed_connected",
                    "subscribed_symbols": list(self._subscribed_symbols)
                }
            )
            return True

    # --- Observability ---

    def get_status(self) -> FeedStatus:
        """Returns snapshot of current feed health metrics."""
        return FeedStatus(
            state=self._state,
            connected_at=self._connected_at,
            last_event_time=self._last_event_time,
            subscribed_symbols=self.get_subscribed_symbols(),
            total_events_received=self._total_events_received,
            total_events_dropped=self._total_events_dropped
        )

# Global singleton instance
market_data_service = MarketDataService()
