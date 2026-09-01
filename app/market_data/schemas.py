from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from decimal import Decimal
from app.market_data.enums import MarketEventType, FeedConnectionState
from app.core.exceptions import ValidationError

class MarketEvent(BaseModel):
    """
    Canonical, normalized market data event representation used across the trading engine.
    """
    event_id: str = Field(..., description="Deterministic unique event identity")
    symbol: str = Field(..., description="Normalized asset symbol in uppercase (e.g., NIFTY, BANKNIFTY)")
    security_id: Optional[str] = Field(None, description="Broker-specific security ID")
    exchange: str = Field("NSE", description="Exchange code (NSE, NFO, BSE, MCX)")
    event_type: MarketEventType = Field(..., description="Nature of event (TICK, CANDLE_CLOSED, etc.)")
    timestamp: datetime = Field(..., description="Timezone-aware UTC timestamp when event occurred")
    timeframe: str = Field("TICK", description="Timeframe code (TICK, 1m, 5m, 15m, 1d)")
    price: Optional[Decimal] = Field(None, description="Last Traded Price (LTP)")
    open: Optional[Decimal] = Field(None, description="Candle Open Price")
    high: Optional[Decimal] = Field(None, description="Candle High Price")
    low: Optional[Decimal] = Field(None, description="Candle Low Price")
    close: Optional[Decimal] = Field(None, description="Candle Close Price")
    volume: Optional[int] = Field(None, description="Traded Volume")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Original unparsed broker payload snippet for traceability")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValidationError("MarketEvent symbol must be a non-empty string.")
        return v.strip().upper()

    @field_validator("timestamp")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

class FeedStatus(BaseModel):
    """
    Observability model reflecting current health and metrics of the Market Data Service.
    """
    state: FeedConnectionState
    connected_at: Optional[datetime] = None
    last_event_time: Optional[datetime] = None
    subscribed_symbols: List[str] = Field(default_factory=list)
    total_events_received: int = 0
    total_events_dropped: int = 0

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }
