import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional
from app.strategies.enums import StrategyHorizon
from app.strategies.schedule.schemas import NormalizedSchedule
from app.core.exceptions import ValidationError

VALID_WEEKDAYS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}

def validate_time_format(time_str: str, field_name: str) -> None:
    """Validates HH:MM time format and logical bounds (00:00 to 23:59)."""
    if not time_str or not isinstance(time_str, str):
        raise ValidationError(f"{field_name} is required and must be a string")
    
    match = re.match(r"^(\d{2}):(\d{2})$", time_str.strip())
    if not match:
        raise ValidationError(f"{field_name} '{time_str}' is invalid. Must be in HH:MM format (24-hour).")
    
    hours, minutes = int(match.group(1)), int(match.group(2))
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise ValidationError(f"{field_name} '{time_str}' has invalid hour ({hours}) or minute ({minutes}).")

def validate_monthly_date_string(date_str: str) -> None:
    """Validates date format and ensures no impossible calendar dates (e.g., Feb 31)."""
    if not date_str or not isinstance(date_str, str):
        return
    
    cleaned = date_str.strip()
    # Check ISO format: YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned):
        try:
            datetime.strptime(cleaned, "%Y-%m-%d")
            return
        except ValueError as e:
            raise ValidationError(f"Invalid monthly date '{date_str}': {str(e)}")
    
    # Check custom format: YYYY-Mon-D (e.g. 2026-Aug-5)
    if re.match(r"^\d{4}-[A-Za-z]{3}-\d{1,2}$", cleaned):
        try:
            datetime.strptime(cleaned, "%Y-%b-%d")
            return
        except ValueError as e:
            raise ValidationError(f"Invalid monthly date '{date_str}': {str(e)}")
        
    # Check single day of month: integer 1..31
    if cleaned.isdigit():
        day_num = int(cleaned)
        if not (1 <= day_num <= 31):
            raise ValidationError(f"Invalid day of month '{date_str}'. Must be between 1 and 31.")
        return

    # If format doesn't match any known pattern
    raise ValidationError(f"Invalid monthly date format '{date_str}'. Supported: YYYY-MM-DD, YYYY-Mon-D, or day number 1-31.")

def validate_normalized_schedule(schedule: NormalizedSchedule) -> None:
    """
    Validates a NormalizedSchedule instance. Raises ValidationError if constraints are violated.
    """
    # 1. Timezone Validation
    try:
        ZoneInfo(schedule.timezone)
    except Exception:
        raise ValidationError(f"Invalid timezone: '{schedule.timezone}'. Must be a valid IANA timezone (e.g., 'Asia/Kolkata').")

    # 2. Time Formats Validation
    validate_time_format(schedule.entry_time, "entry_time")
    validate_time_format(schedule.forced_exit_time, "forced_exit_time")

    if schedule.entry_to:
        validate_time_format(schedule.entry_to, "entry_to")

    # 3. Time Ordering: entry_time must be strictly before forced_exit_time
    if schedule.entry_time >= schedule.forced_exit_time:
        raise ValidationError(
            f"Invalid timing constraint: entry_time ({schedule.entry_time}) must be before forced_exit_time ({schedule.forced_exit_time})."
        )

    if schedule.entry_to:
        if schedule.entry_to < schedule.entry_time:
            raise ValidationError(
                f"Invalid timing constraint: entry_to ({schedule.entry_to}) cannot be earlier than entry_time ({schedule.entry_time})."
            )
        if schedule.entry_to > schedule.forced_exit_time:
            raise ValidationError(
                f"Invalid timing constraint: entry_to ({schedule.entry_to}) cannot be later than forced_exit_time ({schedule.forced_exit_time})."
            )

    # 4. Weekdays Validation
    for day in schedule.entry_days:
        if day not in VALID_WEEKDAYS:
            raise ValidationError(f"Invalid entry day: '{day}'. Must be one of {sorted(VALID_WEEKDAYS)}")

    for day in schedule.exit_days:
        if day not in VALID_WEEKDAYS:
            raise ValidationError(f"Invalid exit day: '{day}'. Must be one of {sorted(VALID_WEEKDAYS)}")

    # 5. Monthly Specifics Validation
    if schedule.horizon == StrategyHorizon.MONTHLY:
        if schedule.selected_monthly_date:
            validate_monthly_date_string(schedule.selected_monthly_date)
