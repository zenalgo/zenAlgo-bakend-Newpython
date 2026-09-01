import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.strategies.risk.enums import (
    RiskCheckType,
    RiskFailureCode
)
from app.strategies.risk.schemas import RiskCheckResult

logger = logging.getLogger(__name__)

def _log_check_result(
    result: RiskCheckResult,
    strategy_id: Optional[int] = None,
    strategy_version_id: Optional[int] = None,
    signal_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> None:
    """Emits structured observability log for individual risk check."""
    event_name = "risk_check_passed" if result.passed else "risk_check_failed"
    log_data = {
        "event": event_name,
        "check_type": result.check_type.value,
        "passed": result.passed,
        "failure_code": result.failure_code.value if result.failure_code else None,
        "actual_value": result.actual_value,
        "configured_limit": result.configured_limit,
        "strategy_id": strategy_id,
        "strategy_version_id": strategy_version_id,
        "signal_id": signal_id,
        "user_id": user_id,
        "reason": result.reason
    }

    if result.passed:
        logger.info(
            "%s: check=%s user_id=%s reason=%s",
            event_name, result.check_type.value, user_id, result.reason,
            extra=log_data
        )
    else:
        logger.warning(
            "%s: check=%s user_id=%s code=%s reason=%s",
            event_name, result.check_type.value, user_id,
            result.failure_code.value if result.failure_code else "UNKNOWN",
            result.reason,
            extra=log_data
        )


def evaluate_max_open_positions(
    open_positions_count: Optional[int],
    max_open_positions: int = 1,
    strategy_id: Optional[int] = None,
    strategy_version_id: Optional[int] = None,
    signal_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> RiskCheckResult:
    """
    Evaluates whether opening a new position package exceeds the user's max concurrent positions.
    Fail-closed: if open_positions_count is None -> REJECT (POSITION_STATE_UNAVAILABLE).
    """
    if open_positions_count is None:
        res = RiskCheckResult(
            check_type=RiskCheckType.MAX_OPEN_POSITIONS,
            passed=False,
            failure_code=RiskFailureCode.POSITION_STATE_UNAVAILABLE,
            actual_value="UNKNOWN",
            configured_limit=str(max_open_positions),
            reason="Open positions count could not be retrieved from execution state."
        )
        _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
        return res

    if open_positions_count >= max_open_positions:
        res = RiskCheckResult(
            check_type=RiskCheckType.MAX_OPEN_POSITIONS,
            passed=False,
            failure_code=RiskFailureCode.MAX_POSITIONS_REACHED,
            actual_value=str(open_positions_count),
            configured_limit=str(max_open_positions),
            reason=f"Open positions count ({open_positions_count}) has reached maximum limit ({max_open_positions})."
        )
    else:
        res = RiskCheckResult(
            check_type=RiskCheckType.MAX_OPEN_POSITIONS,
            passed=True,
            actual_value=str(open_positions_count),
            configured_limit=str(max_open_positions),
            reason=f"Open positions count ({open_positions_count}) is below maximum limit ({max_open_positions})."
        )

    _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
    return res


def evaluate_daily_trade_limit(
    used_executions_today: Optional[int],
    max_trades_per_day: int = 10,
    strategy_id: Optional[int] = None,
    strategy_version_id: Optional[int] = None,
    signal_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> RiskCheckResult:
    """
    Evaluates whether the user's daily strategy execution count is within limit.
    Fail-closed: if used_executions_today is None -> REJECT (POSITION_STATE_UNAVAILABLE).
    """
    if used_executions_today is None:
        res = RiskCheckResult(
            check_type=RiskCheckType.DAILY_TRADE_LIMIT,
            passed=False,
            failure_code=RiskFailureCode.POSITION_STATE_UNAVAILABLE,
            actual_value="UNKNOWN",
            configured_limit=str(max_trades_per_day),
            reason="Daily usage count could not be retrieved."
        )
        _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
        return res

    if used_executions_today >= max_trades_per_day:
        res = RiskCheckResult(
            check_type=RiskCheckType.DAILY_TRADE_LIMIT,
            passed=False,
            failure_code=RiskFailureCode.DAILY_LIMIT_REACHED,
            actual_value=str(used_executions_today),
            configured_limit=str(max_trades_per_day),
            reason=f"Daily trade limit reached: {used_executions_today}/{max_trades_per_day} executions used."
        )
    else:
        res = RiskCheckResult(
            check_type=RiskCheckType.DAILY_TRADE_LIMIT,
            passed=True,
            actual_value=str(used_executions_today),
            configured_limit=str(max_trades_per_day),
            reason=f"Daily trade limit valid: {used_executions_today}/{max_trades_per_day} executions used."
        )

    _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
    return res


def evaluate_cooldown(
    last_exit_time: Optional[datetime],
    current_time: Optional[datetime] = None,
    cooldown_minutes: int = 0,
    strategy_id: Optional[int] = None,
    strategy_version_id: Optional[int] = None,
    signal_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> RiskCheckResult:
    """
    Evaluates whether mandatory quiet time (in minutes) has elapsed since last trade exit.
    If no previous exit exists or cooldown_minutes <= 0 -> PASS.
    """
    if cooldown_minutes <= 0 or last_exit_time is None:
        res = RiskCheckResult(
            check_type=RiskCheckType.COOLDOWN_PERIOD,
            passed=True,
            actual_value="0m elapsed" if last_exit_time else "NO_PREVIOUS_TRADE",
            configured_limit=f"{cooldown_minutes}m",
            reason="Cooldown satisfied (no previous trade or zero cooldown configured)."
        )
        _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
        return res

    now = current_time or datetime.now(timezone.utc)
    # Ensure UTC timezone awareness
    if last_exit_time.tzinfo is None:
        last_exit_time = last_exit_time.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    elapsed_seconds = (now - last_exit_time).total_seconds()
    required_seconds = cooldown_minutes * 60

    if elapsed_seconds < required_seconds:
        remaining_minutes = round((required_seconds - elapsed_seconds) / 60, 1)
        res = RiskCheckResult(
            check_type=RiskCheckType.COOLDOWN_PERIOD,
            passed=False,
            failure_code=RiskFailureCode.COOLDOWN_ACTIVE,
            actual_value=f"{round(elapsed_seconds / 60, 1)}m elapsed",
            configured_limit=f"{cooldown_minutes}m",
            reason=f"Cooldown active: {remaining_minutes}m remaining before re-entry allowed."
        )
    else:
        res = RiskCheckResult(
            check_type=RiskCheckType.COOLDOWN_PERIOD,
            passed=True,
            actual_value=f"{round(elapsed_seconds / 60, 1)}m elapsed",
            configured_limit=f"{cooldown_minutes}m",
            reason=f"Cooldown satisfied: {round(elapsed_seconds / 60, 1)}m elapsed since last exit."
        )

    _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
    return res


def evaluate_consecutive_losses(
    consecutive_losses: Optional[int],
    consecutive_loss_limit: int = 3,
    strategy_id: Optional[int] = None,
    strategy_version_id: Optional[int] = None,
    signal_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> RiskCheckResult:
    """
    Evaluates whether consecutive completed losses exceed the threshold.
    Fail-closed: if consecutive_losses is None -> REJECT (PNL_STATE_UNAVAILABLE).
    """
    if consecutive_losses is None:
        res = RiskCheckResult(
            check_type=RiskCheckType.CONSECUTIVE_LOSS_LIMIT,
            passed=False,
            failure_code=RiskFailureCode.PNL_STATE_UNAVAILABLE,
            actual_value="UNKNOWN",
            configured_limit=str(consecutive_loss_limit),
            reason="Consecutive loss count could not be determined."
        )
        _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
        return res

    if consecutive_losses >= consecutive_loss_limit:
        res = RiskCheckResult(
            check_type=RiskCheckType.CONSECUTIVE_LOSS_LIMIT,
            passed=False,
            failure_code=RiskFailureCode.CONSECUTIVE_LOSS_LIMIT_REACHED,
            actual_value=str(consecutive_losses),
            configured_limit=str(consecutive_loss_limit),
            reason=f"Consecutive loss limit reached ({consecutive_losses}/{consecutive_loss_limit} consecutive losses)."
        )
    else:
        res = RiskCheckResult(
            check_type=RiskCheckType.CONSECUTIVE_LOSS_LIMIT,
            passed=True,
            actual_value=str(consecutive_losses),
            configured_limit=str(consecutive_loss_limit),
            reason=f"Consecutive loss count ({consecutive_losses}/{consecutive_loss_limit}) is within threshold."
        )

    _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
    return res


def evaluate_daily_loss(
    realized_pnl: Optional[Decimal],
    unrealized_pnl: Optional[Decimal] = Decimal("0.00"),
    max_loss_per_day: Optional[Decimal] = None,
    strategy_id: Optional[int] = None,
    strategy_version_id: Optional[int] = None,
    signal_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> RiskCheckResult:
    """
    Evaluates whether the combined daily realized and unrealized loss exceeds max_loss_per_day.
    Loss is calculated as negative PnL.
    Fail-closed: if realized_pnl is None -> REJECT (PNL_STATE_UNAVAILABLE).
    """
    if max_loss_per_day is None or max_loss_per_day <= 0:
        res = RiskCheckResult(
            check_type=RiskCheckType.DAILY_LOSS_LIMIT,
            passed=True,
            actual_value="UNRESTRICTED",
            configured_limit="NONE",
            reason="Daily loss limit not configured."
        )
        _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
        return res

    if realized_pnl is None:
        res = RiskCheckResult(
            check_type=RiskCheckType.DAILY_LOSS_LIMIT,
            passed=False,
            failure_code=RiskFailureCode.PNL_STATE_UNAVAILABLE,
            actual_value="UNKNOWN",
            configured_limit=f"₹{max_loss_per_day:,.2f}",
            reason="Daily realized PnL data is unavailable."
        )
        _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
        return res

    unrealized = unrealized_pnl if unrealized_pnl is not None else Decimal("0.00")
    total_pnl = realized_pnl + unrealized
    current_loss = -total_pnl if total_pnl < Decimal("0.00") else Decimal("0.00")

    if current_loss >= max_loss_per_day:
        res = RiskCheckResult(
            check_type=RiskCheckType.DAILY_LOSS_LIMIT,
            passed=False,
            failure_code=RiskFailureCode.DAILY_LOSS_LIMIT_REACHED,
            actual_value=f"₹{current_loss:,.2f}",
            configured_limit=f"₹{max_loss_per_day:,.2f}",
            reason=f"Daily loss limit reached: current loss ₹{current_loss:,.2f} >= max ₹{max_loss_per_day:,.2f}."
        )
    else:
        res = RiskCheckResult(
            check_type=RiskCheckType.DAILY_LOSS_LIMIT,
            passed=True,
            actual_value=f"₹{current_loss:,.2f}",
            configured_limit=f"₹{max_loss_per_day:,.2f}",
            reason=f"Daily loss limit valid: current loss ₹{current_loss:,.2f} < max ₹{max_loss_per_day:,.2f}."
        )

    _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
    return res


def evaluate_weekly_loss(
    weekly_realized_pnl: Optional[Decimal],
    current_unrealized_pnl: Optional[Decimal] = Decimal("0.00"),
    max_loss_per_week: Optional[Decimal] = None,
    strategy_id: Optional[int] = None,
    strategy_version_id: Optional[int] = None,
    signal_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> RiskCheckResult:
    """
    Evaluates whether the combined weekly realized and unrealized loss exceeds max_loss_per_week.
    Fail-closed: if weekly_realized_pnl is None -> REJECT (PNL_STATE_UNAVAILABLE).
    """
    if max_loss_per_week is None or max_loss_per_week <= 0:
        res = RiskCheckResult(
            check_type=RiskCheckType.WEEKLY_LOSS_LIMIT,
            passed=True,
            actual_value="UNRESTRICTED",
            configured_limit="NONE",
            reason="Weekly loss limit not configured."
        )
        _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
        return res

    if weekly_realized_pnl is None:
        res = RiskCheckResult(
            check_type=RiskCheckType.WEEKLY_LOSS_LIMIT,
            passed=False,
            failure_code=RiskFailureCode.PNL_STATE_UNAVAILABLE,
            actual_value="UNKNOWN",
            configured_limit=f"₹{max_loss_per_week:,.2f}",
            reason="Weekly realized PnL data is unavailable."
        )
        _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
        return res

    unrealized = current_unrealized_pnl if current_unrealized_pnl is not None else Decimal("0.00")
    total_pnl = weekly_realized_pnl + unrealized
    current_loss = -total_pnl if total_pnl < Decimal("0.00") else Decimal("0.00")

    if current_loss >= max_loss_per_week:
        res = RiskCheckResult(
            check_type=RiskCheckType.WEEKLY_LOSS_LIMIT,
            passed=False,
            failure_code=RiskFailureCode.WEEKLY_LOSS_LIMIT_REACHED,
            actual_value=f"₹{current_loss:,.2f}",
            configured_limit=f"₹{max_loss_per_week:,.2f}",
            reason=f"Weekly loss limit reached: current loss ₹{current_loss:,.2f} >= max ₹{max_loss_per_week:,.2f}."
        )
    else:
        res = RiskCheckResult(
            check_type=RiskCheckType.WEEKLY_LOSS_LIMIT,
            passed=True,
            actual_value=f"₹{current_loss:,.2f}",
            configured_limit=f"₹{max_loss_per_week:,.2f}",
            reason=f"Weekly loss limit valid: current loss ₹{current_loss:,.2f} < max ₹{max_loss_per_week:,.2f}."
        )

    _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
    return res


def evaluate_capital_and_margin(
    available_capital: Optional[Decimal],
    required_capital: Optional[Decimal],
    snapshot_time: Optional[datetime] = None,
    current_time: Optional[datetime] = None,
    max_snapshot_age_seconds: int = 86400,
    strategy_id: Optional[int] = None,
    strategy_version_id: Optional[int] = None,
    signal_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> RiskCheckResult:
    """
    Evaluates whether the user's available broker/wallet capital meets or exceeds the required capital.
    Fail-closed:
    - If available_capital is None -> REJECT (FUNDS_DATA_UNAVAILABLE)
    - If required_capital is None -> REJECT (FUNDS_DATA_UNAVAILABLE)
    - If snapshot_time is older than max_snapshot_age_seconds -> REJECT (FUNDS_DATA_UNAVAILABLE)
    """
    if available_capital is None or required_capital is None:
        res = RiskCheckResult(
            check_type=RiskCheckType.CAPITAL_AND_MARGIN,
            passed=False,
            failure_code=RiskFailureCode.FUNDS_DATA_UNAVAILABLE,
            actual_value=f"₹{available_capital:,.2f}" if available_capital is not None else "UNKNOWN",
            configured_limit=f"₹{required_capital:,.2f}" if required_capital is not None else "UNKNOWN",
            reason="Capital or margin requirement data is unavailable."
        )
        _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
        return res

    # Check snapshot freshness if provided
    if snapshot_time is not None:
        now = current_time or datetime.now(timezone.utc)
        if snapshot_time.tzinfo is None:
            snapshot_time = snapshot_time.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        age_seconds = (now - snapshot_time).total_seconds()
        if age_seconds > max_snapshot_age_seconds:
            res = RiskCheckResult(
                check_type=RiskCheckType.CAPITAL_AND_MARGIN,
                passed=False,
                failure_code=RiskFailureCode.FUNDS_DATA_UNAVAILABLE,
                actual_value=f"Snapshot age: {round(age_seconds / 3600, 1)}h",
                configured_limit=f"Max age: {round(max_snapshot_age_seconds / 3600, 1)}h",
                reason=f"Broker fund snapshot is stale ({round(age_seconds / 3600, 1)}h old)."
            )
            _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
            return res

    if available_capital < required_capital:
        res = RiskCheckResult(
            check_type=RiskCheckType.CAPITAL_AND_MARGIN,
            passed=False,
            failure_code=RiskFailureCode.INSUFFICIENT_FUNDS,
            actual_value=f"₹{available_capital:,.2f}",
            configured_limit=f"₹{required_capital:,.2f}",
            reason=f"Insufficient capital: available ₹{available_capital:,.2f} < required ₹{required_capital:,.2f}."
        )
    else:
        res = RiskCheckResult(
            check_type=RiskCheckType.CAPITAL_AND_MARGIN,
            passed=True,
            actual_value=f"₹{available_capital:,.2f}",
            configured_limit=f"₹{required_capital:,.2f}",
            reason=f"Capital validated: available ₹{available_capital:,.2f} >= required ₹{required_capital:,.2f}."
        )

    _log_check_result(res, strategy_id, strategy_version_id, signal_id, user_id)
    return res
