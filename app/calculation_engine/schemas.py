"""
Calculation Engine — Pydantic Schemas
All request/response models for the calculation engine REST + WebSocket API.
"""
from __future__ import annotations
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Indicator value
# ---------------------------------------------------------------------------

class IndicatorValue(BaseModel):
    """A single resolved indicator value with its trading signal."""
    name: str                           # e.g. "RSI", "MACD", "VWAP"
    display_name: str                   # e.g. "RSI (14)", "VWAP (Session)"
    value: Optional[float] = None       # Primary numeric value
    secondary: Optional[Dict[str, float]] = None   # Extra values (MACD: signal/hist, BB: upper/lower, etc.)
    signal: str = "NEUTRAL"            # "BUY", "SELL", "NEUTRAL"
    signal_color: str = "amber"        # "green", "red", "amber"
    description: str = ""              # Human-readable interpretation
    history: List[float] = Field(default_factory=list)  # Last 20 values for sparkline


# ---------------------------------------------------------------------------
# Full indicator snapshot for a symbol
# ---------------------------------------------------------------------------

class IndicatorSnapshot(BaseModel):
    """Complete real-time indicator snapshot for one symbol + timeframe."""
    symbol: str
    timeframe: str
    timestamp: datetime
    ltp: Optional[float] = None          # Last Traded Price
    vwap: Optional[float] = None         # Session VWAP (updated on every tick)
    indicators: List[IndicatorValue] = Field(default_factory=list)
    candle_count: int = 0               # How many confirmed candles in the window
    is_market_hours: bool = True
    data_source: str = "DHAN"           # "DHAN" or "YFINANCE"

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Signal / condition-fire event
# ---------------------------------------------------------------------------

class SignalEvent(BaseModel):
    """Fired when a strategy entry/exit condition is satisfied."""
    event_id: str
    timestamp: datetime
    symbol: str
    timeframe: str
    strategy_id: int
    strategy_name: str
    condition_id: int
    condition_text: str                 # Human-readable rule text
    rule_json: Dict[str, Any]           # Parsed rule_json object
    indicator_name: str
    indicator_value: float
    signal: str                         # "ENTRY" or "EXIT"
    trigger_type: str                   # "TICK" (real-time) or "CANDLE_CLOSE"


# ---------------------------------------------------------------------------
# Engine status
# ---------------------------------------------------------------------------

class LiveEngineStatusItem(BaseModel):
    symbol: str
    timeframe: str
    is_running: bool
    started_at: Optional[datetime] = None
    last_snapshot_at: Optional[datetime] = None
    candle_count: int = 0
    data_source: str = "DHAN"
    websocket_connected: bool = False
    fallback_polling: bool = False


# ---------------------------------------------------------------------------
# REST request bodies
# ---------------------------------------------------------------------------

class StartEngineRequest(BaseModel):
    symbol: str = Field(..., description="e.g. NIFTY, BANKNIFTY, RELIANCE")
    security_id: Optional[str] = Field(None, description="Dhan security ID for REST candle fetch")
    exchange: str = Field("NSE_EQ", description="Dhan exchange segment")
    timeframe: str = Field("5m", description="Candle timeframe: 1m, 5m, 15m, 1h")
    broker_account_id: Optional[int] = Field(None, description="Admin-selected broker account ID for credentials")
