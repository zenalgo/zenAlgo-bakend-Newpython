from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.strategies.engine.enums import EvaluationStatus

class ConditionEvaluationResult(BaseModel):
    """
    Structured outcome of evaluating a single deterministic condition or logical node.
    """
    matched: bool = Field(..., description="Whether the condition evaluated to TRUE")
    status: EvaluationStatus = Field(..., description="Outcome status (MATCHED, NOT_MATCHED, DATA_UNAVAILABLE, ERROR)")
    rule_type: str = Field(..., description="Type of rule (e.g. INDICATOR_CROSSOVER, PRICE_COMPARISON, AND, OR)")
    current_value: Optional[float] = Field(None, description="Active market/indicator value during evaluation")
    previous_value: Optional[float] = Field(None, description="Preceding bar/tick value for crossover evaluation")
    threshold: Optional[float] = Field(None, description="Configured trigger threshold")
    operator: Optional[str] = Field(None, description="Operator applied (e.g. CROSS_ABOVE, GREATER_THAN)")
    reason: str = Field(..., description="Deterministic human-readable explanation of the result")
    raw_text: Optional[str] = Field(None, description="Raw rule string representation")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class StrategyEvaluationResult(BaseModel):
    """
    Aggregated evaluation outcome for a StrategyRoute across all its configured conditions.
    """
    strategy_id: int
    strategy_version_id: int
    event_id: str
    route_type: str # ENTRY or EXIT
    status: EvaluationStatus
    overall_matched: bool
    condition_results: List[ConditionEvaluationResult] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }
