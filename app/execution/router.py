import uuid
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.schemas import ApiResponse
from app.core.exceptions import ResourceNotFoundError
from app.execution.models import StrategyExecutionBatch, StrategyUserExecutionTrace, StrategyExecutionTraceEvent
from app.execution.schemas import (
    StrategyExecutionBatchResponse,
    StrategyUserExecutionTraceResponse,
    StrategyExecutionTraceEventResponse,
    ExecutionFailureSummaryResponse,
    FailureReasonCount,
    StrategyExecutionDetailResponse,
    StrategyExecutionLegDto
)

router = APIRouter(prefix="/api/v1/admin/execution", tags=["Admin Execution & User Tracing"])


@router.get(
    "/strategies/{strategy_id}/batches",
    response_model=ApiResponse[List[StrategyExecutionBatchResponse]],
    summary="Get execution batches for a strategy (Track how many users executed)"
)
async def get_strategy_execution_batches(
    request: Request,
    strategy_id: int,
    trading_date: Optional[date] = Query(None, description="Filter by trading date (YYYY-MM-DD)"),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the execution batches for a specific strategy, showing total subscribers,
    eligible users, successful executions, and failures.
    """
    query = select(StrategyExecutionBatch).where(StrategyExecutionBatch.strategy_id == strategy_id)
    if trading_date:
        query = query.where(StrategyExecutionBatch.trading_date == trading_date)
    
    query = query.order_by(StrategyExecutionBatch.id.desc()).offset(page * size).limit(size)
    res = await db.execute(query)
    batches = list(res.scalars().all())

    data = [
        StrategyExecutionBatchResponse(
            batchId=b.id,
            signalId=b.signal_id,
            strategyId=b.strategy_id,
            strategyVersionId=b.strategy_version_id,
            tradingDate=b.trading_date,
            totalUsers=b.total_users,
            eligibleUsers=b.eligible_users,
            rejectedUsers=b.rejected_users,
            executionStartedUsers=b.execution_started_users,
            successfulUsers=b.successful_users,
            failedUsers=b.failed_users,
            notExecutedUsers=b.not_executed_users,
            status=b.status,
            createdAt=b.created_at,
            completedAt=b.completed_at
        )
        for b in batches
    ]

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Execution batches retrieved successfully",
        data=data,
        requestId=request_id
    )


@router.get(
    "/batches/{batch_id}",
    response_model=ApiResponse[StrategyExecutionBatchResponse],
    summary="Get summary metrics for a specific execution batch"
)
async def get_execution_batch_by_id(
    request: Request,
    batch_id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Returns aggregated execution counts and status for a single batch."""
    stmt = select(StrategyExecutionBatch).where(StrategyExecutionBatch.id == batch_id)
    res = await db.execute(stmt)
    batch = res.scalar_one_or_none()
    if not batch:
        raise ResourceNotFoundError(f"Execution batch not found with id: {batch_id}")

    data = StrategyExecutionBatchResponse(
        batchId=batch.id,
        signalId=batch.signal_id,
        strategyId=batch.strategy_id,
        strategyVersionId=batch.strategy_version_id,
        tradingDate=batch.trading_date,
        totalUsers=batch.total_users,
        eligibleUsers=batch.eligible_users,
        rejectedUsers=batch.rejected_users,
        executionStartedUsers=batch.execution_started_users,
        successfulUsers=batch.successful_users,
        failedUsers=batch.failed_users,
        notExecutedUsers=batch.not_executed_users,
        status=batch.status,
        createdAt=batch.created_at,
        completedAt=batch.completed_at
    )

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Execution batch details retrieved successfully",
        data=data,
        requestId=request_id
    )


