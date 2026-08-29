from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, func
import pytz
from typing import Optional

from app.users.models import User
from app.subscriptions.models import Subscription, Plan, PlanStrategyAccess, UserDailyStrategyUsage
from app.subscriptions.schemas import EligibilityResult, QuotaReservation

ZONE_KOLKATA = pytz.timezone("Asia/Kolkata")

def build_rejection(reason: str, plan_code: Optional[str]) -> EligibilityResult:
    """Builds a rejected EligibilityResult."""
    return EligibilityResult(
        eligible=False,
        reason=reason,
        plan=plan_code,
        strategyAllowed=(reason != "PLAN_DOES_NOT_ALLOW_STRATEGY" and reason != "USER_INACTIVE" and reason != "NO_ACTIVE_SUBSCRIPTION"),
        dailyLimit=0,
        usedToday=0,
        remainingToday=0,
        walletEligible=True # Always True due to Phase 1 bypass
    )

def build_quota_rejection(reason: str, used: int, limit: int) -> QuotaReservation:
    """Builds a rejected QuotaReservation."""
    return QuotaReservation(
        reserved=False,
        reason=reason,
        usedExecutionCount=used,
        maxExecutionLimit=limit
    )

async def check_strategy_eligibility(db: AsyncSession, user_id: int, strategy_id: int) -> EligibilityResult:
    """Verifies access permissions, active status, and daily execution quota limits for a user and strategy."""
    stmt_user = select(User).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()
    if not user or not user.is_active:
        return build_rejection("USER_INACTIVE", None)

    # Fetch active subscription
    stmt_sub = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.status == "ACTIVE"
    )
    res_sub = await db.execute(stmt_sub)
    active_sub = res_sub.scalar_one_or_none()
    if not active_sub:
        return build_rejection("NO_ACTIVE_SUBSCRIPTION", None)

    # Fetch plan details
    stmt_plan = select(Plan).where(Plan.id == active_sub.plan_id)
    res_plan = await db.execute(stmt_plan)
    plan = res_plan.scalar_one()

    # 1. Strategy Access Mapping Check
    stmt_access = select(PlanStrategyAccess).where(
        PlanStrategyAccess.plan_id == plan.id,
        PlanStrategyAccess.strategy_id == strategy_id,
        PlanStrategyAccess.is_enabled == True
    )
    res_access = await db.execute(stmt_access)
    access = res_access.scalar_one_or_none()
    if not access:
        return build_rejection("PLAN_DOES_NOT_ALLOW_STRATEGY", plan.code)

    # 2. Wallet Check - BYPASSED (Always Eligible)
    # (Matches commented logic in Spring Boot)

    # 3. Daily Execution Limit
    # Get current Date in Asia/Kolkata timezone
    from datetime import datetime
    today = datetime.now(ZONE_KOLKATA).date()
    
    stmt_usage = select(UserDailyStrategyUsage).where(
        UserDailyStrategyUsage.user_id == user_id,
        UserDailyStrategyUsage.trading_date == today
    )
    res_usage = await db.execute(stmt_usage)
    usage = res_usage.scalar_one_or_none()
    used_today = usage.strategy_execution_count if usage else 0
    limit = plan.max_strategy_executions_per_day if plan.max_strategy_executions_per_day is not None else 999999

    if used_today >= limit:
        return build_rejection("DAILY_LIMIT_REACHED", plan.code)

    return EligibilityResult(
        eligible=True,
        reason=None,
        plan=plan.code,
        strategyAllowed=True,
        dailyLimit=limit,
        usedToday=used_today,
        remainingToday=max(0, limit - used_today),
        walletEligible=True
    )

async def reserve_strategy_execution(db: AsyncSession, user_id: int, strategy_id: int, trading_date: date) -> QuotaReservation:
    """Safely and atomically decrements/reserves strategy daily execution quota."""
    stmt_user = select(User).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()
    if not user or not user.is_active:
        return build_quota_rejection("USER_INACTIVE", 0, 0)

    # Fetch active subscription
    stmt_sub = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.status == "ACTIVE"
    )
    res_sub = await db.execute(stmt_sub)
    active_sub = res_sub.scalar_one_or_none()
    if not active_sub:
        return build_quota_rejection("NO_ACTIVE_SUBSCRIPTION", 0, 0)

    # Fetch plan details
    stmt_plan = select(Plan).where(Plan.id == active_sub.plan_id)
    res_plan = await db.execute(stmt_plan)
    plan = res_plan.scalar_one()

    # Strategy Access Mapping Check
    stmt_access = select(PlanStrategyAccess).where(
        PlanStrategyAccess.plan_id == plan.id,
        PlanStrategyAccess.strategy_id == strategy_id,
        PlanStrategyAccess.is_enabled == True
    )
    res_access = await db.execute(stmt_access)
    access = res_access.scalar_one_or_none()
    if not access:
        return build_quota_rejection("PLAN_DOES_NOT_ALLOW_STRATEGY", 0, 0)

    # Wallet check - bypassed

    limit = plan.max_strategy_executions_per_day if plan.max_strategy_executions_per_day is not None else 999999

    # Check and insert daily usage record with concurrency handling
    stmt_usage = select(UserDailyStrategyUsage).where(
        UserDailyStrategyUsage.user_id == user_id,
        UserDailyStrategyUsage.trading_date == trading_date
    )
    res_usage = await db.execute(stmt_usage)
    usage = res_usage.scalar_one_or_none()

    if not usage:
        # Concurrent-safe save via nested savepoint
        try:
            async with db.begin_nested():
                usage = UserDailyStrategyUsage(
                    user_id=user_id,
                    trading_date=trading_date,
                    strategy_execution_count=0
                )
                db.add(usage)
                await db.flush()
        except Exception:
            # Row was concurrently inserted; fetch it
            stmt_usage_refetch = select(UserDailyStrategyUsage).where(
                UserDailyStrategyUsage.user_id == user_id,
                UserDailyStrategyUsage.trading_date == trading_date
            )
            res_usage_refetch = await db.execute(stmt_usage_refetch)
            usage = res_usage_refetch.scalar_one()

    # Perform atomic update limit validation
    stmt_inc = (
        update(UserDailyStrategyUsage)
        .where(UserDailyStrategyUsage.user_id == user_id)
        .where(UserDailyStrategyUsage.trading_date == trading_date)
        .where(UserDailyStrategyUsage.strategy_execution_count < limit)
        .values(
            strategy_execution_count=UserDailyStrategyUsage.strategy_execution_count + 1,
            updated_at=func.now()
        )
    )
    result_inc = await db.execute(stmt_inc)
    rows_updated = result_inc.rowcount

    if rows_updated == 1:
        # Refetch to get the updated execution count
        stmt_refetch = select(UserDailyStrategyUsage.strategy_execution_count).where(
            UserDailyStrategyUsage.user_id == user_id,
            UserDailyStrategyUsage.trading_date == trading_date
        )
        res_count = await db.execute(stmt_refetch)
        updated_count = res_count.scalar()
        return QuotaReservation(
            reserved=True,
            reason=None,
            usedExecutionCount=updated_count,
            maxExecutionLimit=limit
        )
    else:
        return QuotaReservation(
            reserved=False,
            reason="DAILY_LIMIT_REACHED",
            usedExecutionCount=limit,
            maxExecutionLimit=limit
        )
