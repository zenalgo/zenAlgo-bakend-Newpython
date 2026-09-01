from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from decimal import Decimal

from app.strategies.signals.enums import SignalType, SignalDirection, SignalStatus

def build_deterministic_signal_key(
    strategy_id: int,
    strategy_version_id: int,
    signal_type: str,
    market_event_key: str
) -> str:
    """
    Constructs a deterministic, immutable business key for a strategy signal.
    Format: '{strategy_id}:{strategy_version_id}:{signal_type}:{market_event_key}'
    """
    st = str(signal_type.value if hasattr(signal_type, "value") else signal_type).upper()
    return f"{strategy_id}:{strategy_version_id}:{st}:{market_event_key}"

class TradingSignal(BaseModel):
    """
    Strongly typed Pydantic domain representation of a verified strategy trading decision.
    """
    signal_id: Optional[int] = Field(None, description="Database primary key once persisted")
    signal_key: str = Field(..., description="Deterministic business identity key")
    strategy_id: int = Field(..., description="Strategy identifier")
    strategy_version_id: int = Field(..., description="Exact active StrategyVersion that generated this decision")
    market_event_key: str = Field(..., description="Correlated market event processing key")
    event_id: str = Field(..., description="Canonical MarketEvent ID")
    symbol: str = Field(..., description="Underlying asset symbol (e.g. NIFTY)")
    timeframe: str = Field("5m", description="Strategy evaluation timeframe")
    signal_type: SignalType = Field(SignalType.ENTRY, description="Signal type (ENTRY or EXIT)")
    direction: SignalDirection = Field(SignalDirection.BUY, description="Trade direction (BUY or SELL)")
    price: Optional[Decimal] = Field(None, description="Observed trigger market price during evaluation")
    status: SignalStatus = Field(SignalStatus.CREATED, description="Current signal lifecycle status")
    reason: Optional[str] = Field(None, description="Explainability reason explaining condition and gate outcomes")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC creation timestamp")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }
