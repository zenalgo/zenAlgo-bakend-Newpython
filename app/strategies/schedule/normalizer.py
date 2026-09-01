import json
import re
import logging
from typing import Optional, Union, Dict, Any, List
from app.strategies.enums import StrategyHorizon
from app.strategies.schemas import StrategyRequest, ScheduleConfig, InstrumentConfig
from app.strategies.models import Strategy, StrategyVersion
from app.strategies.schedule.schemas import NormalizedSchedule
from app.strategies.schedule.validator import validate_normalized_schedule
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

DAY_MAP = {
    "MON": "MONDAY", "MONDAY": "MONDAY",
    "TUE": "TUESDAY", "TUESDAY": "TUESDAY",
    "WED": "WEDNESDAY", "WEDNESDAY": "WEDNESDAY",
    "THU": "THURSDAY", "THURSDAY": "THURSDAY",
    "FRI": "FRIDAY", "FRIDAY": "FRIDAY",
    "SAT": "SATURDAY", "SATURDAY": "SATURDAY",
    "SUN": "SUNDAY", "SUNDAY": "SUNDAY"
}

def normalize_horizon(raw_horizon: Optional[Union[str, StrategyHorizon]]) -> StrategyHorizon:
    """Normalizes string or enum representation of strategy horizon."""
    if not raw_horizon:
        return StrategyHorizon.INTRADAY
    
    if isinstance(raw_horizon, StrategyHorizon):
        return raw_horizon
    
    clean = str(raw_horizon).strip().upper()
    if clean in ("INTRADAY", "DAY", "DAILY"):
        return StrategyHorizon.INTRADAY
    elif clean in ("WEEKLY", "WEEK"):
        return StrategyHorizon.WEEKLY
    elif clean in ("MONTHLY", "MONTH"):
        return StrategyHorizon.MONTHLY
    else:
        raise ValidationError(f"Invalid strategy horizon / expiryType: '{raw_horizon}'. Supported: INTRADAY, WEEKLY, MONTHLY.")

def normalize_day(day_str: str) -> str:
    """Normalizes day name to full uppercase weekday name."""
    clean = str(day_str).strip().upper()
    if clean in DAY_MAP:
        return DAY_MAP[clean]
    raise ValidationError(f"Invalid weekday name: '{day_str}'.")

