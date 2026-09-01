import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.strategies.risk.enums import (
    RiskCheckType,
    RiskFailureCode
)
from app.strategies.risk.evaluators import (
    evaluate_max_open_positions,
    evaluate_daily_trade_limit,
    evaluate_cooldown,
    evaluate_consecutive_losses,
    evaluate_daily_loss,
    evaluate_weekly_loss,
    evaluate_capital_and_margin
)

# --- 1. Max Open Positions Tests ---

def test_evaluate_max_open_positions_pass():
    res = evaluate_max_open_positions(open_positions_count=0, max_open_positions=1)
    assert res.passed is True
    assert res.check_type == RiskCheckType.MAX_OPEN_POSITIONS
    assert res.failure_code is None
    assert res.actual_value == "0"

def test_evaluate_max_open_positions_boundary_fail():
    res = evaluate_max_open_positions(open_positions_count=1, max_open_positions=1)
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.MAX_POSITIONS_REACHED
    assert res.actual_value == "1"

def test_evaluate_max_open_positions_exceeded_fail():
    res = evaluate_max_open_positions(open_positions_count=2, max_open_positions=1)
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.MAX_POSITIONS_REACHED

def test_evaluate_max_open_positions_fail_closed_none():
    res = evaluate_max_open_positions(open_positions_count=None, max_open_positions=1)
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.POSITION_STATE_UNAVAILABLE

# --- 2. Daily Trade Limit Tests ---

def test_evaluate_daily_trade_limit_pass():
    res = evaluate_daily_trade_limit(used_executions_today=2, max_trades_per_day=3)
    assert res.passed is True
    assert res.actual_value == "2"
    assert res.configured_limit == "3"

def test_evaluate_daily_trade_limit_reached_fail():
    res = evaluate_daily_trade_limit(used_executions_today=3, max_trades_per_day=3)
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.DAILY_LIMIT_REACHED

def test_evaluate_daily_trade_limit_fail_closed_none():
    res = evaluate_daily_trade_limit(used_executions_today=None, max_trades_per_day=3)
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.POSITION_STATE_UNAVAILABLE

# --- 3. Cooldown Period Tests ---

def test_evaluate_cooldown_no_previous_trade_pass():
    res = evaluate_cooldown(last_exit_time=None, cooldown_minutes=15)
    assert res.passed is True
    assert res.failure_code is None

def test_evaluate_cooldown_zero_cooldown_pass():
    t = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    res = evaluate_cooldown(last_exit_time=t, current_time=t, cooldown_minutes=0)
    assert res.passed is True

def test_evaluate_cooldown_active_fail():
    exit_time = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    curr_time = datetime(2026, 9, 1, 10, 10, 0, tzinfo=timezone.utc) # 10m elapsed
    res = evaluate_cooldown(last_exit_time=exit_time, current_time=curr_time, cooldown_minutes=15)
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.COOLDOWN_ACTIVE
    assert "5.0m remaining" in res.reason

def test_evaluate_cooldown_exact_boundary_pass():
    exit_time = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    curr_time = datetime(2026, 9, 1, 10, 15, 0, tzinfo=timezone.utc) # Exactly 15m elapsed
    res = evaluate_cooldown(last_exit_time=exit_time, current_time=curr_time, cooldown_minutes=15)
    assert res.passed is True

def test_evaluate_cooldown_after_cooldown_pass():
    exit_time = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    curr_time = datetime(2026, 9, 1, 10, 20, 0, tzinfo=timezone.utc) # 20m elapsed
    res = evaluate_cooldown(last_exit_time=exit_time, current_time=curr_time, cooldown_minutes=15)
    assert res.passed is True

# --- 4. Consecutive Losses Tests ---

def test_evaluate_consecutive_losses_zero_pass():
    res = evaluate_consecutive_losses(consecutive_losses=0, consecutive_loss_limit=2)
    assert res.passed is True
    assert res.actual_value == "0"

def test_evaluate_consecutive_losses_below_limit_pass():
    res = evaluate_consecutive_losses(consecutive_losses=1, consecutive_loss_limit=2)
    assert res.passed is True
    assert res.actual_value == "1"

def test_evaluate_consecutive_losses_limit_reached_fail():
    res = evaluate_consecutive_losses(consecutive_losses=2, consecutive_loss_limit=2)
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.CONSECUTIVE_LOSS_LIMIT_REACHED

def test_evaluate_consecutive_losses_fail_closed_none():
    res = evaluate_consecutive_losses(consecutive_losses=None, consecutive_loss_limit=2)
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.PNL_STATE_UNAVAILABLE

# --- 5. Daily Loss Tests ---

def test_evaluate_daily_loss_profit_pass():
    res = evaluate_daily_loss(realized_pnl=Decimal("1500.00"), unrealized_pnl=Decimal("500.00"), max_loss_per_day=Decimal("5000.00"))
    assert res.passed is True
    assert res.actual_value == "₹0.00"

def test_evaluate_daily_loss_below_limit_pass():
    res = evaluate_daily_loss(realized_pnl=Decimal("-3000.00"), unrealized_pnl=Decimal("-1500.00"), max_loss_per_day=Decimal("5000.00"))
    assert res.passed is True
    assert res.actual_value == "₹4,500.00"

def test_evaluate_daily_loss_exact_boundary_fail():
    res = evaluate_daily_loss(realized_pnl=Decimal("-5000.00"), unrealized_pnl=Decimal("0.00"), max_loss_per_day=Decimal("5000.00"))
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.DAILY_LOSS_LIMIT_REACHED
    assert res.actual_value == "₹5,000.00"

def test_evaluate_daily_loss_above_limit_fail():
    res = evaluate_daily_loss(realized_pnl=Decimal("-4000.00"), unrealized_pnl=Decimal("-1000.01"), max_loss_per_day=Decimal("5000.00"))
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.DAILY_LOSS_LIMIT_REACHED
    assert res.actual_value == "₹5,000.01"

def test_evaluate_daily_loss_fail_closed_none():
    res = evaluate_daily_loss(realized_pnl=None, max_loss_per_day=Decimal("5000.00"))
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.PNL_STATE_UNAVAILABLE

# --- 6. Weekly Loss Tests ---

def test_evaluate_weekly_loss_below_limit_pass():
    res = evaluate_weekly_loss(weekly_realized_pnl=Decimal("-10000.00"), current_unrealized_pnl=Decimal("-2000.00"), max_loss_per_week=Decimal("15000.00"))
    assert res.passed is True
    assert res.actual_value == "₹12,000.00"

def test_evaluate_weekly_loss_exact_limit_fail():
    res = evaluate_weekly_loss(weekly_realized_pnl=Decimal("-15000.00"), current_unrealized_pnl=Decimal("0.00"), max_loss_per_week=Decimal("15000.00"))
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.WEEKLY_LOSS_LIMIT_REACHED

def test_evaluate_weekly_loss_fail_closed_none():
    res = evaluate_weekly_loss(weekly_realized_pnl=None, max_loss_per_week=Decimal("15000.00"))
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.PNL_STATE_UNAVAILABLE

# --- 7. Capital & Margin Tests ---

def test_evaluate_capital_and_margin_pass():
    res = evaluate_capital_and_margin(available_capital=Decimal("50000.00"), required_capital=Decimal("30000.00"))
    assert res.passed is True
    assert res.actual_value == "₹50,000.00"
    assert res.configured_limit == "₹30,000.00"

def test_evaluate_capital_and_margin_exact_equal_pass():
    res = evaluate_capital_and_margin(available_capital=Decimal("30000.00"), required_capital=Decimal("30000.00"))
    assert res.passed is True

def test_evaluate_capital_and_margin_insufficient_fail():
    res = evaluate_capital_and_margin(available_capital=Decimal("29999.99"), required_capital=Decimal("30000.00"))
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.INSUFFICIENT_FUNDS

def test_evaluate_capital_and_margin_stale_snapshot_fail():
    snap_time = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)
    curr_time = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc) # 50h old (> 24h)
    res = evaluate_capital_and_margin(
        available_capital=Decimal("50000.00"),
        required_capital=Decimal("30000.00"),
        snapshot_time=snap_time,
        current_time=curr_time,
        max_snapshot_age_seconds=86400
    )
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.FUNDS_DATA_UNAVAILABLE
    assert "stale" in res.reason

def test_evaluate_capital_and_margin_fail_closed_none():
    res = evaluate_capital_and_margin(available_capital=None, required_capital=Decimal("30000.00"))
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.FUNDS_DATA_UNAVAILABLE

# --- 8. Multi-User Isolation Test ---

def test_multi_user_evaluator_isolation():
    # User A has 0 open positions -> PASS
    res_a = evaluate_max_open_positions(open_positions_count=0, max_open_positions=1, user_id=1)
    # User B has 1 open position -> FAIL
    res_b = evaluate_max_open_positions(open_positions_count=1, max_open_positions=1, user_id=2)

    assert res_a.passed is True
    assert res_b.passed is False
    assert res_a.actual_value != res_b.actual_value
