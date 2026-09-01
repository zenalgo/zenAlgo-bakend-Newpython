from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from typing import Dict, Tuple, Optional, List
import logging

from app.market_data.enums import MarketEventType
from app.market_data.schemas import MarketEvent
from app.market_data.adapter import build_deterministic_event_id

logger = logging.getLogger(__name__)

MARKET_TIMEZONE = ZoneInfo("Asia/Kolkata")

TIMEFRAME_MINUTES_MAP = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "10m": 10,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "60m": 60,
    "1d": 1440
}

class InProgressCandle:
    """Holds accumulating OHLCV state for an open candle."""
    def __init__(self, symbol: str, timeframe: str, exchange: str, security_id: Optional[str], start_time: datetime, end_time: datetime, initial_price: Decimal, initial_volume: Optional[int] = None):
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = exchange
        self.security_id = security_id
        self.start_time = start_time # UTC
        self.end_time = end_time     # UTC
        self.open = initial_price
        self.high = initial_price
        self.low = initial_price
        self.close = initial_price
        self.volume = initial_volume or 0
        self.ticks_count = 1

    def update(self, price: Decimal, volume: Optional[int] = None):
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.close = price
        if volume is not None:
            self.volume += volume
        self.ticks_count += 1

    def to_market_event(self, event_type: MarketEventType = MarketEventType.CANDLE_CLOSED) -> MarketEvent:
        event_id = build_deterministic_event_id(self.symbol, self.timeframe, event_type, self.end_time)
        return MarketEvent(
            event_id=event_id,
            symbol=self.symbol,
            security_id=self.security_id,
            exchange=self.exchange,
            event_type=event_type,
            timestamp=self.end_time,
            timeframe=self.timeframe,
            price=self.close,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume if self.volume > 0 else None
        )

class CandleAggregator:
    """
    In-memory candle aggregation engine that turns streaming ticks into deterministic OHLCV candles.
    """
    def __init__(self, supported_timeframes: Optional[List[str]] = None):
        self.supported_timeframes = supported_timeframes or ["1m", "5m", "15m"]
        # Key: (symbol, timeframe) -> InProgressCandle
        self._active_candles: Dict[Tuple[str, str], InProgressCandle] = {}
        # Set of already closed candle event IDs to guarantee strict single emission
        self._closed_candle_ids = set()

    def _calculate_candle_bounds(self, tick_time_utc: datetime, timeframe_str: str) -> Tuple[datetime, datetime]:
        """Calculates candle start and end UTC timestamps using Asia/Kolkata market time boundaries."""
        minutes = TIMEFRAME_MINUTES_MAP.get(timeframe_str, 5)
        local_dt = tick_time_utc.astimezone(MARKET_TIMEZONE)

        # Truncate to candle bucket boundary
        minute_bucket = (local_dt.minute // minutes) * minutes
        start_local = local_dt.replace(minute=minute_bucket, second=0, microsecond=0)
        end_local = start_local + timedelta(minutes=minutes)

        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        return start_utc, end_utc

    def process_tick(self, tick_event: MarketEvent) -> List[MarketEvent]:
        """
        Ingests a TICK MarketEvent. Returns a list of newly closed CANDLE_CLOSED MarketEvents (if any boundary was crossed).
        """
        if tick_event.price is None:
            return []

        closed_events: List[MarketEvent] = []
        symbol = tick_event.symbol
        tick_time = tick_event.timestamp
        price = tick_event.price
        volume = tick_event.volume

        for tf in self.supported_timeframes:
            start_utc, end_utc = self._calculate_candle_bounds(tick_time, tf)
            key = (symbol, tf)
            current_candle = self._active_candles.get(key)

            if current_candle is None:
                # Initialize new candle
                self._active_candles[key] = InProgressCandle(
                    symbol=symbol,
                    timeframe=tf,
                    exchange=tick_event.exchange,
                    security_id=tick_event.security_id,
                    start_time=start_utc,
                    end_time=end_utc,
                    initial_price=price,
                    initial_volume=volume
                )
            elif tick_time >= current_candle.end_time:
                # Boundary crossed: Finalize existing candle
                closed_candle_event = current_candle.to_market_event(MarketEventType.CANDLE_CLOSED)
                if closed_candle_event.event_id not in self._closed_candle_ids:
                    self._closed_candle_ids.add(closed_candle_event.event_id)
                    closed_events.append(closed_candle_event)

                    logger.debug(
                        f"Candle closed: symbol={symbol}, tf={tf}, close={closed_candle_event.close}, time={closed_candle_event.timestamp}",
                        extra={
                            "event": "candle_closed",
                            "symbol": symbol,
                            "timeframe": tf,
                            "event_id": closed_candle_event.event_id,
                            "open": float(closed_candle_event.open),
                            "high": float(closed_candle_event.high),
                            "low": float(closed_candle_event.low),
                            "close": float(closed_candle_event.close),
                            "timestamp": closed_candle_event.timestamp.isoformat()
                        }
                    )

                # Start the next candle
                self._active_candles[key] = InProgressCandle(
                    symbol=symbol,
                    timeframe=tf,
                    exchange=tick_event.exchange,
                    security_id=tick_event.security_id,
                    start_time=start_utc,
                    end_time=end_utc,
                    initial_price=price,
                    initial_volume=volume
                )
            else:
                # Update current active candle in-place
                current_candle.update(price, volume)

        return closed_events

    def flush_open_candles(self) -> List[MarketEvent]:
        """Flushes and finalizes all currently open candles."""
        closed_events: List[MarketEvent] = []
        for key, current_candle in list(self._active_candles.items()):
            closed_event = current_candle.to_market_event(MarketEventType.CANDLE_CLOSED)
            if closed_event.event_id not in self._closed_candle_ids:
                self._closed_candle_ids.add(closed_event.event_id)
                closed_events.append(closed_event)
        self._active_candles.clear()
        return closed_events
