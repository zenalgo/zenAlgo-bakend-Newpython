from typing import Optional, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import BaseModel, Field

from app.strategies.exits.enums import ExitType, ExitDecision, PositionDirection

class ExitEvaluationResult(BaseModel):
    """Structured result of evaluating an exit condition against an open position."""
    decision: ExitDecision
    exit_type: Optional[ExitType] = None
    trigger_price: Optional[Decimal] = None
    exit_quantity_pct: Decimal = Field(default=Decimal("100.0"), description="Percentage of lots to exit (100.0 for full, 50.0 for partial)")
    reason: str
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic metric snapshots for full explainability")


class TrailingStopState(BaseModel):
    """Runtime and durable trailing stop state for an active execution."""
    execution_id: int
    direction: PositionDirection = PositionDirection.BUY
    entry_price: Decimal
    initial_stop_loss: Decimal
    current_trailing_stop: Decimal
    highest_favorable_price: Decimal
    lowest_favorable_price: Decimal
    step_r: Decimal = Decimal("1.0")
    is_breakeven_activated: bool = False
    last_updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
