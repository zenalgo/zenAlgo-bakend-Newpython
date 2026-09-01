from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import logging
from typing import Optional, Dict, Any
from app.strategies.enums import StrategyHorizon, ScheduleEvaluationReason
from app.strategies.schedule.schemas import NormalizedSchedule, ScheduleEvaluationResult

logger = logging.getLogger(__name__)

def is_month_applicable(applicable_months: list, local_dt: datetime) -> bool:
    """Checks if the local date's month matches any of the configured applicable months."""
    if not applicable_months:
        return True
    
    month_formats = {
        local_dt.strftime("%b-%Y").upper(),     # AUG-2026
        local_dt.strftime("%Y-%m").upper(),     # 2026-08
        local_dt.strftime("%B-%Y").upper(),     # AUGUST-2026
        local_dt.strftime("%b").upper(),        # AUG
        local_dt.strftime("%B").upper()         # AUGUST
    }

    for m in applicable_months:
        if str(m).strip().upper() in month_formats:
            return True
    return False

def is_monthly_date_applicable(selected_date: str, local_dt: datetime) -> bool:
    """Checks if today matches the configured monthly date (specific date or day of month)."""
    if not selected_date:
        return True
    
    cleaned = str(selected_date).strip()
    
    # 1. Day of month integer (e.g. "5" or "15")
    if cleaned.isdigit():
        return local_dt.day == int(cleaned)
    
    # 2. ISO Date (YYYY-MM-DD)
    if cleaned == local_dt.strftime("%Y-%m-%d"):
        return True
        
    # 3. Formatted Date (e.g. 2026-Aug-5 or 2026-Aug-05)
    try:
        parsed_dt = datetime.strptime(cleaned, "%Y-%b-%d")
        return (parsed_dt.year == local_dt.year and 
                parsed_dt.month == local_dt.month and 
                parsed_dt.day == local_dt.day)
    except Exception:
        pass

    return False

def evaluate_schedule(
    schedule: NormalizedSchedule,
    evaluation_dt: Optional[datetime] = None,
    context: Optional[Dict[str, Any]] = None
) -> ScheduleEvaluationResult:
    """
    Pure, deterministic evaluation function that determines if a strategy is eligible 
    to trade at the specified evaluation datetime.
    """
    if evaluation_dt is None:
        evaluation_dt = datetime.now(timezone.utc)
    elif evaluation_dt.tzinfo is None:
        evaluation_dt = evaluation_dt.replace(tzinfo=timezone.utc)

    # 1. Timezone conversion to strategy's market timezone (Asia/Kolkata)
    tz = ZoneInfo(schedule.timezone)
    local_dt = evaluation_dt.astimezone(tz)

    current_weekday = local_dt.strftime("%A").upper()
    current_time = local_dt.strftime("%H:%M")
    eval_time_iso = local_dt.isoformat()

    eligible = False
    reason = ScheduleEvaluationReason.BEFORE_ENTRY_TIME
    details = {
        "local_datetime": eval_time_iso,
        "weekday": current_weekday,
        "current_time": current_time
    }

    # 2. Horizon-Specific Calendar/Day Evaluation
    if schedule.horizon == StrategyHorizon.INTRADAY:
        if schedule.entry_days and current_weekday not in schedule.entry_days:
            eligible = False
            reason = ScheduleEvaluationReason.DAY_NOT_APPLICABLE
        elif current_time < schedule.entry_time:
            eligible = False
            reason = ScheduleEvaluationReason.BEFORE_ENTRY_TIME
        elif current_time >= schedule.forced_exit_time:
            eligible = False
            reason = ScheduleEvaluationReason.AFTER_FORCED_EXIT_TIME
        elif schedule.entry_to and current_time > schedule.entry_to:
            eligible = False
            reason = ScheduleEvaluationReason.AFTER_ENTRY_TO_TIME
        else:
            eligible = True
            reason = ScheduleEvaluationReason.WITHIN_ENTRY_WINDOW

    elif schedule.horizon == StrategyHorizon.WEEKLY:
        if schedule.entry_days and current_weekday not in schedule.entry_days:
            eligible = False
            reason = ScheduleEvaluationReason.DAY_NOT_APPLICABLE
        elif current_time < schedule.entry_time:
            eligible = False
            reason = ScheduleEvaluationReason.BEFORE_ENTRY_TIME
        elif current_time >= schedule.forced_exit_time:
            eligible = False
            reason = ScheduleEvaluationReason.AFTER_FORCED_EXIT_TIME
        elif schedule.entry_to and current_time > schedule.entry_to:
            eligible = False
            reason = ScheduleEvaluationReason.AFTER_ENTRY_TO_TIME
        else:
            eligible = True
            reason = ScheduleEvaluationReason.WITHIN_ENTRY_WINDOW

    elif schedule.horizon == StrategyHorizon.MONTHLY:
        if schedule.applicable_months and not is_month_applicable(schedule.applicable_months, local_dt):
            eligible = False
            reason = ScheduleEvaluationReason.MONTH_NOT_APPLICABLE
        elif schedule.selected_monthly_date and not is_monthly_date_applicable(schedule.selected_monthly_date, local_dt):
            eligible = False
            reason = ScheduleEvaluationReason.DATE_NOT_APPLICABLE
        elif schedule.entry_days and current_weekday not in schedule.entry_days:
            eligible = False
            reason = ScheduleEvaluationReason.DAY_NOT_APPLICABLE
        elif current_time < schedule.entry_time:
            eligible = False
            reason = ScheduleEvaluationReason.BEFORE_ENTRY_TIME
        elif current_time >= schedule.forced_exit_time:
            eligible = False
            reason = ScheduleEvaluationReason.AFTER_FORCED_EXIT_TIME
        elif schedule.entry_to and current_time > schedule.entry_to:
            eligible = False
            reason = ScheduleEvaluationReason.AFTER_ENTRY_TO_TIME
        else:
            eligible = True
            reason = ScheduleEvaluationReason.WITHIN_ENTRY_WINDOW

    result = ScheduleEvaluationResult(
        eligible=eligible,
        reason=reason,
        horizon=schedule.horizon,
        evaluation_time=eval_time_iso,
        current_time=current_time,
        entry_time=schedule.entry_time,
        forced_exit_time=schedule.forced_exit_time,
        timezone=schedule.timezone,
        details=details
    )

    horizon_str = schedule.horizon.value if hasattr(schedule.horizon, "value") else str(schedule.horizon)
    reason_str = reason.value if hasattr(reason, "value") else str(reason)

    # 3. Structured Logging
    log_extra = {
        "event": "strategy_schedule_evaluated",
        "horizon": horizon_str,
        "evaluation_time": eval_time_iso,
        "timezone": schedule.timezone,
        "current_time": current_time,
        "entry_time": schedule.entry_time,
        "forced_exit_time": schedule.forced_exit_time,
        "eligible": eligible,
        "reason": reason_str
    }
    if context:
        log_extra.update(context)

    logger.debug(
        f"Strategy schedule evaluated: horizon={horizon_str}, eligible={eligible}, reason={reason_str}",
        extra=log_extra
    )
    return result
