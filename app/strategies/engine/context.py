from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal
from app.market_data.schemas import MarketEvent

class MarketContext(BaseModel):
    """
    Market and indicator state evaluated during strategy condition checks.
    """
    symbol: str
    timestamp: datetime
    timeframe: str = "5m"
    current_price: Optional[Decimal] = None
    previous_price: Optional[Decimal] = None
    candle: Optional[MarketEvent] = None
    previous_candle: Optional[MarketEvent] = None
    indicators: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

    def get_indicator(self, indicator_name: str, period: Optional[int] = None, is_previous: bool = False) -> Optional[float]:
        """
        Retrieves current or preceding indicator numeric value from the indicator context.
        Supports normalized key formats (e.g. 'RSI_14', 'RSI_14_PREV', 'RSI', 'RSI_PREV').
        """
        if not indicator_name:
            return None
        
        name_clean = indicator_name.strip().upper()
        candidates = []

        if period is not None:
            if is_previous:
                candidates.extend([
                    f"{name_clean}_{period}_PREV",
                    f"PREV_{name_clean}_{period}",
                    f"{name_clean}_PREV",
                    f"{name_clean}_{period}_PREVIOUS"
                ])
            else:
                candidates.extend([
                    f"{name_clean}_{period}",
                    f"{name_clean}_{period}_CURRENT",
                    name_clean
                ])
        else:
            if is_previous:
                candidates.extend([
                    f"{name_clean}_PREV",
                    f"PREV_{name_clean}",
                    f"{name_clean}_PREVIOUS"
                ])
            else:
                candidates.extend([
                    name_clean,
                    f"{name_clean}_CURRENT"
                ])

        # Lookup in indicators dict
        for key in candidates:
            if key in self.indicators and self.indicators[key] is not None:
                try:
                    return float(self.indicators[key])
                except (ValueError, TypeError):
                    continue

        return None
