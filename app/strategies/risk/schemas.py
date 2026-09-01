from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal

from app.strategies.risk.enums import (
    RiskDecisionType,
    RiskCheckType,
    RiskFailureCode,
    RiskSizingMode
)

class RiskCheckResult(BaseModel):
    """
    Structured outcome of a single deterministic risk check in the pipeline.
    """
    check_type: RiskCheckType = Field(..., description="Type of risk check evaluated")
    passed: bool = Field(..., description="Whether this specific check passed")
    failure_code: Optional[RiskFailureCode] = Field(None, description="Standardized failure code if rejected")
    actual_value: Optional[str] = Field(None, description="Observed runtime value (e.g. current daily loss ₹5200)")
    configured_limit: Optional[str] = Field(None, description="Configured limit threshold (e.g. max daily loss ₹5000)")
    reason: str = Field(..., description="Human-readable explanation of check outcome")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class StrategyRiskProfile(BaseModel):
    """
    Configuration parameters governing strategy-level and user-level risk limits.
    Derived strictly from the active StrategyVersion metadata.
    """
    strategy_id: int = Field(..., description="Strategy identifier")
    strategy_version_id: int = Field(..., description="Exact active StrategyVersion ID")
    max_loss_per_trade: Optional[Decimal] = Field(None, description="Maximum allowable loss for a single execution")
    max_loss_per_day: Optional[Decimal] = Field(None, description="Maximum allowable loss for a single calendar day")
    max_loss_per_week: Optional[Decimal] = Field(None, description="Maximum allowable cumulative loss across the current calendar week")
    max_trades_per_day: int = Field(10, description="Maximum execution trade packages allowed per day")
    max_open_positions: int = Field(1, description="Maximum concurrent running positions allowed per strategy")
    consecutive_loss_limit: int = Field(3, description="Maximum allowable consecutive losses before halting/sizing down")
    cooldown_minutes: int = Field(0, description="Mandatory quiet time in minutes required after position exit")
    sizing_mode: RiskSizingMode = Field(RiskSizingMode.FIXED_LOTS, description="Position sizing model")
    capital_allocation_pct: Optional[Decimal] = Field(None, description="Capital allocation percentage per trade")
    after_loss_action: str = Field("STOP_STRATEGY", description="Action upon breach: STOP_STRATEGY or REDUCE_SIZE")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

class UserRiskEvaluationResult(BaseModel):
    """
    Complete user-isolated risk evaluation outcome for a single StrategySignal.
    Contains full explainability timeline and approved execution sizing parameters.
    """
    user_id: int = Field(..., description="Target user identifier")
    strategy_id: int = Field(..., description="Strategy identifier")
    strategy_version_id: int = Field(..., description="Exact active StrategyVersion ID evaluated")
    signal_id: int = Field(..., description="Correlated StrategySignal ID")
    decision: RiskDecisionType = Field(..., description="Final decision: APPROVED or REJECTED")
    approved_lots: int = Field(1, description="Approved order quantity in lots (multiplied by lot_size in Step 10)")
    required_capital: Decimal = Field(Decimal("0.00"), description="Estimated required margin/capital for this execution package")
    sizing_mode: RiskSizingMode = Field(RiskSizingMode.FIXED_LOTS, description="Applied sizing model")
    failure_code: Optional[RiskFailureCode] = Field(None, description="Primary failure code if decision is REJECTED")
    reason: str = Field(..., description="Comprehensive explainability summary for Admin and user audit trails")
    checks: List[RiskCheckResult] = Field(default_factory=list, description="Timeline list of all individual risk checks executed")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC evaluation timestamp")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }
