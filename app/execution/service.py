import asyncio
from datetime import datetime, date, timezone
from decimal import Decimal
import uuid
import logging
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, func, exists

from sqlalchemy.orm.attributes import set_committed_value
from app.core.database import AsyncSessionLocal
from app.core.redis import redis_manager
from app.users.models import User
from app.subscriptions.models import Subscription, Plan
from app.subscriptions import service_eligibility
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyExecution, StrategyExecutionLeg
from app.strategies.instrument_resolver import InstrumentResolver
from app.execution.models import StrategySignal, StrategyExecutionBatch, StrategyUserExecutionTrace, StrategyExecutionTraceEvent
from app.execution.schemas import UserExecutionResult, StrategyExecutionBatchResponse, StrategyUserExecutionTraceResponse, StrategyExecutionTraceEventResponse, ExecutionFailureSummaryResponse, FailureReasonCount
from app.brokers.models import BrokerAccount, UserFundSnapshot
from app.brokers.service import get_active_broker_for_user, get_today_kolkata
from app.brokers.registry import broker_registry
from app.brokers.base.schemas import OrderRequest
from app.core.exceptions import ResourceNotFoundError, ValidationError
from app.core.config import settings

import pytz
ZONE_KOLKATA = pytz.timezone("Asia/Kolkata")
logger = logging.getLogger(__name__)

# Bounded Concurrency Semaphore
_execution_semaphore = asyncio.Semaphore(getattr(settings, "MAX_CONCURRENT_USER_EXECUTIONS", 20))


async def resolve_candidate_users(db: AsyncSession, strategy_id: int) -> List[int]:
    """Retrieves all active user IDs whose plan subscribes to the strategy."""
    from app.subscriptions.models import PlanStrategyAccess, Plan
    stmt_plans = select(PlanStrategyAccess.plan_id).where(
        PlanStrategyAccess.strategy_id == strategy_id,
        PlanStrategyAccess.is_enabled == True
    )
    res_plans = await db.execute(stmt_plans)
    plan_ids = list(res_plans.scalars().all())
    
    # Fallback: if no restrictive PlanStrategyAccess rows exist for this strategy,
    # all active subscribed users to active plans are eligible candidates.
    if not plan_ids:
        stmt_active_plans = select(Plan.id).where(Plan.is_active == True)
        res_active = await db.execute(stmt_active_plans)
        plan_ids = list(res_active.scalars().all())

    if not plan_ids:
        return []

    stmt_users = select(Subscription.user_id).where(
        Subscription.plan_id.in_(plan_ids),
        Subscription.status == "ACTIVE"
    )
    res_users = await db.execute(stmt_users)
    return list(set(res_users.scalars().all()))


async def create_batch_record(db: AsyncSession, signal_id: int, total_users: int) -> StrategyExecutionBatch:
    """Creates a batch summary record in processing status."""
    stmt_signal = select(StrategySignal).where(StrategySignal.id == signal_id)
    res_signal = await db.execute(stmt_signal)
    signal = res_signal.scalar_one_or_none()
    if not signal:
        raise ResourceNotFoundError(f"Signal not found with id: {signal_id}")

    batch = StrategyExecutionBatch(
        signal_id=signal_id,
        strategy_id=signal.strategy_id,
        strategy_version_id=signal.strategy_version_id,
        trading_date=signal.trading_date,
        total_users=total_users,
        status="PROCESSING"
    )
    db.add(batch)
    await db.flush()
    return batch


async def update_batch_record_status(
    db: AsyncSession,
    batch_id: int,
    eligible: int,
    rejected: int,
    started: int,
    successful: int,
    failed: int,
    not_executed: int
) -> None:
    """Summarizes and updates batch execution status counts."""
    stmt = select(StrategyExecutionBatch).where(StrategyExecutionBatch.id == batch_id)
    res = await db.execute(stmt)
    batch = res.scalar_one()

    batch.eligible_users = eligible
    batch.rejected_users = rejected
    batch.execution_started_users = started
    batch.successful_users = successful
    batch.failed_users = failed
    batch.not_executed_users = not_executed
    batch.status = "COMPLETED_WITH_ERRORS" if failed > 0 else "COMPLETED"
    batch.completed_at = datetime.now(timezone.utc)
    
    db.add(batch)
    await db.flush()


async def log_event(db: AsyncSession, trace_id: int, step: str, status: str, message: str, error_code: str = None) -> None:
    """Logs trace event timeline step."""
    event = StrategyExecutionTraceEvent(
        execution_trace_id=trace_id,
        step=step,
        status=status,
        message=message,
        error_code=error_code
    )
    db.add(event)
    await db.flush()


async def fail_trace(
    db: AsyncSession,
    trace: StrategyUserExecutionTrace,
    step: str,
    failure_code: str,
    reason: str,
    final_status: str
) -> UserExecutionResult:
    """Marks trace status as failed or rejected and returns execution error result."""
    trace.status = final_status
    trace.current_step = step
    trace.failure_code = failure_code
    trace.failure_reason = reason
    trace.completed_at = datetime.now(timezone.utc)
    
    db.add(trace)
    await db.flush()

    await log_event(db, trace.id, step, "FAILED", reason, failure_code)
    await log_event(db, trace.id, "EXECUTION_COMPLETE", "FAILED", f"Execution terminated with status: {final_status}", failure_code)

    is_eligible = final_status in ["FAILED", "UNKNOWN"]
    return UserExecutionResult(
        eligible=is_eligible,
        executed=False,
        status=final_status,
        failureCode=failure_code,
        failureReason=reason
    )


async def process_user(db: AsyncSession, batch: StrategyExecutionBatch, user_id: int) -> UserExecutionResult:
    """Processes strategy copy trading legs execution for a single user context with Account-Level Execution Guard."""
    async with _execution_semaphore:
        # Acquire Account Execution Lock lock:user_execution:{user_id}
        async with redis_manager.lock(f"lock:user_execution:{user_id}", timeout=15.0):
            stmt_strat = select(Strategy).where(Strategy.id == batch.strategy_id)
            res_strat = await db.execute(stmt_strat)
            strategy = res_strat.scalar_one()

            stmt_version = select(StrategyVersion).where(StrategyVersion.id == batch.strategy_version_id)
            res_version = await db.execute(stmt_version)
            version = res_version.scalar_one()

            # Load version relations
            stmt_legs = select(StrategyLeg).where(StrategyLeg.strategy_version_id == version.id).order_by(StrategyLeg.sequence.asc())
            res_legs = await db.execute(stmt_legs)
            set_committed_value(version, "legs", list(res_legs.scalars().all()))

            correlation_id = f"STRAT-{strategy.id}-SIG-{batch.signal_id}-USR-{user_id}-{str(uuid.uuid4())[:8]}"

            # 1. Initialize trace record
            trace = StrategyUserExecutionTrace(
                execution_batch_id=batch.id,
                signal_id=batch.signal_id,
                strategy_id=strategy.id,
                strategy_version_id=version.id,
                user_id=user_id,
                status="PENDING",
                correlation_id=correlation_id,
                current_step="INIT"
            )
            db.add(trace)
            await db.flush()

            await log_event(db, trace.id, "INIT", "SUCCESS", "Trace initialized")

            quota_reserved = False
            today = get_today_kolkata()

            try:
                # 2. Check User Active State
                trace.current_step = "USER_CHECK"
                trace.status = "ELIGIBILITY_CHECKING"
                db.add(trace)
                await db.flush()

                stmt_user = select(User).where(User.id == user_id)
                res_user = await db.execute(stmt_user)
                user = res_user.scalar_one_or_none()

                if not user or not user.is_active:
                    return await fail_trace(db, trace, "USER_CHECK", "USER_INACTIVE", "User is inactive or not found", "NOT_EXECUTED")
                
                await log_event(db, trace.id, "USER_CHECK", "SUCCESS", "User is active")

                # 3. Check Active Subscription
                trace.current_step = "SUBSCRIPTION_CHECK"
                db.add(trace)
                await db.flush()

                stmt_sub = select(Subscription).where(
                    Subscription.user_id == user_id,
                    Subscription.status == "ACTIVE"
                )
                res_sub = await db.execute(stmt_sub)
                active_sub = res_sub.scalar_one_or_none()

                if not active_sub:
                    return await fail_trace(db, trace, "SUBSCRIPTION_CHECK", "SUBSCRIPTION_INACTIVE", "No active subscription found", "NOT_EXECUTED")
                
                stmt_plan = select(Plan).where(Plan.id == active_sub.plan_id)
                res_plan = await db.execute(stmt_plan)
                plan = res_plan.scalar_one()

                trace.plan_id = plan.id
                db.add(trace)
                await db.flush()
                await log_event(db, trace.id, "SUBSCRIPTION_CHECK", "SUCCESS", f"Active subscription validated for plan: {plan.code}")

                # 4. Strategy Access & Eligibility Checking
                trace.current_step = "PLAN_STRATEGY_CHECK"
                db.add(trace)
                await db.flush()

                eligibility = await service_eligibility.check_strategy_eligibility(db, user_id, strategy.id)
                if not eligibility.eligible:
                    code = "PLAN_NOT_ALLOWED"
                    if eligibility.reason == "DAILY_LIMIT_REACHED":
                        code = "DAILY_LIMIT_REACHED"
                    return await fail_trace(db, trace, "PLAN_STRATEGY_CHECK", code, f"Plan check failed: {eligibility.reason}", "NOT_EXECUTED")
                
                await log_event(db, trace.id, "PLAN_STRATEGY_CHECK", "SUCCESS", "Strategy eligibility validated")

                # 5. Broker Selection Check BEFORE Quota Reservation
                trace.current_step = "BROKER_SESSION_CHECK"
                trace.status = "BROKER_SESSION_CHECKING"
                db.add(trace)
                await db.flush()

                try:
                    broker_account = await get_active_broker_for_user(db, user_id, today)
                except ResourceNotFoundError:
                    return await fail_trace(db, trace, "BROKER_SESSION_CHECK", "BROKER_SESSION_NOT_FOUND", "No active broker connected for user today (Asia/Kolkata)", "BROKER_SESSION_INVALID")
                except ValidationError as ex:
                    return await fail_trace(db, trace, "BROKER_SESSION_CHECK", "BROKER_SESSION_EXPIRED", str(ex), "BROKER_SESSION_INVALID")

                trace.broker_account_id = broker_account.id
                trace.broker = broker_account.broker_code
                db.add(trace)
                await db.flush()

                adapter = broker_registry.get(broker_account.broker_code)
                val_res = await adapter.validate_connection(broker_account, broker_account.credentials)

                if not val_res.is_valid:
                    failure_code = "BROKER_SESSION_EXPIRED" if val_res.status == "EXPIRED" else "BROKER_SESSION_INVALID"
                    return await fail_trace(db, trace, "BROKER_SESSION_CHECK", failure_code, val_res.message or f"Session status is {val_res.status}", "BROKER_SESSION_INVALID")

                await log_event(db, trace.id, "BROKER_SESSION_CHECK", "SUCCESS", f"{broker_account.broker_code} broker session verified")

                # 5b. Live Balance Check & 50% Maximum Allocation Rule
                trace.current_step = "BALANCE_CHECK"
                trace.status = "BALANCE_CHECKING"
                db.add(trace)
                await db.flush()

                # Calculate total order value required across all strategy legs
                total_order_value = Decimal("0.00")
                for leg in version.legs:
                    resolved = InstrumentResolver.resolve_leg_instrument(version.underlying, leg)
                    calculated_qty = leg.lots * resolved.lot_size
                    leg_price = leg.strike_value if leg.strike_value is not None and leg.strike_value > 0 else Decimal("100.00")
                    total_order_value += (Decimal(str(leg_price)) * Decimal(str(calculated_qty)))

                # Query live user balance from broker adapter
                user_balance = Decimal("0.00")
                try:
                    funds_data = await adapter.get_funds(broker_account, broker_account.credentials)
                    if funds_data and hasattr(funds_data, "available_balance") and funds_data.available_balance is not None:
                        user_balance = Decimal(str(funds_data.available_balance))
                    elif isinstance(funds_data, dict):
                        b_val = funds_data.get("availableBalance") or funds_data.get("available_balance") or funds_data.get("sodLimit") or 0
                        user_balance = Decimal(str(b_val))
                except Exception as ex:
                    logger.warning("Live broker fund fetch notice for user %s: %s", user_id, ex)

                # Fallback to UserFundSnapshot or User Wallet if broker funds are zero/unavailable
                if user_balance <= 0:
                    stmt_fund = select(UserFundSnapshot).where(
                        UserFundSnapshot.user_id == user_id,
                        UserFundSnapshot.snapshot_date == today
                    )
                    res_fund = await db.execute(stmt_fund)
                    fund_snapshot = res_fund.scalar_one_or_none()
                    if fund_snapshot and fund_snapshot.available_balance > 0:
                        user_balance = Decimal(str(fund_snapshot.available_balance))
                    else:
                        from app.wallets.models import Wallet
                        stmt_w = select(Wallet).where(Wallet.user_id == user_id)
                        res_w = await db.execute(stmt_w)
                        user_wallet = res_w.scalar_one_or_none()
                        if user_wallet and user_wallet.available_margin > 0:
                            user_balance = Decimal(str(user_wallet.available_margin))

                if user_balance <= 0:
                    return await fail_trace(
                        db, trace, "BALANCE_CHECK", "INSUFFICIENT_FUNDS",
                        "User trading balance is zero or unavailable.",
                        "NOT_EXECUTED"
                    )

                # Enforce 50% Balance Cap Rule: Order Value must be <= 50% of available balance
                max_allowed_allocation = user_balance * Decimal("0.50")
                if total_order_value > max_allowed_allocation:
                    fail_msg = (
                        f"Order value (₹{total_order_value:,.2f}) exceeds 50% maximum allocation limit of user balance "
                        f"(Available Balance: ₹{user_balance:,.2f}, Max 50% Allowed: ₹{max_allowed_allocation:,.2f})."
                    )
                    return await fail_trace(
                        db, trace, "BALANCE_CHECK", "ORDER_EXCEEDS_50_PCT_BALANCE",
                        fail_msg, "REJECTED"
                    )

                await log_event(
                    db, trace.id, "BALANCE_CHECK", "SUCCESS",
                    f"Balance check passed: Order value ₹{total_order_value:,.2f} is within 50% of available balance ₹{user_balance:,.2f} (50% Cap: ₹{max_allowed_allocation:,.2f})"
                )

                # 5c. Admin-Configured Max Order Value Safety Cap Enforcement (Default ₹5,000)
                trace.current_step = "SAFETY_CAP_CHECK"
                trace.status = "SAFETY_CAP_CHECKING"
                db.add(trace)
                await db.flush()

                from app.core.settings_service import SystemSettingsService
                max_order_cap_val = await SystemSettingsService.get_max_order_value_cap(db)
                max_order_cap = Decimal(str(max_order_cap_val))

                # Enforce Max Order Value Safety Cap across live executions
                if strategy.mode != "PAPER" and total_order_value > max_order_cap:
                    if len(version.legs) == 1 and version.legs[0].strike_value and version.legs[0].strike_value > 0:
                        leg = version.legs[0]
                        leg_price = Decimal(str(leg.strike_value))
                        max_allowed_qty = int(max_order_cap // leg_price)
                        if max_allowed_qty >= 1:
                            old_val = total_order_value
                            resolved = InstrumentResolver.resolve_leg_instrument(version.underlying, leg)
                            lot_size = resolved.lot_size if resolved.lot_size > 0 else 1
                            scaled_lots = max(1, max_allowed_qty // lot_size)
                            scaled_qty = scaled_lots * lot_size
                            scaled_total_val = leg_price * Decimal(str(scaled_qty))
                            if scaled_total_val <= max_order_cap:
                                total_order_value = scaled_total_val
                                await log_event(
                                    db, trace.id, "SAFETY_CAP_CHECK", "SUCCESS",
                                    f"Scaled order from ₹{old_val:,.2f} to ₹{total_order_value:,.2f} (Qty: {scaled_qty}) to comply with Admin Safety Cap (₹{max_order_cap:,.2f})"
                                )
                            else:
                                fail_msg = f"Order value (₹{total_order_value:,.2f}) exceeds Admin Safety Cap of ₹{max_order_cap:,.2f}."
                                return await fail_trace(db, trace, "SAFETY_CAP_CHECK", "ORDER_VALUE_EXCEEDS_CAP", fail_msg, "REJECTED")
                        else:
                            fail_msg = f"Order value (₹{total_order_value:,.2f}) exceeds Admin Safety Cap of ₹{max_order_cap:,.2f} and cannot be scaled down."
                            return await fail_trace(db, trace, "SAFETY_CAP_CHECK", "ORDER_VALUE_EXCEEDS_CAP", fail_msg, "REJECTED")
                    else:
                        fail_msg = (
                            f"Order value (₹{total_order_value:,.2f}) exceeds Admin Safety Cap of ₹{max_order_cap:,.2f}."
                        )
                        return await fail_trace(
                            db, trace, "SAFETY_CAP_CHECK", "ORDER_VALUE_EXCEEDS_CAP",
                            fail_msg, "REJECTED"
                        )

                await log_event(
                    db, trace.id, "SAFETY_CAP_CHECK", "SUCCESS",
                    f"Safety cap check passed: Order value ₹{total_order_value:,.2f} is within Admin Safety Cap of ₹{max_order_cap:,.2f}"
                )

                # 6. Atomic Quota Reservation
                trace.current_step = "QUOTA_RESERVATION"
                trace.status = "QUOTA_RESERVING"
                db.add(trace)
                await db.flush()

                reservation = await service_eligibility.reserve_strategy_execution(db, user_id, strategy.id, today)
                if not reservation.reserved:
                    return await fail_trace(db, trace, "QUOTA_RESERVATION", "DAILY_LIMIT_REACHED", f"Limit reached: {reservation.reason}", "QUOTA_REJECTED")

                quota_reserved = True
                await log_event(db, trace.id, "QUOTA_RESERVATION", "SUCCESS", f"Quota reserved: {reservation.usedExecutionCount}/{reservation.maxExecutionLimit}")

                # 7. Start Position Execution
                trace.status = "PROCESSING"
                trace.started_at = datetime.now(timezone.utc)
                trace.current_step = "ORDER_PLACEMENT"
                db.add(trace)
                await db.flush()

                execution = StrategyExecution(
                    strategy_id=strategy.id,
                    strategy_version_id=version.id,
                    user_id=user_id,
                    execution_trace_id=trace.id,
                    status="RUNNING",
                    entry_time=datetime.now(timezone.utc)
                )
                db.add(execution)
                await db.flush()

                exec_logs = [f"[{datetime.now()}] Started execution in {strategy.mode} mode using broker {broker_account.broker_code}."]
                all_legs_success = True
                any_leg_placed = False

                # 8. Loop and place legs via Broker Adapter with Idempotency Lock
                for leg in version.legs:
                    resolved = InstrumentResolver.resolve_leg_instrument(version.underlying, leg)
                    calculated_qty = leg.lots * resolved.lot_size
                    # Ensure individual leg quantity stays strictly under Admin Safety Cap
                    if strategy.mode != "PAPER" and leg.strike_value and leg.strike_value > 0:
                        leg_val = Decimal(str(leg.strike_value)) * Decimal(str(calculated_qty))
                        if leg_val > max_order_cap:
                            max_qty = int(max_order_cap // Decimal(str(leg.strike_value)))
                            if max_qty >= 1:
                                calculated_qty = max_qty
                    leg_cid = f"{correlation_id}-LEG-{leg.sequence}"

                    exec_leg = StrategyExecutionLeg(
                        strategy_execution_id=execution.id,
                        strategy_leg_id=leg.id,
                        correlation_id=leg_cid,
                        quantity=calculated_qty,
                        requested_quantity=calculated_qty,
                        requested_price=leg.strike_value or Decimal("0.00"),
                        status="PENDING"
                    )
                    db.add(exec_leg)
                    await db.flush()

                    leg_msg = f"Leg {leg.sequence}: {leg.side} {leg.segment} Symbol: {resolved.trading_symbol} Lots: {leg.lots} (Qty: {calculated_qty})"
                    await log_event(db, trace.id, "ORDER_PLACING", "PENDING", f"Placing leg: {leg_msg}")

                    if strategy.mode == "PAPER":
                        exec_leg.status = "FILLED"
                        exec_leg.filled_quantity = calculated_qty
                        exec_leg.price = leg.strike_value if leg.strike_value is not None else Decimal("100.00")
                        exec_leg.average_fill_price = exec_leg.price
                        exec_leg.broker_order_id = f"PAPER-{str(uuid.uuid4())[:8]}"
                        db.add(exec_leg)
                        
                        exec_logs.append(f"[{datetime.now()}] PAPER Leg {leg.sequence} filled at {exec_leg.price}")
                        await log_event(db, trace.id, "ORDER_PLACED", "SUCCESS", f"PAPER Leg filled: {leg_msg}")
                        any_leg_placed = True
                    else:
                        # LIVE Execution under Redis Idempotency Lock
                        async with redis_manager.lock(f"lock:order:idempotency:{leg_cid}", timeout=15.0):
                            try:
                                order_req = OrderRequest(
                                    trading_symbol=resolved.trading_symbol,
                                    security_id=resolved.security_id,
                                    exchange_segment=resolved.exchange_segment,
                                    product_type="INTRADAY",
                                    order_type="MARKET",
                                    transaction_type=leg.side,
                                    quantity=calculated_qty,
                                    correlation_id=leg_cid
                                )
                                order_response = await adapter.place_order(broker_account, broker_account.credentials, order_req)
                                
                                broker_order_id = order_response.broker_order_id
                                exec_leg.status = order_response.order_status
                                exec_leg.filled_quantity = calculated_qty
                                exec_leg.price = leg.strike_value if (leg.strike_value is not None and leg.strike_value > 0) else Decimal("15.00")
                                exec_leg.average_fill_price = exec_leg.price
                                exec_leg.broker_order_id = broker_order_id
                                db.add(exec_leg)

                                exec_logs.append(f"[{datetime.now()}] LIVE Leg {leg.sequence} executed via {broker_account.broker_code}. Broker ID: {broker_order_id}, Status: {order_response.order_status}")
                                await log_event(db, trace.id, "ORDER_PLACED", "SUCCESS", f"LIVE Leg placed: {leg_msg} (Broker ID: {broker_order_id})")
                                any_leg_placed = True
                            except Exception as ex:
                                all_legs_success = False
                                exec_leg.status = "REJECTED"
                                exec_leg.rejection_reason = str(ex)
                                db.add(exec_leg)

                                exec_logs.append(f"[{datetime.now()}] ERROR placing leg {leg.sequence}: {str(ex)}")
                                await log_event(db, trace.id, "ORDER_PLACING", "FAILED", f"Failed placing order: {leg_msg}. Error: {str(ex)}", "BROKER_ORDER_REJECTED")

                execution.execution_logs = "\n".join(exec_logs)
                
                if all_legs_success:
                    execution.status = "SUCCESS"
                    db.add(execution)
                    trace.status = "EXECUTED"
                    trace.current_step = "ORDER_FILLED"
                    trace.completed_at = datetime.now(timezone.utc)
                    db.add(trace)
                    return UserExecutionResult(eligible=True, executed=True, status="EXECUTED", executionId=execution.id)
                elif any_leg_placed:
                    execution.status = "FAILED"
                    db.add(execution)
                    trace.status = "PARTIALLY_EXECUTED"
                    trace.current_step = "ORDER_PLACEMENT"
                    trace.failure_code = "BROKER_ORDER_REJECTED"
                    trace.failure_reason = "Some legs failed to execute"
                    trace.completed_at = datetime.now(timezone.utc)
                    db.add(trace)
                    return UserExecutionResult(eligible=True, executed=False, status="PARTIALLY_EXECUTED", failureCode="BROKER_ORDER_REJECTED", failureReason="Some legs failed to execute", executionId=execution.id)
                else:
                    await db.delete(execution)
                    if quota_reserved:
                        await service_eligibility.release_strategy_execution(db, user_id, strategy.id, today)
                    trace.status = "FAILED"
                    trace.current_step = "ORDER_PLACEMENT"
                    trace.failure_code = "BROKER_ORDER_REJECTED"
                    trace.failure_reason = "All legs failed to place orders"
                    trace.completed_at = datetime.now(timezone.utc)
                    db.add(trace)
                    return UserExecutionResult(eligible=True, executed=False, status="FAILED", failureCode="BROKER_ORDER_REJECTED", failureReason="All legs failed to place orders")

            except Exception as e:
                if quota_reserved and not any_leg_placed:
                    await service_eligibility.release_strategy_execution(db, user_id, strategy.id, today)
                return await fail_trace(db, trace, "SYSTEM_ERROR", "SYSTEM_ERROR", str(e), "FAILED")


async def execute_single_user_task(batch_id: int, user_id: int) -> UserExecutionResult:
    """Independent isolated task execution runner."""
    async with AsyncSessionLocal() as db:
        try:
            stmt = select(StrategyExecutionBatch).where(StrategyExecutionBatch.id == batch_id)
            res = await db.execute(stmt)
            batch = res.scalar_one()

            res_val = await process_user(db, batch, user_id)
            await db.commit()
            return res_val
        except Exception as ex:
            await db.rollback()
            return UserExecutionResult(eligible=False, executed=False, status="FAILED", failureCode="SYSTEM_ERROR", failureReason=str(ex))


async def execute_signal_batch(signal_id: int) -> None:
    """Executes signal batch."""
    async with AsyncSessionLocal() as db:
        stmt_sig = select(StrategySignal).where(StrategySignal.id == signal_id)
        res_sig = await db.execute(stmt_sig)
        signal = res_sig.scalar_one_or_none()
        if not signal:
            raise ResourceNotFoundError(f"Signal not found with id: {signal_id}")

        candidate_ids = await resolve_candidate_users(db, signal.strategy_id)
        batch = await create_batch_record(db, signal_id, len(candidate_ids))
        batch_id = batch.id
        await db.commit()

    tasks = [execute_single_user_task(batch_id, uid) for uid in candidate_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    eligible = 0
    rejected = 0
    started = 0
    successful = 0
    failed = 0
    not_executed = 0

    for res in results:
        if isinstance(res, Exception):
            failed += 1
            started += 1
            continue

        if res.eligible:
            eligible += 1
        else:
            rejected += 1

        if res.status == "EXECUTED":
            successful += 1
            started += 1
        elif res.status in ["PARTIALLY_EXECUTED", "FAILED"]:
            failed += 1
            started += 1
        else:
            not_executed += 1

    async with AsyncSessionLocal() as db:
        await update_batch_record_status(db, batch_id, eligible, rejected, started, successful, failed, not_executed)
        await db.commit()


async def exit_all_positions(db: AsyncSession, strategy_id: int) -> None:
    """Performs manual square-off with live Dhan opposite market orders and net_qty == 0 verification."""
    stmt = select(StrategyExecution).where(
        StrategyExecution.strategy_id == strategy_id,
        StrategyExecution.status == "RUNNING"
    )
    res = await db.execute(stmt)
    active_executions = list(res.scalars().all())

    for exec in active_executions:
        async with redis_manager.lock(f"lock:user_execution:{exec.user_id}", timeout=15.0):
            async with redis_manager.lock(f"lock:squareoff:{exec.user_id}:{strategy_id}", timeout=15.0):
                try:
                    account = await get_active_broker_for_user(db, exec.user_id)
                    adapter = broker_registry.get(account.broker_code)
                    live_positions = await adapter.get_positions(account, account.credentials)
                    
                    for pos in live_positions:
                        if pos.net_qty != 0:
                            exit_side = "SELL" if pos.net_qty > 0 else "BUY"
                            exit_qty = abs(pos.net_qty)
                            order_req = OrderRequest(
                                trading_symbol=pos.trading_symbol,
                                security_id=pos.security_id,
                                transaction_type=exit_side,
                                quantity=exit_qty,
                                product_type="INTRADAY",
                                order_type="MARKET",
                                correlation_id=f"SQOFF-{exec.id}-{str(uuid.uuid4())[:8]}"
                            )
                            await adapter.place_order(account, account.credentials, order_req)
                    
                    exec.status = "SQUARED_OFF"
                    exec.exit_time = datetime.now(timezone.utc)
                    exec.execution_logs = (exec.execution_logs or "") + f"\n[{datetime.now()}] Live market square-off executed cleanly."
                    db.add(exec)
                except Exception as ex:
                    logger.error("Square-off failed for execution %s: %s", exec.id, str(ex))
                    exec.status = "SQUARE_OFF_FAILED"
                    exec.execution_logs = (exec.execution_logs or "") + f"\n[{datetime.now()}] Square-off failed: {str(ex)}"
                    db.add(exec)

    await db.flush()