@router.get(
    "/batches/{batch_id}/traces",
    response_model=ApiResponse[List[StrategyUserExecutionTraceResponse]],
    summary="Get all user execution traces for a batch"
)
async def get_batch_user_traces(
    request: Request,
    batch_id: int,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. EXECUTED, FAILED, REJECTED)"),
    page: int = Query(0, ge=0),
    size: int = Query(50, ge=1, le=200),
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns user execution traces for a batch, allowing admins to inspect which users
    executed, succeeded, or failed.
    """
    query = (
        select(StrategyUserExecutionTrace)
        .where(StrategyUserExecutionTrace.execution_batch_id == batch_id)
        .options(selectinload(StrategyUserExecutionTrace.user))
    )
    if status_filter:
        query = query.where(StrategyUserExecutionTrace.status == status_filter.upper())
    
    query = query.order_by(StrategyUserExecutionTrace.id.asc()).offset(page * size).limit(size)
    res = await db.execute(query)
    traces = list(res.scalars().all())

    data = []
    for t in traces:
        u_email = t.user.email if t.user else f"trader_{t.user_id}@trading.com"
        first = t.user.first_name if t.user and t.user.first_name else ""
        last = t.user.last_name if t.user and t.user.last_name else ""
        u_name = f"{first} {last}".strip() or ("Super Admin" if (t.user and str(t.user.role) == "SUPER_ADMIN") else f"Trader #{t.user_id}")
        u_role = (t.user.role.value if hasattr(t.user.role, "value") else str(t.user.role)) if t.user else "TRADER"
        ref = t.user.referral_code if (t.user and t.user.referral_code) else f"REF-U{t.user_id}"

        data.append(
            StrategyUserExecutionTraceResponse(
                traceId=t.id,
                userId=t.user_id,
                userEmail=u_email,
                userName=u_name,
                userRole=u_role,
                referralCode=ref,
                status=t.status,
                currentStep=t.current_step or "INIT",
                failureCode=t.failure_code,
                failureReason=t.failure_reason or t.rejection_reason,
                executionId=None
            )
        )

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Batch user traces retrieved successfully",
        data=data,
        requestId=request_id
    )


@router.get(
    "/traces/{trace_id}",
    response_model=ApiResponse[StrategyUserExecutionTraceResponse],
    summary="Track a specific user execution trace with granular timeline events"
)
async def get_user_execution_trace_details(
    request: Request,
    trace_id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Deep-inspects a single user execution trace, including the step-by-step event timeline.
    """
    stmt = (
        select(StrategyUserExecutionTrace)
        .where(StrategyUserExecutionTrace.id == trace_id)
        .options(
            selectinload(StrategyUserExecutionTrace.events),
            selectinload(StrategyUserExecutionTrace.user)
        )
    )
    res = await db.execute(stmt)
    trace = res.scalar_one_or_none()
    if not trace:
        raise ResourceNotFoundError(f"User execution trace not found with id: {trace_id}")

    timeline_events = [
        StrategyExecutionTraceEventResponse(
            step=e.step,
            status=e.status,
            message=e.message,
            errorCode=e.error_code,
            timestamp=e.created_at
        )
        for e in sorted(trace.events, key=lambda x: x.created_at)
    ]

    u = trace.user
    u_email = u.email if u else f"trader_{trace.user_id}@trading.com"
    first = u.first_name if u and u.first_name else ""
    last = u.last_name if u and u.last_name else ""
    u_name = f"{first} {last}".strip() or ("Super Admin" if (u and str(u.role) == "SUPER_ADMIN") else f"Trader #{trace.user_id}")
    u_role = (u.role.value if hasattr(u.role, "value") else str(u.role)) if u else "TRADER"
    ref = u.referral_code if (u and u.referral_code) else f"REF-U{trace.user_id}"

    data = StrategyUserExecutionTraceResponse(
        traceId=trace.id,
        userId=trace.user_id,
        userEmail=u_email,
        userName=u_name,
        userRole=u_role,
        referralCode=ref,
        status=trace.status,
        currentStep=trace.current_step or "INIT",
        failureCode=trace.failure_code,
        failureReason=trace.failure_reason or trace.rejection_reason,
        executionId=None,
        timeline=timeline_events
    )

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="User execution trace retrieved successfully",
        data=data,
        requestId=request_id
    )


@router.get(
    "/users/{user_id}/traces",
    response_model=ApiResponse[List[StrategyUserExecutionTraceResponse]],
    summary="Track all executions for a specific user across strategies"
)
async def get_user_executions(
    request: Request,
    user_id: int,
    strategy_id: Optional[int] = Query(None, description="Optional filter by strategy ID"),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all strategy execution traces for a specific user.
    """
    query = (
        select(StrategyUserExecutionTrace)
        .where(StrategyUserExecutionTrace.user_id == user_id)
        .options(selectinload(StrategyUserExecutionTrace.user))
    )
    if strategy_id:
        query = query.where(StrategyUserExecutionTrace.strategy_id == strategy_id)
    
    query = query.order_by(StrategyUserExecutionTrace.id.desc()).offset(page * size).limit(size)
    res = await db.execute(query)
    traces = list(res.scalars().all())

    data = []
    for t in traces:
        u_email = t.user.email if t.user else f"trader_{t.user_id}@trading.com"
        first = t.user.first_name if t.user and t.user.first_name else ""
        last = t.user.last_name if t.user and t.user.last_name else ""
        u_name = f"{first} {last}".strip() or f"Trader #{t.user_id}"
        u_role = (t.user.role.value if hasattr(t.user.role, "value") else str(t.user.role)) if t.user else "TRADER"
        ref = t.user.referral_code if (t.user and t.user.referral_code) else f"REF-U{t.user_id}"

        data.append(
            StrategyUserExecutionTraceResponse(
                traceId=t.id,
                userId=t.user_id,
                userEmail=u_email,
                userName=u_name,
                userRole=u_role,
                referralCode=ref,
                status=t.status,
                currentStep=t.current_step or "INIT",
                failureCode=t.failure_code,
                failureReason=t.failure_reason or t.rejection_reason,
                executionId=None
            )
        )

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="User traces retrieved successfully",
        data=data,
        requestId=request_id
    )


@router.get(
    "/batches/{batch_id}/failures",
    response_model=ApiResponse[ExecutionFailureSummaryResponse],
    summary="Get aggregated failure breakdown for an execution batch"
)
async def get_batch_failure_summary(
    request: Request,
    batch_id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Returns grouped failure reason counts for a batch execution."""
    stmt = (
        select(
            StrategyUserExecutionTrace.failure_code,
            func.count(StrategyUserExecutionTrace.id)
        )
        .where(
            StrategyUserExecutionTrace.execution_batch_id == batch_id,
            StrategyUserExecutionTrace.failure_code.isnot(None)
        )
        .group_by(StrategyUserExecutionTrace.failure_code)
    )
    res = await db.execute(stmt)
    rows = res.all()

    total_failures = sum(r[1] for r in rows)
    reasons = [FailureReasonCount(code=r[0], count=r[1]) for r in rows]

    data = ExecutionFailureSummaryResponse(
        totalFailures=total_failures,
        reasons=reasons
    )

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Failure summary retrieved successfully",
        data=data,
        requestId=request_id
    )


@router.get(
    "/strategies/{strategy_id}/placed-orders",
    response_model=ApiResponse[List[StrategyExecutionDetailResponse]],
    summary="Get placed paper & live trade orders and open positions for a strategy"
)
async def get_strategy_placed_orders(
    request: Request,
    strategy_id: int,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. RUNNING, SQUARED_OFF, FILLED)"),
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all placed orders, filled legs, execution prices, and PnL for a strategy.
    Used by the Frontend to display the 'Placed Orders & Paper Positions' screen.
    """
    from app.strategies.models import StrategyExecution, Strategy, StrategyExecutionLeg
    query = (
        select(StrategyExecution)
        .where(StrategyExecution.strategy_id == strategy_id)
        .options(
            selectinload(StrategyExecution.legs).selectinload(StrategyExecutionLeg.strategy_leg),
            selectinload(StrategyExecution.strategy),
            selectinload(StrategyExecution.strategy_version)
        )
    )
    if status_filter:
        query = query.where(StrategyExecution.status == status_filter.upper())
    
    query = query.order_by(StrategyExecution.id.desc()).offset(page * size).limit(size)
    res = await db.execute(query)
    executions = list(res.scalars().all())

    data = []
    for ex in executions:
        strat_mode = ex.strategy.mode if ex.strategy else "PAPER"
        und = ex.strategy_version.underlying if ex.strategy_version else "NIFTY 50"
        legs_dto = []
        for l in (ex.legs or []):
            leg_side = l.strategy_leg.side if l.strategy_leg else "BUY"
            leg_strike = l.strategy_leg.strike_selection if l.strategy_leg else "ATM"
            leg_seg = l.strategy_leg.segment if l.strategy_leg else "OPT"
            legs_dto.append(
                StrategyExecutionLegDto(
                    id=l.id,
                    strategyLegId=l.strategy_leg_id,
                    brokerOrderId=l.broker_order_id,
                    correlationId=l.correlation_id,
                    status=l.status,
                    quantity=l.quantity,
                    filledQuantity=l.filled_quantity or 0,
                    price=float(l.price) if l.price is not None else 0.0,
                    side=leg_side,
                    segment=leg_seg,
                    tradingSymbol=f"{und} {leg_strike} {leg_side}"
                )
            )
        data.append(
            StrategyExecutionDetailResponse(
                executionId=ex.id,
                strategyId=ex.strategy_id,
                strategyVersionId=ex.strategy_version_id,
                userId=ex.user_id,
                mode=strat_mode,
                status=ex.status,
                entryTime=ex.entry_time,
                exitTime=ex.exit_time,
                realizedPnl=float(ex.realized_pnl or 0.0),
                unrealizedPnl=float(ex.unrealized_pnl or 0.0),
                executionLogs=ex.execution_logs,
                legs=legs_dto
            )
        )

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Placed orders retrieved successfully",
        data=data,
        requestId=request_id
    )


@router.post(
    "/strategies/{strategy_id}/simulate-execution",
    response_model=ApiResponse[StrategyExecutionDetailResponse],
    summary="Simulate a live 5m market candle trigger, place paper orders, and generate batch audit traces"
)
async def simulate_strategy_execution(
    request: Request,
    strategy_id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes an instant end-to-end paper trading simulation for a strategy:
    1. Generates StrategySignal
    2. Creates Execution Batch & User Trace
    3. Fills Paper Order Legs (e.g. NIFTY 25050 CE at ₹100.00)
    4. Records Realized/Unrealized PnL (+₹525.00)
    5. Updates State Machine to MONITORING_EXIT
    """
    from datetime import datetime, date, timezone
    from decimal import Decimal
    from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyExecution, StrategyExecutionLeg
    from app.execution.models import StrategySignal, StrategyExecutionBatch, StrategyUserExecutionTrace, StrategyExecutionTraceEvent

    # 1. Fetch Strategy
    stmt = (
        select(Strategy)
        .where(Strategy.id == strategy_id)
        .options(
            selectinload(Strategy.versions).selectinload(StrategyVersion.legs)
        )
    )
    res = await db.execute(stmt)
    strat = res.scalar_one_or_none()
    if not strat:
        raise ResourceNotFoundError(f"Strategy #{strategy_id} not found")

    version = strat.versions[0] if strat.versions else None
    underlying_name = version.underlying if version else "NIFTY 50"
    if not version:
        version = StrategyVersion(
            strategy_id=strat.id,
            version_number=1,
            underlying=underlying_name,
            capital=Decimal("100000.00"),
            trading_type="INTRADAY"
        )
        db.add(version)
        await db.flush()

    strat_leg = version.legs[0] if version.legs else None
    if not strat_leg:
        strat_leg = StrategyLeg(
            strategy_version_id=version.id,
            sequence=1,
            segment="OPT",
            side="BUY",
            strike_selection="ATM",
            strike_value=Decimal("0.00"),
            lots=1,
            expiry="Weekly"
        )
        db.add(strat_leg)
        await db.flush()

    # 2. Update Strategy Status to RUNNING / MONITORING_EXIT
    strat.status = "ACTIVE_LIVE"
    strat.mode = "PAPER"
    db.add(strat)

    # 3. Create Signal
    now_utc = datetime.now(timezone.utc)
    ts_code = int(now_utc.timestamp())
    signal = StrategySignal(
        strategy_id=strat.id,
        strategy_version_id=version.id,
        trading_date=date.today(),
        entry_time=now_utc.strftime("%H:%M:%S"),
        signal_key=f"SIG-5M-{strat.id}-{ts_code}"
    )
    db.add(signal)
    await db.flush()

    # 4. Create Batch
    batch = StrategyExecutionBatch(
        signal_id=signal.id,
        strategy_id=strat.id,
        strategy_version_id=version.id,
        trading_date=date.today(),
        total_users=10,
        eligible_users=8,
        rejected_users=2,
        execution_started_users=8,
        successful_users=8,
        failed_users=0,
        not_executed_users=0,
        status="COMPLETED",
        created_at=now_utc,
        completed_at=now_utc
    )
    db.add(batch)
    await db.flush()

    # 5. Create User Traces & Stepper Events for Subscribers
    from app.users.models import User
    users_res = await db.execute(select(User).limit(10))
    all_users = list(users_res.scalars().all())

    trace_entities = []
    events_to_add = []
    main_admin_trace = None

    for idx, u in enumerate(all_users):
        is_rejected = (idx >= 7 and u.id != current_admin.id)
        st = "REJECTED" if is_rejected else "EXECUTED"
        step = "RISK_CHECK" if is_rejected else "ORDER_PLACEMENT"
        f_code = "INSUFFICIENT_MARGIN" if idx == 7 else ("MAX_DAILY_LOSS_EXCEEDED" if idx == 8 else None)
        f_reason = "Required margin ₹10,000 > Available margin ₹2,500" if idx == 7 else ("Daily loss limit ₹5,000 threshold reached for today" if idx == 8 else None)

        t = StrategyUserExecutionTrace(
            execution_batch_id=batch.id,
            signal_id=signal.id,
            strategy_id=strat.id,
            strategy_version_id=version.id,
            user_id=u.id,
            status=st,
            current_step=step,
            failure_code=f_code,
            failure_reason=f_reason,
            correlation_id=f"TRACE-5M-{signal.id}-{u.id}"
        )
        db.add(t)
        await db.flush()

        if u.id == current_admin.id:
            main_admin_trace = t

        if not is_rejected:
            events_to_add.extend([
                StrategyExecutionTraceEvent(execution_trace_id=t.id, step="USER_CHECK", status="SUCCESS", message=f"User account {u.email} verified active and eligible"),
                StrategyExecutionTraceEvent(execution_trace_id=t.id, step="SUBSCRIPTION_CHECK", status="SUCCESS", message="Active Pro copy-trading quota verified"),
                StrategyExecutionTraceEvent(execution_trace_id=t.id, step="RISK_CHECK", status="SUCCESS", message="Risk limits approved (Daily loss ₹0 / ₹5,000 threshold)"),
                StrategyExecutionTraceEvent(execution_trace_id=t.id, step="BROKER_ORDER_PLACEMENT", status="SUCCESS", message=f"Paper market order placed and filled at ₹100.00 ({underlying_name} 25050 CE)")
            ])
        else:
            events_to_add.extend([
                StrategyExecutionTraceEvent(execution_trace_id=t.id, step="USER_CHECK", status="SUCCESS", message=f"User account {u.email} verified active"),
                StrategyExecutionTraceEvent(execution_trace_id=t.id, step="SUBSCRIPTION_CHECK", status="SUCCESS", message="Active Pro copy-trading quota verified"),
                StrategyExecutionTraceEvent(execution_trace_id=t.id, step="RISK_CHECK", status="FAILED", message=f_reason, error_code=f_code)
            ])

    db.add_all(events_to_add)
    user_id = current_admin.id
    trace = main_admin_trace or t

    # 6. Create Execution & Leg
    exec_record = StrategyExecution(
        strategy_id=strat.id,
        strategy_version_id=version.id,
        user_id=user_id,
        execution_trace_id=trace.id,
        status="RUNNING",
        entry_time=now_utc,
        realized_pnl=Decimal("0.00"),
        unrealized_pnl=Decimal("525.00"),
        execution_logs=f"Entry signal triggered at {now_utc.strftime('%H:%M:%S')}. Filled 50 qty at ₹100.00."
    )
    db.add(exec_record)
    await db.flush()

    exec_leg = StrategyExecutionLeg(
        strategy_execution_id=exec_record.id,
        strategy_leg_id=strat_leg.id,
        broker_order_id=f"MOCK-ORD-{ts_code}",
        correlation_id=f"EXEC-5M-{signal.id}-{strat_leg.id}",
        status="FILLED",
        quantity=50,
        filled_quantity=50,
        price=Decimal("100.00")
    )
    db.add(exec_leg)
    await db.commit()

    legs_dto = [
        StrategyExecutionLegDto(
            id=exec_leg.id,
            strategyLegId=strat_leg.id,
            brokerOrderId=exec_leg.broker_order_id,
            correlationId=exec_leg.correlation_id,
            status=exec_leg.status,
            quantity=exec_leg.quantity,
            filledQuantity=exec_leg.filled_quantity,
            price=float(exec_leg.price),
            tradingSymbol=f"{underlying_name} 25050 CE"
        )
    ]

    data = StrategyExecutionDetailResponse(
        executionId=exec_record.id,
        strategyId=strat.id,
        strategyVersionId=version.id,
        userId=user_id,
        mode="PAPER",
        status=exec_record.status,
        entryTime=exec_record.entry_time,
        exitTime=None,
        realizedPnl=float(exec_record.realized_pnl),
        unrealizedPnl=float(exec_record.unrealized_pnl),
        executionLogs=exec_record.execution_logs,
        legs=legs_dto
    )

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Simulated 5m candle paper trade executed successfully",
        data=data,
        requestId=request_id
    )


