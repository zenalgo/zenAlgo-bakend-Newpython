from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

class BaseIndicatorProvider(ABC):
    """
    Abstract interface for retrieving technical indicator values.
    """
    @abstractmethod
    def get_indicator_context(self, symbol: str, timeframe: str, timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """Returns key-value map of active technical indicator values for symbol and timeframe."""
        pass

class InMemoryIndicatorProvider(BaseIndicatorProvider):
    """
    In-memory indicator store for condition evaluation and tests.
    """
    def __init__(self):
        # Key: (symbol, timeframe) -> Dict[indicator_key, value]
        self._indicators: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def set_indicator(
        self,
        symbol: str,
        timeframe: str,
        indicator_key: str,
        current_value: float,
        previous_value: Optional[float] = None
    ) -> None:
        """Stores current and optional previous indicator values for a symbol/timeframe."""
        key = (symbol.strip().upper(), timeframe.strip().lower())
        if key not in self._indicators:
            self._indicators[key] = {}
        
        norm_key = indicator_key.strip().upper()
        self._indicators[key][norm_key] = current_value
        if previous_value is not None:
            self._indicators[key][f"{norm_key}_PREV"] = previous_value

    def get_indicator_context(self, symbol: str, timeframe: str, timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        key = (symbol.strip().upper(), timeframe.strip().lower())
        return dict(self._indicators.get(key, {}))

    def clear(self) -> None:
        self._indicators.clear()

# Global default provider
default_indicator_provider = InMemoryIndicatorProvider()
