from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal

from app.execution.enums import (
    ExecutionStatus,
    ExecutionMode,
    OrderType,
    LegRole,
    OptionStrikePolicy,
    OptionExpiryPolicy
)

class LogicalLeg(BaseModel):
    """
    Represents the logical instruction for an individual trade leg prior to live contract resolution.
    Does NOT contain hardcoded broker security IDs or static market prices.
    """
    leg_id: int = Field(..., description="Unique leg identifier within the strategy version")
    sequence: int = Field(1, description="Execution sequence priority (e.g. 1 for hedge, 2 for short)")
    role: LegRole = Field(LegRole.PRIMARY, description="Role: PRIMARY, HEDGE, PROTECTION, ENTRY, EXIT")
    side: str = Field(..., description="BUY or SELL")
    segment: str = Field("OPT", description="Segment: OPT, FUT, EQ")
    option_type: Optional[str] = Field(None, description="CE or PE for options")
    strike_policy: OptionStrikePolicy = Field(OptionStrikePolicy.ATM, description="ATM, OTM, ITM, CUSTOM")
    strike_offset: Optional[Decimal] = Field(Decimal("0.00"), description="Strike offset from baseline (e.g. +200 for hedge)")
    expiry_policy: OptionExpiryPolicy = Field(OptionExpiryPolicy.CURRENT_WEEKLY, description="Weekly or Monthly selection")
    lots: int = Field(1, description="Requested lot quantity")
    order_type: OrderType = Field(OrderType.MARKET, description="MARKET, LIMIT, SL, SLM")
    limit_price: Optional[Decimal] = Field(None, description="Optional limit price for LIMIT orders")
    trigger_price: Optional[Decimal] = Field(None, description="Optional trigger price for SL orders")

    @field_validator("lots")
    @classmethod
    def validate_lots_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Leg lots must be strictly positive (> 0)")
        return v

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class ResolvedLeg(BaseModel):
    """
    Represents a fully resolved broker-executable contract mapped from a LogicalLeg in Step 10D.
    """
    leg_id: int
    sequence: int
    role: LegRole
    trading_symbol: str
    security_id: str
    exchange: str = "NSE"
    exchange_segment: str = "NSE_FN"
    side: str
    quantity: int
    lot_size: int
    lots: int
    price: Decimal = Decimal("0.00")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class ExecutionRequest(BaseModel):
    """
    Canonical, strongly typed execution contract emitted by the Risk Engine upon user approval.
    Immutable execution request containing all parameters necessary for broker order construction.
    """
    user_id: int = Field(..., description="Target user identifier")
    strategy_id: int = Field(..., description="Strategy identifier")
    strategy_version_id: int = Field(..., description="Exact active StrategyVersion ID")
    signal_id: int = Field(..., description="Triggering StrategySignal ID")
    signal_type: str = Field("ENTRY", description="ENTRY or EXIT")
    direction: str = Field("BUY", description="Primary strategy direction: BUY or SELL")
    execution_mode: ExecutionMode = Field(ExecutionMode.PAPER, description="MOCK, PAPER, LIVE")
    underlying: str = Field(..., description="Underlying symbol (e.g. NIFTY, RELIANCE)")
    correlation_id: str = Field(..., description="Deterministic correlation ID tracking this execution")
    legs: List[LogicalLeg] = Field(..., description="Logical trade legs comprising this execution package")
    approved_lots: int = Field(1, description="Risk-approved multiplier lots")
    required_capital: Decimal = Field(Decimal("0.00"), description="Risk-approved required capital")
    slippage_tolerance_pct: Optional[Decimal] = Field(Decimal("0.5"), description="Slippage constraint percentage")
    order_timeout_seconds: int = Field(30, description="Broker response timeout constraint")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Request creation timestamp")

    @field_validator("legs")
    @classmethod
    def validate_legs_non_empty(cls, v: List[LogicalLeg]) -> List[LogicalLeg]:
        if not v:
            raise ValueError("ExecutionRequest must contain at least one trade leg")
        return v

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class ExecutionLegResult(BaseModel):
    """
    Detailed broker submission and fill tracking outcome for an individual leg.
    """
    leg_id: int
    broker_order_id: Optional[str] = None
    correlation_id: str
    status: ExecutionStatus = ExecutionStatus.CREATED
    filled_quantity: int = 0
    remaining_quantity: int = 0
    average_fill_price: Decimal = Decimal("0.00")
    rejection_reason: Optional[str] = None
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }


class ExecutionResult(BaseModel):
    """
    Canonical execution package result outcome returned to higher-level orchestrators.
    """
    user_id: int
    strategy_id: int
    strategy_version_id: int
    signal_id: int
    execution_id: Optional[int] = None
    correlation_id: str
    status: ExecutionStatus
    leg_results: List[ExecutionLegResult] = Field(default_factory=list)
    total_filled_quantity: int = 0
    total_realized_pnl: Decimal = Decimal("0.00")
    rejection_reason: Optional[str] = None
    completed_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }
