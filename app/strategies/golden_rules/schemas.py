from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.strategies.golden_rules.enums import GoldenRuleStatus, GateDecision

class GoldenRuleEvaluationResult(BaseModel):
    """
    Evaluation outcome of an individual mandatory Golden Rule constraint.
    """
    rule_id: Optional[int] = None
    raw_text: str
    confirmation: str
    evaluation_type: str = "CANDLE_CLOSE"
    mandatory: bool = True
    status: GoldenRuleStatus
    observed_value: Optional[float] = None
    expected_value: Optional[float] = None
    threshold: Optional[float] = None
    reason: str

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class GoldenRulesGateResult(BaseModel):
    """
    Aggregated outcome of the mandatory Golden Rules gate.
    """
    strategy_id: int
    strategy_version_id: int
    event_id: str
    gate_decision: GateDecision
    all_passed: bool
    rules_evaluated: int
    rules_passed: int
    rules_failed: int
    rules_unavailable: int
    rule_results: List[GoldenRuleEvaluationResult] = Field(default_factory=list)
    reason: str

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }
