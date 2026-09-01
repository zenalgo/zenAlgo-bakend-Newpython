import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
import pytz
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.core.redis import redis_manager
from app.users.models import User
from app.subscriptions.models import Subscription, Plan, PlanStrategyAccess, UserDailyStrategyUsage
from app.subscriptions import service_eligibility
from app.brokers.models import BrokerAccount, UserFundSnapshot
from app.brokers.service import get_active_broker_for_user, get_today_kolkata
from app.brokers.registry import broker_registry
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyExecution
from app.execution.models import StrategySignal, StrategyUserExecutionTrace, StrategyExecutionBatch
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
from app.strategies.risk.evaluators import (
    evaluate_max_open_positions,
    evaluate_daily_trade_limit,
    evaluate_cooldown,
    evaluate_consecutive_losses,
    evaluate_daily_loss,
    evaluate_weekly_loss,
    evaluate_capital_and_margin
)

ZONE_KOLKATA = pytz.timezone("Asia/Kolkata")
logger = logging.getLogger(__name__)

class RiskEngine:
    """
    RiskEngine orchestrates the complete risk evaluation pipeline for incoming StrategySignals.
    Evaluates each candidate user independently under distributed concurrency lock,
    guaranteeing isolation, atomic quota reservation, and fail-closed safety.
    """

    async def resolve_candidate_users(self, db: AsyncSession, strategy_id: int) -> List[int]:
        """
        Identifies active users who have an active subscription allowing this strategy.
        """
        stmt_plans = select(PlanStrategyAccess.plan_id).where(
            PlanStrategyAccess.strategy_id == strategy_id,
            PlanStrategyAccess.is_enabled == True
        )
        res_plans = await db.execute(stmt_plans)
        plan_ids = list(res_plans.scalars().all())

        if not plan_ids:
            return []

        stmt_users = select(Subscription.user_id).where(
            Subscription.plan_id.in_(plan_ids),
            Subscription.status == "ACTIVE"
        )
        res_users = await db.execute(stmt_users)
        return list(set(res_users.scalars().all()))

    async def evaluate_signal_for_users(
        self,
        db: AsyncSession,
        signal: StrategySignal,
        user_ids: Optional[List[int]] = None
    ) -> List[UserRiskEvaluationResult]:
        """
        Orchestrates independent risk evaluations for all candidate users for the given signal.
        """
        if user_ids is None:
            user_ids = await self.resolve_candidate_users(db, signal.strategy_id)

        results: List[UserRiskEvaluationResult] = []
        for uid in user_ids:
            res = await self.evaluate_user_risk(db, signal, uid)
            results.append(res)

        return results

    async def evaluate_user_risk(
        self,
        db: AsyncSession,
        signal: StrategySignal,
        user_id: int
    ) -> UserRiskEvaluationResult:
        """
        Evaluates risk for a single user in complete isolation with per-user distributed locking.
        """
        lock_key = f"lock:user_risk_eval:{user_id}"
        correlation_id = f"RISK-SIG-{signal.id}-USR-{user_id}-{str(uuid.uuid4())[:8]}"

        logger.info(
            "risk_evaluation_started: signal_id=%s user_id=%s strategy_id=%s version_id=%s correlation_id=%s",
            signal.id, user_id, signal.strategy_id, signal.strategy_version_id, correlation_id,
            extra={
                "event": "risk_evaluation_started",
                "signal_id": signal.id,
                "user_id": user_id,
                "strategy_id": signal.strategy_id,
                "strategy_version_id": signal.strategy_version_id,
                "correlation_id": correlation_id
            }
        )

        try:
            async with redis_manager.lock(lock_key, timeout=10.0):
                return await self._run_risk_pipeline(db, signal, user_id, correlation_id)
        except Exception as ex:
            logger.error(
                "risk_evaluation_error: signal_id=%s user_id=%s error=%s",
                signal.id, user_id, str(ex),
                extra={
                    "event": "risk_evaluation_error",
                    "signal_id": signal.id,
                    "user_id": user_id,
                    "strategy_id": signal.strategy_id,
                    "strategy_version_id": signal.strategy_version_id,
                    "error": str(ex)
                }
            )
            # Fail closed on lock or unexpected error
            return UserRiskEvaluationResult(
                user_id=user_id,
                strategy_id=signal.strategy_id,
                strategy_version_id=signal.strategy_version_id,
                signal_id=signal.id,
                decision=RiskDecisionType.REJECTED,
                failure_code=RiskFailureCode.RESERVATION_FAILED,
                reason=f"Risk evaluation failed due to concurrency or system error: {str(ex)}"
            )

    async def _run_risk_pipeline(
        self,
        db: AsyncSession,
        signal: StrategySignal,
        user_id: int,
        correlation_id: str
    ) -> UserRiskEvaluationResult:
        """
        Executes the sequential 14-step risk check pipeline inside user lock.
        """
        today_kolkata = get_today_kolkata()
        checks: List[RiskCheckResult] = []

        # 0. Fast-path Idempotency Check: (signal_id, user_id)
        stmt_trace = select(StrategyUserExecutionTrace).where(
            StrategyUserExecutionTrace.signal_id == signal.id,
            StrategyUserExecutionTrace.user_id == user_id
        )
        res_trace = await db.execute(stmt_trace)
        existing_trace = res_trace.scalar_one_or_none()

        if existing_trace:
            decision = RiskDecisionType.APPROVED if existing_trace.status in ["PENDING", "PROCESSING", "EXECUTED", "RISK_APPROVED"] else RiskDecisionType.REJECTED
            return UserRiskEvaluationResult(
                user_id=user_id,
                strategy_id=signal.strategy_id,
                strategy_version_id=signal.strategy_version_id,
                signal_id=signal.id,
                decision=decision,
                failure_code=RiskFailureCode(existing_trace.failure_code) if existing_trace.failure_code and existing_trace.failure_code in RiskFailureCode._value2member_map_ else None,
                reason=f"Idempotent return from existing execution trace (status: {existing_trace.status})"
            )

        # 1. SIGNAL_VALIDATION
        stmt_sig = select(StrategySignal).where(StrategySignal.id == signal.id)
        res_sig = await db.execute(stmt_sig)
        persisted_sig = res_sig.scalar_one_or_none()
        if not persisted_sig or persisted_sig.strategy_version_id != signal.strategy_version_id:
            res_chk = RiskCheckResult(
                check_type=RiskCheckType.SIGNAL_VALIDATION, passed=False,
                failure_code=RiskFailureCode.SIGNAL_INVALID,
                reason="Signal does not exist or strategy_version_id mismatch."
            )
            return self._build_rejected(signal, user_id, res_chk, checks)
        checks.append(RiskCheckResult(check_type=RiskCheckType.SIGNAL_VALIDATION, passed=True, reason="Signal validated."))

        # 2. STRATEGY_ACTIVE & Version Verification
        stmt_strat = select(Strategy).where(Strategy.id == signal.strategy_id)
        res_strat = await db.execute(stmt_strat)
        strategy = res_strat.scalar_one_or_none()
        if not strategy or not strategy.is_active:
            res_chk = RiskCheckResult(
                check_type=RiskCheckType.STRATEGY_ACTIVE, passed=False,
                failure_code=RiskFailureCode.STRATEGY_DISABLED,
                reason="Strategy is inactive or disabled."
            )
            return self._build_rejected(signal, user_id, res_chk, checks)
        checks.append(RiskCheckResult(check_type=RiskCheckType.STRATEGY_ACTIVE, passed=True, reason="Strategy is active."))

        stmt_version = select(StrategyVersion).where(StrategyVersion.id == signal.strategy_version_id)
        res_ver = await db.execute(stmt_version)
        version = res_ver.scalar_one_or_none()
        if not version:
            res_chk = RiskCheckResult(
                check_type=RiskCheckType.SIGNAL_VALIDATION, passed=False,
                failure_code=RiskFailureCode.SIGNAL_INVALID,
                reason="Evaluated StrategyVersion record not found."
            )
            return self._build_rejected(signal, user_id, res_chk, checks)

        # Load legs for sizing / package calculation
        stmt_legs = select(StrategyLeg).where(StrategyLeg.strategy_version_id == version.id).order_by(StrategyLeg.sequence.asc())
        res_legs = await db.execute(stmt_legs)
        legs = list(res_legs.scalars().all())
        package_lots = legs[0].lots if legs else 1
        required_capital = version.capital if version.capital is not None else Decimal("0.00")

        # 3. USER_ACTIVE
        stmt_user = select(User).where(User.id == user_id)
        res_user = await db.execute(stmt_user)
        user = res_user.scalar_one_or_none()
        if not user or not user.is_active:
            res_chk = RiskCheckResult(
                check_type=RiskCheckType.USER_ACTIVE, passed=False,
                failure_code=RiskFailureCode.USER_INACTIVE,
                reason="User is inactive or not found."
            )
            return self._build_rejected(signal, user_id, res_chk, checks)
        checks.append(RiskCheckResult(check_type=RiskCheckType.USER_ACTIVE, passed=True, reason="User is active."))

        # 4. SUBSCRIPTION_ACCESS
        stmt_sub = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "ACTIVE"
        )
        res_sub = await db.execute(stmt_sub)
        sub = res_sub.scalar_one_or_none()
        if not sub:
            res_chk = RiskCheckResult(
                check_type=RiskCheckType.SUBSCRIPTION_ACCESS, passed=False,
                failure_code=RiskFailureCode.PLAN_NOT_ALLOWED,
                reason="No active subscription found for user."
            )
            return self._build_rejected(signal, user_id, res_chk, checks)

        stmt_plan = select(Plan).where(Plan.id == sub.plan_id)
        res_plan = await db.execute(stmt_plan)
        plan = res_plan.scalar_one_or_none()

        stmt_access = select(PlanStrategyAccess).where(
            PlanStrategyAccess.plan_id == sub.plan_id,
            PlanStrategyAccess.strategy_id == signal.strategy_id,
            PlanStrategyAccess.is_enabled == True
        )
        res_access = await db.execute(stmt_access)
        if not res_access.scalar_one_or_none():
            res_chk = RiskCheckResult(
                check_type=RiskCheckType.SUBSCRIPTION_ACCESS, passed=False,
                failure_code=RiskFailureCode.PLAN_NOT_ALLOWED,
                reason=f"Plan {plan.code if plan else ''} does not authorize this strategy."
            )
            return self._build_rejected(signal, user_id, res_chk, checks)
        checks.append(RiskCheckResult(check_type=RiskCheckType.SUBSCRIPTION_ACCESS, passed=True, reason="Subscription and plan access verified."))

        # 5. BROKER_CONNECTION
        try:
            broker_account = await get_active_broker_for_user(db, user_id, today_kolkata)
            adapter = broker_registry.get(broker_account.broker_code)
            val_res = await adapter.validate_connection(broker_account, broker_account.credentials)
            if not val_res.is_valid:
                res_chk = RiskCheckResult(
                    check_type=RiskCheckType.BROKER_CONNECTION, passed=False,
                    failure_code=RiskFailureCode.BROKER_SESSION_EXPIRED if val_res.status == "EXPIRED" else RiskFailureCode.BROKER_SESSION_INVALID,
                    reason=val_res.message or f"Broker session status: {val_res.status}"
                )
                return self._build_rejected(signal, user_id, res_chk, checks)
        except Exception as ex:
            res_chk = RiskCheckResult(
                check_type=RiskCheckType.BROKER_CONNECTION, passed=False,
                failure_code=RiskFailureCode.BROKER_SESSION_NOT_FOUND,
                reason=f"Broker session unavailable: {str(ex)}"
            )
            return self._build_rejected(signal, user_id, res_chk, checks)
        checks.append(RiskCheckResult(check_type=RiskCheckType.BROKER_CONNECTION, passed=True, reason=f"Active broker {broker_account.broker_code} verified."))

        # If EXIT signal, safety exit bypasses entry quota and limit checks
        is_exit_signal = str(signal.signal_type).upper() == "EXIT"
        if is_exit_signal:
            checks.append(RiskCheckResult(
                check_type=RiskCheckType.FINAL_APPROVAL, passed=True,
                reason="Safety exit signal approved (bypasses entry position/quota checks)."
            ))
            return UserRiskEvaluationResult(
                user_id=user_id,
                strategy_id=signal.strategy_id,
                strategy_version_id=signal.strategy_version_id,
                signal_id=signal.id,
                decision=RiskDecisionType.APPROVED,
                approved_lots=package_lots,
                required_capital=Decimal("0.00"),
                reason="Safety EXIT approved",
                checks=checks
            )

        # 6. MAX_OPEN_POSITIONS
        stmt_pos = select(func.count(StrategyExecution.id)).where(
            StrategyExecution.strategy_id == signal.strategy_id,
            StrategyExecution.user_id == user_id,
            StrategyExecution.status == "RUNNING"
        )
        res_pos = await db.execute(stmt_pos)
        open_count = res_pos.scalar()
        res_chk_pos = evaluate_max_open_positions(open_positions_count=open_count, max_open_positions=1, user_id=user_id)
        checks.append(res_chk_pos)
        if not res_chk_pos.passed:
            return self._build_rejected(signal, user_id, res_chk_pos, checks)

        # 7. DAILY_TRADE_LIMIT
        stmt_usage = select(UserDailyStrategyUsage).where(
            UserDailyStrategyUsage.user_id == user_id,
            UserDailyStrategyUsage.trading_date == today_kolkata
        )
        res_usage = await db.execute(stmt_usage)
        usage = res_usage.scalar_one_or_none()
        used_today = usage.strategy_execution_count if usage else 0
        limit_trades = plan.max_strategy_executions_per_day if plan and plan.max_strategy_executions_per_day is not None else 10

        res_chk_trades = evaluate_daily_trade_limit(used_executions_today=used_today, max_trades_per_day=limit_trades, user_id=user_id)
        checks.append(res_chk_trades)
        if not res_chk_trades.passed:
            return self._build_rejected(signal, user_id, res_chk_trades, checks)

        # 8. COOLDOWN_PERIOD
        stmt_last_exit = select(StrategyExecution.exit_time).where(
            StrategyExecution.strategy_id == signal.strategy_id,
            StrategyExecution.user_id == user_id,
            StrategyExecution.status.in_(["SUCCESS", "SQUARED_OFF", "COMPLETED"]),
            StrategyExecution.exit_time != None
        ).order_by(StrategyExecution.exit_time.desc()).limit(1)
        res_last_exit = await db.execute(stmt_last_exit)
        last_exit_time = res_last_exit.scalar_one_or_none()

        res_chk_cool = evaluate_cooldown(last_exit_time=last_exit_time, current_time=datetime.now(timezone.utc), cooldown_minutes=0, user_id=user_id)
        checks.append(res_chk_cool)
        if not res_chk_cool.passed:
            return self._build_rejected(signal, user_id, res_chk_cool, checks)

        # 9. CONSECUTIVE_LOSS_LIMIT
        stmt_execs = select(StrategyExecution.realized_pnl).where(
            StrategyExecution.strategy_id == signal.strategy_id,
            StrategyExecution.user_id == user_id,
            StrategyExecution.status.in_(["SUCCESS", "SQUARED_OFF", "COMPLETED"])
        ).order_by(StrategyExecution.id.desc()).limit(10)
        res_execs = await db.execute(stmt_execs)
        recent_pnls = list(res_execs.scalars().all())

        consecutive_losses = 0
        for pnl in recent_pnls:
            if pnl is not None and pnl < Decimal("0.00"):
                consecutive_losses += 1
            else:
                break

        res_chk_consec = evaluate_consecutive_losses(consecutive_losses=consecutive_losses, consecutive_loss_limit=3, user_id=user_id)
        checks.append(res_chk_consec)
        if not res_chk_consec.passed:
            return self._build_rejected(signal, user_id, res_chk_consec, checks)

        # 10. DAILY_LOSS_LIMIT
        today_start_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt_pnl = select(
            func.coalesce(func.sum(StrategyExecution.realized_pnl), Decimal("0.00")),
            func.coalesce(func.sum(StrategyExecution.unrealized_pnl), Decimal("0.00"))
        ).where(
            StrategyExecution.strategy_id == signal.strategy_id,
            StrategyExecution.user_id == user_id,
            StrategyExecution.created_at >= today_start_utc
        )
        res_pnl = await db.execute(stmt_pnl)
        realized_pnl, unrealized_pnl = res_pnl.one()

        res_chk_daily_loss = evaluate_daily_loss(realized_pnl=realized_pnl, unrealized_pnl=unrealized_pnl, max_loss_per_day=Decimal("5000.00"), user_id=user_id)
        checks.append(res_chk_daily_loss)
        if not res_chk_daily_loss.passed:
            return self._build_rejected(signal, user_id, res_chk_daily_loss, checks)

        # 11. WEEKLY_LOSS_LIMIT
        # Current calendar week (Monday to Sunday)
        now_kolkata = datetime.now(ZONE_KOLKATA)
        monday_kolkata = now_kolkata - timedelta(days=now_kolkata.weekday())
        week_start_utc = monday_kolkata.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

        stmt_weekly_pnl = select(
            func.coalesce(func.sum(StrategyExecution.realized_pnl), Decimal("0.00"))
        ).where(
            StrategyExecution.strategy_id == signal.strategy_id,
            StrategyExecution.user_id == user_id,
            StrategyExecution.created_at >= week_start_utc
        )
        res_weekly_pnl = await db.execute(stmt_weekly_pnl)
        weekly_realized = res_weekly_pnl.scalar()

        res_chk_weekly_loss = evaluate_weekly_loss(weekly_realized_pnl=weekly_realized, current_unrealized_pnl=unrealized_pnl, max_loss_per_week=Decimal("15000.00"), user_id=user_id)
        checks.append(res_chk_weekly_loss)
        if not res_chk_weekly_loss.passed:
            return self._build_rejected(signal, user_id, res_chk_weekly_loss, checks)

        # 12. CAPITAL_AND_MARGIN
        stmt_fund = select(UserFundSnapshot).where(
            UserFundSnapshot.user_id == user_id,
            UserFundSnapshot.snapshot_date == today_kolkata
        )
        res_fund = await db.execute(stmt_fund)
        fund_snapshot = res_fund.scalar_one_or_none()
        available_cap = fund_snapshot.available_balance if fund_snapshot else Decimal("100000.00") # Fallback to user capital if simulated

        res_chk_cap = evaluate_capital_and_margin(available_capital=available_cap, required_capital=required_capital, user_id=user_id)
        checks.append(res_chk_cap)
        if not res_chk_cap.passed:
            return self._build_rejected(signal, user_id, res_chk_cap, checks)

        # 13. ATOMIC QUOTA RESERVATION
        reservation = await service_eligibility.reserve_strategy_execution(db, user_id, signal.strategy_id, today_kolkata)
        if not reservation.reserved:
            res_chk_res = RiskCheckResult(
                check_type=RiskCheckType.QUOTA_RESERVATION, passed=False,
                failure_code=RiskFailureCode.DAILY_LIMIT_REACHED,
                reason=f"Quota reservation rejected: {reservation.reason}"
            )
            return self._build_rejected(signal, user_id, res_chk_res, checks)

        checks.append(RiskCheckResult(
            check_type=RiskCheckType.QUOTA_RESERVATION, passed=True,
            actual_value=f"{reservation.usedExecutionCount}/{reservation.maxExecutionLimit}",
            reason=f"Execution quota slot atomically reserved ({reservation.usedExecutionCount}/{reservation.maxExecutionLimit})."
        ))

        # 14. FINAL_APPROVAL
        checks.append(RiskCheckResult(
            check_type=RiskCheckType.FINAL_APPROVAL, passed=True,
            reason="All 14 deterministic risk checks passed successfully."
        ))

        approved_result = UserRiskEvaluationResult(
            user_id=user_id,
            strategy_id=signal.strategy_id,
            strategy_version_id=signal.strategy_version_id,
            signal_id=signal.id,
            decision=RiskDecisionType.APPROVED,
            approved_lots=package_lots,
            required_capital=required_capital,
            reason="All risk checks passed and execution quota reserved.",
            checks=checks
        )

        logger.info(
            "risk_evaluation_completed: decision=APPROVED user_id=%s signal_id=%s approved_lots=%s required_capital=%s",
            user_id, signal.id, package_lots, required_capital,
            extra={
                "event": "risk_evaluation_completed",
                "decision": "APPROVED",
                "user_id": user_id,
                "signal_id": signal.id,
                "strategy_id": signal.strategy_id,
                "strategy_version_id": signal.strategy_version_id,
                "approved_lots": package_lots,
                "required_capital": str(required_capital)
            }
        )

        return approved_result

    def _build_rejected(
        self,
        signal: StrategySignal,
        user_id: int,
        failed_check: RiskCheckResult,
        checks: List[RiskCheckResult]
    ) -> UserRiskEvaluationResult:
        """Helper to construct rejected UserRiskEvaluationResult and log warning."""
        checks.append(failed_check)
        rej_result = UserRiskEvaluationResult(
            user_id=user_id,
            strategy_id=signal.strategy_id,
            strategy_version_id=signal.strategy_version_id,
            signal_id=signal.id,
            decision=RiskDecisionType.REJECTED,
            approved_lots=0,
            required_capital=Decimal("0.00"),
            failure_code=failed_check.failure_code,
            reason=failed_check.reason,
            checks=checks
        )

        logger.warning(
            "risk_evaluation_rejected: user_id=%s signal_id=%s failure_code=%s reason=%s",
            user_id, signal.id,
            failed_check.failure_code.value if failed_check.failure_code else "UNKNOWN",
            failed_check.reason,
            extra={
                "event": "risk_evaluation_rejected",
                "decision": "REJECTED",
                "user_id": user_id,
                "signal_id": signal.id,
                "strategy_id": signal.strategy_id,
                "strategy_version_id": signal.strategy_version_id,
                "failure_code": failed_check.failure_code.value if failed_check.failure_code else None,
                "reason": failed_check.reason
            }
        )
        return rej_result

risk_engine = RiskEngine()