def normalize_schedule(
    request_or_dict: Optional[Union[StrategyRequest, Dict[str, Any], Strategy, StrategyVersion]] = None,
    default_horizon: Optional[StrategyHorizon] = None
) -> NormalizedSchedule:
    """
    Constructs and returns a validated NormalizedSchedule from various strategy input formats.
    """
    raw_schedule: Dict[str, Any] = {}
    raw_instrument: Dict[str, Any] = {}
    raw_horizon: Optional[str] = None
    trading_type: Optional[str] = None
    strategy_id: Optional[int] = None
    strategy_version_id: Optional[int] = None

    if request_or_dict is None:
        raw_schedule = {}
    elif isinstance(request_or_dict, StrategyRequest):
        if request_or_dict.schedule:
            raw_schedule = request_or_dict.schedule.model_dump(by_alias=True)
        if request_or_dict.instrument:
            raw_instrument = request_or_dict.instrument.model_dump(by_alias=True)
            raw_horizon = request_or_dict.instrument.expiryType
        trading_type = request_or_dict.tradingType
    elif isinstance(request_or_dict, dict):
        raw_schedule = request_or_dict.get("schedule") or request_or_dict.get("timing") or request_or_dict
        raw_instrument = request_or_dict.get("instrument") or {}
        raw_horizon = raw_instrument.get("expiryType") or request_or_dict.get("expiryType") or request_or_dict.get("tradingType") or request_or_dict.get("horizon")
    elif isinstance(request_or_dict, Strategy):
        strategy_id = request_or_dict.id
        strategy_version_id = request_or_dict.current_version_id
        if request_or_dict.parameters:
            try:
                params = json.loads(request_or_dict.parameters)
                raw_schedule = params.get("schedule") or {}
                raw_instrument = params.get("instrument") or {}
                raw_horizon = raw_instrument.get("expiryType") or params.get("expiryType")
            except Exception:
                pass
    elif isinstance(request_or_dict, StrategyVersion):
        strategy_id = request_or_dict.strategy_id
        strategy_version_id = request_or_dict.id
        trading_type = request_or_dict.trading_type
        if request_or_dict.entry_setting:
            raw_schedule["entryFrom"] = request_or_dict.entry_setting.entry_time
        if request_or_dict.exit_setting:
            raw_schedule["forcedExitTime"] = request_or_dict.exit_setting.exit_time
        if request_or_dict.entry_days:
            raw_schedule["entryDays"] = [d.day_of_week for d in request_or_dict.entry_days]

    # Determine horizon
    if default_horizon:
        horizon = default_horizon
    elif raw_horizon:
        horizon = normalize_horizon(raw_horizon)
    elif trading_type:
        horizon = normalize_horizon(trading_type)
    else:
        horizon = StrategyHorizon.INTRADAY

    # Extract timings
    entry_time = raw_schedule.get("entryFrom") or raw_schedule.get("entryTime") or "09:20"
    entry_to = raw_schedule.get("entryTo")
    forced_exit_time = raw_schedule.get("forcedExitTime") or raw_schedule.get("exitTime") or "15:15"

    # Extract & normalize days
    raw_entry_days = raw_schedule.get("entryDays") or raw_schedule.get("applicableDays") or []
    if not raw_entry_days and raw_schedule.get("entryDay"):
        raw_entry_days = [raw_schedule["entryDay"]]
    
    if not raw_entry_days:
        if horizon == StrategyHorizon.INTRADAY:
            # Default trading days for Intraday
            entry_days = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
        else:
            entry_days = []
    else:
        entry_days = [normalize_day(d) for d in raw_entry_days]

    raw_exit_days = raw_schedule.get("exitDays") or []
    if not raw_exit_days and raw_schedule.get("exitDay"):
        raw_exit_days = [raw_schedule["exitDay"]]
    exit_days = [normalize_day(d) for d in raw_exit_days]

    weekly_cycle_scope = raw_schedule.get("weeklyCycleScope")
    if weekly_cycle_scope:
        weekly_cycle_scope = str(weekly_cycle_scope).strip().upper()

    # Extract & normalize monthly fields
    applicable_months = raw_schedule.get("applicableMonths") or []
    selected_monthly_date = raw_schedule.get("selectedMonthlyDate")

    schedule = NormalizedSchedule(
        horizon=horizon,
        entry_time=str(entry_time).strip(),
        entry_to=str(entry_to).strip() if entry_to else None,
        forced_exit_time=str(forced_exit_time).strip(),
        entry_days=entry_days,
        exit_days=exit_days,
        weekly_cycle_scope=weekly_cycle_scope,
        applicable_months=[str(m).strip() for m in applicable_months],
        selected_monthly_date=str(selected_monthly_date).strip() if selected_monthly_date else None,
        timezone="Asia/Kolkata"
    )

    # Validate the normalized schedule
    validate_normalized_schedule(schedule)

    logger.debug(
        f"Strategy schedule normalized: horizon={schedule.horizon}, entry={schedule.entry_time}, exit={schedule.forced_exit_time}",
        extra={
            "event": "strategy_schedule_normalized",
            "strategy_id": strategy_id,
            "strategy_version_id": strategy_version_id,
            "horizon": schedule.horizon.value if hasattr(schedule.horizon, "value") else str(schedule.horizon),
            "entry_time": schedule.entry_time,
            "forced_exit_time": schedule.forced_exit_time,
            "timezone": schedule.timezone
        }
    )
    return schedule
