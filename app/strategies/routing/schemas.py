from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.strategies.enums import StrategyLifecycleState
from app.market_data.enums import MarketEventType
from app.strategies.routing.enums import RouteType, RouteSkipReason

class CandidateStrategy(BaseModel):
    """
    In-memory descriptor of a strategy registered for real-time market event routing.
    """
    strategy_id: int
    strategy_version_id: int
    symbol: str
    security_id: Optional[str] = None
    timeframe: str = "5m"
    lifecycle_state: StrategyLifecycleState = StrategyLifecycleState.WAITING
    is_active: bool = True

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class StrategyRoute(BaseModel):
    """
    Structured routing instruction directing a MarketEvent to a specific strategy and route handler.
    """
    strategy_id: int
    strategy_version_id: int
    lifecycle_state: StrategyLifecycleState
    event_id: str
    route_type: RouteType
    symbol: str
    timeframe: str
    event_type: MarketEventType
    timestamp: datetime

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class RouteSkip(BaseModel):
    """
    Traceable log descriptor explaining why a candidate strategy was skipped for a market event.
    """
    strategy_id: int
    reason: RouteSkipReason
    details: Optional[str] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class RoutingDecisionResult(BaseModel):
    """
    Aggregated result of evaluating a single MarketEvent across all candidate strategies.
    """
    event_id: str
    matched_routes: List[StrategyRoute] = Field(default_factory=list)
    skipped_routes: List[RouteSkip] = Field(default_factory=list)

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }
