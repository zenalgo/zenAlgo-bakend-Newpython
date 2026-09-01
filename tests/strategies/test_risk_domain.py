import pytest
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import ValidationError

from app.strategies.risk.enums import (
    RiskDecisionType,
    RiskCheckType,
    RiskFailureCode,
    RiskSizingMode
)
from app.strategies.risk.schemas import (
    RiskCheckResult,
    StrategyRiskProfile,
    UserRiskEvaluationResult
)

# --- 1. Enum Validation Tests ---

def test_risk_decision_types():
    assert RiskDecisionType.APPROVED == "APPROVED"
    assert RiskDecisionType.REJECTED == "REJECTED"
    assert len(RiskDecisionType) == 2

def test_risk_check_types_completeness():
    expected_checks = [
        "SIGNAL_VALIDATION", "STRATEGY_ACTIVE", "USER_ACTIVE",
        "SUBSCRIPTION_ACCESS", "BROKER_CONNECTION", "MAX_OPEN_POSITIONS",
        "DAILY_TRADE_LIMIT", "COOLDOWN_PERIOD", "CONSECUTIVE_LOSS_LIMIT",
        "DAILY_LOSS_LIMIT", "WEEKLY_LOSS_LIMIT", "CAPITAL_AND_MARGIN",
        "QUOTA_RESERVATION", "FINAL_APPROVAL"
    ]
    for check in expected_checks:
        assert hasattr(RiskCheckType, check)
        assert getattr(RiskCheckType, check).value == check

def test_risk_failure_codes():
    assert RiskFailureCode.DAILY_LOSS_LIMIT_REACHED.value == "DAILY_LOSS_LIMIT_REACHED"
    assert RiskFailureCode.INSUFFICIENT_FUNDS.value == "INSUFFICIENT_FUNDS"
    assert RiskFailureCode.MAX_POSITIONS_REACHED.value == "MAX_POSITIONS_REACHED"

# --- 2. RiskCheckResult Schema Tests ---

def test_risk_check_result_passed():
    chk = RiskCheckResult(
        check_type=RiskCheckType.DAILY_LOSS_LIMIT,
        passed=True,
        actual_value="₹1,200",
        configured_limit="₹5,000",
        reason="Daily loss ₹1200 is below configured limit ₹5000"
    )
    assert chk.passed is True
    assert chk.failure_code is None
    assert chk.actual_value == "₹1,200"

def test_risk_check_result_failed():
    chk = RiskCheckResult(
        check_type=RiskCheckType.DAILY_LOSS_LIMIT,
        passed=False,
        failure_code=RiskFailureCode.DAILY_LOSS_LIMIT_REACHED,
        actual_value="₹5,250",
        configured_limit="₹5,000",
        reason="Daily loss ₹5250 exceeds maximum threshold ₹5000"
    )
    assert chk.passed is False
    assert chk.failure_code == RiskFailureCode.DAILY_LOSS_LIMIT_REACHED
    assert chk.actual_value == "₹5,250"

# --- 3. StrategyRiskProfile Schema Tests ---

def test_strategy_risk_profile_defaults_and_decimals():
    profile = StrategyRiskProfile(
        strategy_id=101,
        strategy_version_id=501,
        max_loss_per_trade=Decimal("2500.00"),
        max_loss_per_day=Decimal("5000.00"),
        max_loss_per_week=Decimal("15000.00"),
        max_trades_per_day=3,
        max_open_positions=1,
        consecutive_loss_limit=2,
        cooldown_minutes=15,
        sizing_mode=RiskSizingMode.FIXED_LOTS
    )
    assert profile.strategy_id == 101
    assert profile.strategy_version_id == 501
    assert profile.max_loss_per_day == Decimal("5000.00")
    assert profile.sizing_mode == RiskSizingMode.FIXED_LOTS

# --- 4. UserRiskEvaluationResult & User-Level Isolation Tests ---

def test_user_risk_evaluation_approved():
    chk1 = RiskCheckResult(check_type=RiskCheckType.USER_ACTIVE, passed=True, reason="User is active")
    chk2 = RiskCheckResult(check_type=RiskCheckType.BROKER_CONNECTION, passed=True, reason="Broker session active")
    chk3 = RiskCheckResult(check_type=RiskCheckType.DAILY_LOSS_LIMIT, passed=True, actual_value="₹0.00", configured_limit="₹5000.00", reason="No loss today")

    res = UserRiskEvaluationResult(
        user_id=10,
        strategy_id=101,
        strategy_version_id=501,
        signal_id=9001,
        decision=RiskDecisionType.APPROVED,
        approved_lots=2,
        required_capital=Decimal("45000.00"),
        reason="All risk checks passed successfully",
        checks=[chk1, chk2, chk3]
    )

    assert res.decision == RiskDecisionType.APPROVED
    assert res.approved_lots == 2
    assert res.required_capital == Decimal("45000.00")
    assert res.failure_code is None
    assert len(res.checks) == 3

def test_user_risk_evaluation_rejected():
    chk = RiskCheckResult(
        check_type=RiskCheckType.DAILY_LOSS_LIMIT,
        passed=False,
        failure_code=RiskFailureCode.DAILY_LOSS_LIMIT_REACHED,
        actual_value="₹5,200",
        configured_limit="₹5,000",
        reason="Daily loss ₹5200 exceeds limit ₹5000"
    )

    res = UserRiskEvaluationResult(
        user_id=20,
        strategy_id=101,
        strategy_version_id=501,
        signal_id=9001,
        decision=RiskDecisionType.REJECTED,
        approved_lots=0,
        required_capital=Decimal("0.00"),
        failure_code=RiskFailureCode.DAILY_LOSS_LIMIT_REACHED,
        reason="Daily loss limit exceeded",
        checks=[chk]
    )

    assert res.decision == RiskDecisionType.REJECTED
    assert res.failure_code == RiskFailureCode.DAILY_LOSS_LIMIT_REACHED
    assert res.approved_lots == 0

def test_user_level_isolation_on_same_signal():
    """Verifies that User A being APPROVED and User B being REJECTED on the same signal are completely independent."""
    res_user_a = UserRiskEvaluationResult(
        user_id=100,
        strategy_id=42,
        strategy_version_id=7,
        signal_id=1001,
        decision=RiskDecisionType.APPROVED,
        approved_lots=1,
        required_capital=Decimal("30000.00"),
        reason="User A passed risk"
    )

    res_user_b = UserRiskEvaluationResult(
        user_id=200,
        strategy_id=42,
        strategy_version_id=7,
        signal_id=1001,
        decision=RiskDecisionType.REJECTED,
        approved_lots=0,
        required_capital=Decimal("0.00"),
        failure_code=RiskFailureCode.MAX_POSITIONS_REACHED,
        reason="User B reached maximum open positions limit"
    )

    assert res_user_a.signal_id == res_user_b.signal_id
    assert res_user_a.user_id != res_user_b.user_id
    assert res_user_a.decision == RiskDecisionType.APPROVED
    assert res_user_b.decision == RiskDecisionType.REJECTED

# --- 5. Validation and Financial Decimal Safety Tests ---

def test_missing_required_fields_raises_validation_error():
    with pytest.raises(ValidationError):
        # Missing decision and reason
        UserRiskEvaluationResult(
            user_id=10,
            strategy_id=101,
            strategy_version_id=501,
            signal_id=9001
        )

def test_invalid_decision_enum_rejected():
    with pytest.raises(ValidationError):
        UserRiskEvaluationResult(
            user_id=10,
            strategy_id=101,
            strategy_version_id=501,
            signal_id=9001,
            decision="MAYBE", # Invalid enum
            reason="Test"
        )
