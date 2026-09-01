from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional, Union
import logging

from app.market_data.enums import MarketEventType
from app.market_data.schemas import MarketEvent
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

def build_deterministic_event_id(
    symbol: str,
    timeframe: str,
    event_type: Union[MarketEventType, str],
    timestamp: datetime
) -> str:
    """Constructs a deterministic unique event identifier."""
    event_type_str = event_type.value if hasattr(event_type, "value") else str(event_type)
    ts_iso = timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return f"{symbol.strip().upper()}:{timeframe.strip()}:{event_type_str}:{ts_iso}"

class BaseMarketDataAdapter(ABC):
    """
    Abstract adapter for transforming raw broker-specific market data feeds into canonical MarketEvents.
    """
    @abstractmethod
    def normalize_raw_feed_frame(self, raw_frame: Dict[str, Any]) -> List[MarketEvent]:
        """Parses and normalizes a raw feed payload dictionary into one or more MarketEvents."""
        pass

class DhanMarketDataAdapter(BaseMarketDataAdapter):
    """
    Concrete adapter for Dhan HQ Market Feed WebSocket packets and REST quote responses.
    """
    # Mapping for Dhan exchange segment codes to standardized exchange names
    EXCHANGE_MAP = {
        "NSE_EQ": "NSE",
        "NSE_FNO": "NFO",
        "NSE_CURRENCY": "CDS",
        "BSE_EQ": "BSE",
        "BSE_FNO": "BFO",
        "MCX_COMM": "MCX",
        "NSE": "NSE",
        "NFO": "NFO",
        "BSE": "BSE",
        "MCX": "MCX"
    }

    def normalize_raw_feed_frame(self, raw_frame: Dict[str, Any]) -> List[MarketEvent]:
        if not raw_frame or not isinstance(raw_frame, dict):
            raise ValidationError("Raw feed frame must be a non-empty dictionary.")

        # 1. Extract Symbol
        raw_symbol = (
            raw_frame.get("symbol") or 
            raw_frame.get("tradingSymbol") or 
            raw_frame.get("instrument") or
            raw_frame.get("securityId")
        )
        if not raw_symbol:
            raise ValidationError("Market feed frame missing required symbol / tradingSymbol / securityId.")
        symbol = str(raw_symbol).strip().upper()

        # 2. Extract Price (LTP)
        raw_price = (
            raw_frame.get("ltp") or 
            raw_frame.get("LTP") or 
            raw_frame.get("price") or 
            raw_frame.get("lastPrice") or
            raw_frame.get("close")
        )
        if raw_price is None:
            raise ValidationError(f"Market feed frame for symbol '{symbol}' missing price/LTP field.")
        try:
            price = Decimal(str(raw_price))
        except Exception as e:
            raise ValidationError(f"Invalid price value '{raw_price}' in market feed frame: {str(e)}")

        # 3. Extract Security ID and Exchange
        security_id = str(raw_frame.get("securityId") or raw_frame.get("security_id") or "").strip() or None
        raw_exchange = str(raw_frame.get("exchangeSegment") or raw_frame.get("exchange") or "NSE").strip().upper()
        exchange = self.EXCHANGE_MAP.get(raw_exchange, "NSE")

        # 4. Extract and Normalize Timestamp to UTC
        raw_ts = (
            raw_frame.get("timestamp") or 
            raw_frame.get("last_trade_time") or 
            raw_frame.get("ltt") or 
            raw_frame.get("time") or
            raw_frame.get("feedTime")
        )
        event_time: datetime
        if raw_ts is None:
            event_time = datetime.now(timezone.utc)
        elif isinstance(raw_ts, (int, float)):
            # Handle epoch in seconds or milliseconds
            if raw_ts > 1e11: # Milliseconds
                event_time = datetime.fromtimestamp(raw_ts / 1000.0, tz=timezone.utc)
            else: # Seconds
                event_time = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
        elif isinstance(raw_ts, str):
            try:
                # Try ISO format
                event_time = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                if event_time.tzinfo is None:
                    event_time = event_time.replace(tzinfo=timezone.utc)
                else:
                    event_time = event_time.astimezone(timezone.utc)
            except Exception:
                try:
                    # Try datetime format "%Y-%m-%d %H:%M:%S"
                    event_time = datetime.strptime(raw_ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                except Exception:
                    event_time = datetime.now(timezone.utc)
        elif isinstance(raw_ts, datetime):
            if raw_ts.tzinfo is None:
                event_time = raw_ts.replace(tzinfo=timezone.utc)
            else:
                event_time = raw_ts.astimezone(timezone.utc)
        else:
            event_time = datetime.now(timezone.utc)

        # 5. Extract Event Type and Timeframe
        raw_type = raw_frame.get("event_type") or raw_frame.get("type") or MarketEventType.TICK
        if isinstance(raw_type, MarketEventType):
            event_type = raw_type
        else:
            type_str = str(raw_type).strip().upper()
            try:
                event_type = MarketEventType(type_str)
            except ValueError:
                event_type = MarketEventType.TICK

        timeframe = str(raw_frame.get("timeframe") or "TICK").strip()

        # 6. Extract OHLCV if present
        def parse_decimal(val):
            return Decimal(str(val)) if val is not None else None

        open_p = parse_decimal(raw_frame.get("open"))
        high_p = parse_decimal(raw_frame.get("high"))
        low_p = parse_decimal(raw_frame.get("low"))
        close_p = parse_decimal(raw_frame.get("close")) or price
        volume = int(raw_frame["volume"]) if raw_frame.get("volume") is not None else None

        # 7. Generate Deterministic Event ID
        event_id = build_deterministic_event_id(symbol, timeframe, event_type, event_time)

        event = MarketEvent(
            event_id=event_id,
            symbol=symbol,
            security_id=security_id,
            exchange=exchange,
            event_type=event_type,
            timestamp=event_time,
            timeframe=timeframe,
            price=price,
            open=open_p,
            high=high_p,
            low=low_p,
            close=close_p,
            volume=volume,
            raw_data=raw_frame
        )

        return [event]
