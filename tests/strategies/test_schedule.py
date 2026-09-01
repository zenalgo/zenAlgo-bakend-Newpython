import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.strategies.enums import StrategyHorizon, ScheduleEvaluationReason
from app.strategies.schedule.schemas import NormalizedSchedule
from app.strategies.schedule.validator import validate_normalized_schedule
from app.strategies.schedule.normalizer import normalize_schedule, normalize_horizon
from app.strategies.schedule.evaluator import evaluate_schedule
from app.core.exceptions import ValidationError

# --- Test 3-01 & 3-02: Schedule Validation ---

def test_intraday_valid_configuration():
    """Test 3-01: Valid intraday schedule passes validation."""
    sched = NormalizedSchedule(
        horizon=StrategyHorizon.INTRADAY,
        entry_time="09:20",
        forced_exit_time="15:15",
        entry_days=["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
        timezone="Asia/Kolkata"
    )
    validate_normalized_schedule(sched)
    assert sched.horizon == StrategyHorizon.INTRADAY
    assert sched.entry_time == "09:20"
    assert sched.forced_exit_time == "15:15"

def test_intraday_invalid_time_order():
    """Test 3-02: entry_time >= forced_exit_time raises ValidationError."""
    with pytest.raises(ValidationError, match="entry_time .* must be before forced_exit_time"):
        NormalizedSchedule(
            horizon=StrategyHorizon.INTRADAY,
            entry_time="15:15",
            forced_exit_time="09:20",
            timezone="Asia/Kolkata"
        )

def test_invalid_time_formats():
    """Validates that malformed time strings raise ValidationError."""
    with pytest.raises(ValidationError, match="invalid"):
        NormalizedSchedule(
            horizon=StrategyHorizon.INTRADAY,
            entry_time="25:00",
            forced_exit_time="15:15",
            timezone="Asia/Kolkata"
        )

# --- Test 3-03, 3-04 & 3-05: Intraday Evaluation & Boundaries ---

def test_before_intraday_entry_time():
    """Test 3-03: 09:10 IST is before entry window start (09:20 IST)."""
    sched = NormalizedSchedule(
        horizon=StrategyHorizon.INTRADAY,
        entry_time="09:20",
        forced_exit_time="15:15",
        entry_days=["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
        timezone="Asia/Kolkata"
    )
    # Monday 09:10 IST
    eval_dt = datetime(2026, 8, 31, 9, 10, tzinfo=ZoneInfo("Asia/Kolkata"))
    result = evaluate_schedule(sched, eval_dt)
    
    assert result.eligible is False
    assert result.reason == ScheduleEvaluationReason.BEFORE_ENTRY_TIME
    assert result.current_time == "09:10"

def test_intraday_active_window():
    """Test 3-04: 10:30 IST is within entry window (09:20 - 15:15 IST)."""
    sched = NormalizedSchedule(
        horizon=StrategyHorizon.INTRADAY,
        entry_time="09:20",
        forced_exit_time="15:15",
        entry_days=["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
        timezone="Asia/Kolkata"
    )
    # Monday 10:30 IST
    eval_dt = datetime(2026, 8, 31, 10, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    result = evaluate_schedule(sched, eval_dt)
    
    assert result.eligible is True
    assert result.reason == ScheduleEvaluationReason.WITHIN_ENTRY_WINDOW

def test_intraday_forced_exit_boundary():
    """Test 3-05: Exact boundary checks for 15:14, 15:15, and 15:20 IST."""
    sched = NormalizedSchedule(
        horizon=StrategyHorizon.INTRADAY,
        entry_time="09:20",
        forced_exit_time="15:15",
        entry_days=["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
        timezone="Asia/Kolkata"
    )
    # 15:14 IST -> Still within active window
    dt_1514 = datetime(2026, 8, 31, 15, 14, tzinfo=ZoneInfo("Asia/Kolkata"))
    res_1514 = evaluate_schedule(sched, dt_1514)
    assert res_1514.eligible is True
    assert res_1514.reason == ScheduleEvaluationReason.WITHIN_ENTRY_WINDOW

    # 15:15 IST -> Forced exit boundary reached
    dt_1515 = datetime(2026, 8, 31, 15, 15, tzinfo=ZoneInfo("Asia/Kolkata"))
    res_1515 = evaluate_schedule(sched, dt_1515)
    assert res_1515.eligible is False
    assert res_1515.reason == ScheduleEvaluationReason.AFTER_FORCED_EXIT_TIME

    # 15:20 IST -> Past forced exit window
    dt_1520 = datetime(2026, 8, 31, 15, 20, tzinfo=ZoneInfo("Asia/Kolkata"))
    res_1520 = evaluate_schedule(sched, dt_1520)
    assert res_1520.eligible is False
    assert res_1520.reason == ScheduleEvaluationReason.AFTER_FORCED_EXIT_TIME

# --- Weekly Horizon Tests ---

def test_weekly_horizon_evaluation():
    """Verifies weekly horizon checks for entryDays."""
    sched = NormalizedSchedule(
        horizon=StrategyHorizon.WEEKLY,
        entry_time="09:20",
        forced_exit_time="15:15",
        entry_days=["THURSDAY"],
        exit_days=["MONDAY"],
        weekly_cycle_scope="SAME_WEEK",
        timezone="Asia/Kolkata"
    )
    # Thursday 10:00 IST (2026-09-03 is Thursday)
    dt_thu = datetime(2026, 9, 3, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    res_thu = evaluate_schedule(sched, dt_thu)
    assert res_thu.eligible is True
    assert res_thu.reason == ScheduleEvaluationReason.WITHIN_ENTRY_WINDOW

    # Wednesday 10:00 IST (2026-09-02 is Wednesday)
    dt_wed = datetime(2026, 9, 2, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    res_wed = evaluate_schedule(sched, dt_wed)
    assert res_wed.eligible is False
    assert res_wed.reason == ScheduleEvaluationReason.DAY_NOT_APPLICABLE

# --- Monthly Horizon Tests ---

def test_monthly_horizon_evaluation():
    """Verifies monthly horizon evaluation against date and applicable months."""
    sched = NormalizedSchedule(
        horizon=StrategyHorizon.MONTHLY,
        entry_time="09:20",
        forced_exit_time="15:15",
        applicable_months=["Aug-2026", "2026-08"],
        selected_monthly_date="2026-08-05",
        timezone="Asia/Kolkata"
    )
    # 2026-08-05 10:00 IST (Matches exact date and month)
    dt_match = datetime(2026, 8, 5, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    res_match = evaluate_schedule(sched, dt_match)
    assert res_match.eligible is True
    assert res_match.reason == ScheduleEvaluationReason.WITHIN_ENTRY_WINDOW

    # 2026-08-06 10:00 IST (Month matches, date does not)
    dt_wrong_date = datetime(2026, 8, 6, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    res_wrong_date = evaluate_schedule(sched, dt_wrong_date)
    assert res_wrong_date.eligible is False
    assert res_wrong_date.reason == ScheduleEvaluationReason.DATE_NOT_APPLICABLE

    # 2026-09-05 10:00 IST (Date 5 matches, but month Sep-2026 does not)
    dt_wrong_month = datetime(2026, 9, 5, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    res_wrong_month = evaluate_schedule(sched, dt_wrong_month)
    assert res_wrong_month.eligible is False
    assert res_wrong_month.reason == ScheduleEvaluationReason.MONTH_NOT_APPLICABLE

def test_monthly_invalid_calendar_date():
    """Rejects impossible calendar dates such as Feb 31."""
    sched = NormalizedSchedule(
        horizon=StrategyHorizon.MONTHLY,
        entry_time="09:20",
        forced_exit_time="15:15",
        selected_monthly_date="2026-02-31",
        timezone="Asia/Kolkata"
    )
    with pytest.raises(ValidationError, match="Invalid monthly date"):
        validate_normalized_schedule(sched)

# --- Timezone & Date Boundary Tests ---

def test_timezone_conversion_from_utc():
    """Verifies that UTC inputs are accurately converted to IST for evaluation."""
    sched = NormalizedSchedule(
        horizon=StrategyHorizon.INTRADAY,
        entry_time="09:20",
        forced_exit_time="15:15",
        entry_days=["MONDAY"],
        timezone="Asia/Kolkata"
    )
    # 03:50 UTC on Monday corresponds to 09:20 IST (entry start)
    dt_utc_0920 = datetime(2026, 8, 31, 3, 50, tzinfo=timezone.utc)
    res_0920 = evaluate_schedule(sched, dt_utc_0920)
    assert res_0920.eligible is True
    assert res_0920.current_time == "09:20"

    # 03:40 UTC on Monday corresponds to 09:10 IST (before entry)
    dt_utc_0910 = datetime(2026, 8, 31, 3, 40, tzinfo=timezone.utc)
    res_0910 = evaluate_schedule(sched, dt_utc_0910)
    assert res_0910.eligible is False
    assert res_0910.reason == ScheduleEvaluationReason.BEFORE_ENTRY_TIME

def test_date_boundary_crossing_utc_to_ist():
    """Verifies that Sunday night UTC (e.g. 23:55 UTC) is evaluated as Monday in IST."""
    sched = NormalizedSchedule(
        horizon=StrategyHorizon.INTRADAY,
        entry_time="09:20",
        forced_exit_time="15:15",
        entry_days=["MONDAY"],
        timezone="Asia/Kolkata"
    )
    # 2026-08-30 23:55 UTC (Sunday) is 2026-08-31 05:25 IST (Monday early morning)
    dt_sunday_night_utc = datetime(2026, 8, 30, 23, 55, tzinfo=timezone.utc)
    res = evaluate_schedule(sched, dt_sunday_night_utc)
    # In IST, it is Monday 05:25, which is BEFORE_ENTRY_TIME on a valid Monday!
    assert res.details["weekday"] == "MONDAY"
    assert res.eligible is False
    assert res.reason == ScheduleEvaluationReason.BEFORE_ENTRY_TIME

# --- Normalization Tests ---

def test_schedule_normalization_variations():
    """Verifies casing and dictionary structures normalize to NormalizedSchedule."""
    # Test Intraday variations
    assert normalize_horizon("Intraday") == StrategyHorizon.INTRADAY
    assert normalize_horizon("intraday") == StrategyHorizon.INTRADAY
    assert normalize_horizon("INTRADAY") == StrategyHorizon.INTRADAY

    # Test Weekly variations
    assert normalize_horizon("Weekly") == StrategyHorizon.WEEKLY
    assert normalize_horizon("weekly") == StrategyHorizon.WEEKLY

    # Test Monthly variations
    assert normalize_horizon("Monthly") == StrategyHorizon.MONTHLY
    assert normalize_horizon("monthly") == StrategyHorizon.MONTHLY

    # Invalid horizon
    with pytest.raises(ValidationError, match="Invalid strategy horizon"):
        normalize_horizon("RandomHorizon")

def test_normalize_schedule_from_dict():
    """Normalizes raw dictionary payload from frontend builder."""
    payload = {
        "expiryType": "Weekly",
        "schedule": {
            "entryFrom": "09:25",
            "forcedExitTime": "15:10",
            "entryDays": ["Thu", "Fri"],
            "exitDays": ["Mon"],
            "weeklyCycleScope": "NEXT_WEEK"
        }
    }
    sched = normalize_schedule(payload)
    assert sched.horizon == StrategyHorizon.WEEKLY
    assert sched.entry_time == "09:25"
    assert sched.forced_exit_time == "15:10"
    assert sched.entry_days == ["THURSDAY", "FRIDAY"]
    assert sched.exit_days == ["MONDAY"]
    assert sched.weekly_cycle_scope == "NEXT_WEEK"
