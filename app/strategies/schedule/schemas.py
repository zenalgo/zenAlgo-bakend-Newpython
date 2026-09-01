from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
import re
from zoneinfo import ZoneInfo
from app.strategies.enums import StrategyHorizon, ScheduleEvaluationReason
from app.core.exceptions import ValidationError

VALID_WEEKDAYS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}

class NormalizedSchedule(BaseModel):
    """
    Standardized, internal representation of a strategy's schedule and timing constraints.
    """
    horizon: StrategyHorizon
    entry_time: str = Field(..., description="Daily entry window start in HH:MM (IST)")
    entry_to: Optional[str] = Field(None, description="Daily entry window end in HH:MM (IST)")
    forced_exit_time: str = Field(..., description="Mandatory square-off/forced exit time in HH:MM (IST)")
    entry_days: List[str] = Field(default_factory=list, description="Days of week for entry in uppercase (MONDAY, etc.)")
    exit_days: List[str] = Field(default_factory=list, description="Days of week for exit in uppercase (TUESDAY, etc.)")
    weekly_cycle_scope: Optional[str] = Field(None, description="Scope of weekly cycle (SAME_WEEK, NEXT_WEEK)")
    applicable_months: List[str] = Field(default_factory=list, description="Eligible months normalized (e.g. 2026-08, Aug-2026)")
    selected_monthly_date: Optional[str] = Field(None, description="Specific calendar date or day of month")
    timezone: str = Field(default="Asia/Kolkata", description="Trading timezone for market evaluation")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

    @field_validator("entry_time", "forced_exit_time", "entry_to")
    @classmethod
    def validate_time_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = str(v).strip()
        match = re.match(r"^(\d{2}):(\d{2})$", cleaned)
        if not match:
            raise ValidationError(f"Time '{v}' is invalid. Must be in HH:MM format (24-hour).")
        hours, minutes = int(match.group(1)), int(match.group(2))
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValidationError(f"Time '{v}' has invalid hour ({hours}) or minute ({minutes}).")
        return cleaned

    @field_validator("timezone")
    @classmethod
    def validate_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
            return v
        except Exception:
            raise ValidationError(f"Invalid timezone: '{v}'.")

    @model_validator(mode="after")
    def validate_time_order(self) -> "NormalizedSchedule":
        if self.entry_time >= self.forced_exit_time:
            raise ValidationError(
                f"Invalid timing constraint: entry_time ({self.entry_time}) must be before forced_exit_time ({self.forced_exit_time})."
            )
        if self.entry_to:
            if self.entry_to < self.entry_time:
                raise ValidationError(
                    f"Invalid timing constraint: entry_to ({self.entry_to}) cannot be earlier than entry_time ({self.entry_time})."
                )
            if self.entry_to > self.forced_exit_time:
                raise ValidationError(
                    f"Invalid timing constraint: entry_to ({self.entry_to}) cannot be later than forced_exit_time ({self.forced_exit_time})."
                )
        return self

class ScheduleEvaluationResult(BaseModel):
    """
    Structured result returned by ScheduleEvaluator indicating whether a strategy is eligible.
    """
    eligible: bool
    reason: ScheduleEvaluationReason
    horizon: StrategyHorizon
    evaluation_time: str
    current_time: str
    entry_time: str
    forced_exit_time: str
    timezone: str
    details: Optional[dict] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

