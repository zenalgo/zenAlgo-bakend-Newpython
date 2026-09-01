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
    query = select(StrategyUserExecutionTrace).where(
        StrategyUserExecutionTrace.execution_batch_id == batch_id
    )
    if status_filter:
        query = query.where(StrategyUserExecutionTrace.status == status_filter.upper())
    
    query = query.order_by(StrategyUserExecutionTrace.id.asc()).offset(page * size).limit(size)
    res = await db.execute(query)
    traces = list(res.scalars().all())

    data = [
        StrategyUserExecutionTraceResponse(
            userId=t.user_id,
            status=t.status,
            currentStep=t.current_step or "INIT",
            failureCode=t.failure_code,
            failureReason=t.failure_reason or t.rejection_reason,
            executionId=None
        )
        for t in traces
    ]

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
        .options(selectinload(StrategyUserExecutionTrace.events))
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

    data = StrategyUserExecutionTraceResponse(
        userId=trace.user_id,
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
    query = select(StrategyUserExecutionTrace).where(StrategyUserExecutionTrace.user_id == user_id)
    if strategy_id:
        query = query.where(StrategyUserExecutionTrace.strategy_id == strategy_id)
    
    query = query.order_by(StrategyUserExecutionTrace.id.desc()).offset(page * size).limit(size)
    res = await db.execute(query)
    traces = list(res.scalars().all())

    data = [
        StrategyUserExecutionTraceResponse(
            userId=t.user_id,
            status=t.status,
            currentStep=t.current_step or "INIT",
            failureCode=t.failure_code,
            failureReason=t.failure_reason or t.rejection_reason,
            executionId=None
        )
        for t in traces
    ]

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
    from app.strategies.models import StrategyExecution, Strategy
    query = (
        select(StrategyExecution)
        .where(StrategyExecution.strategy_id == strategy_id)
        .options(
            selectinload(StrategyExecution.legs),
            selectinload(StrategyExecution.strategy)
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
        legs_dto = [
            StrategyExecutionLegDto(
                id=l.id,
                strategyLegId=l.strategy_leg_id,
                brokerOrderId=l.broker_order_id,
                correlationId=l.correlation_id,
                status=l.status,
                quantity=l.quantity,
                filledQuantity=l.filled_quantity or 0,
                price=float(l.price) if l.price is not None else 0.0,
                tradingSymbol=getattr(l, "trading_symbol", None)
            )
            for l in (ex.legs or [])
        ]
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

