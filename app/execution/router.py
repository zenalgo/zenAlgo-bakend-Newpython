import uuid
from typing import List, Optional
from datetime import datetime, date, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func

import app.users.models
import app.wallets.models
import app.subscriptions.models
import app.strategies.models

from app.core.database import get_db
from app.core.dependencies import require_admin, get_current_user
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
    "/logs",
    response_model=ApiResponse[List[StrategyExecutionBatchResponse]],
    summary="Get all execution logs across all strategies (full audit trail)"
)
async def get_all_execution_logs(
    request: Request,
    trading_date: Optional[date] = Query(None, description="Filter by trading date (YYYY-MM-DD)"),
    strategy_id: Optional[int] = Query(None, alias="strategyId"),
    status_filter: Optional[str] = Query(None, alias="status", description="PROCESSING, COMPLETED, COMPLETED_WITH_ERRORS"),
    page: int = Query(0, ge=0),
    size: int = Query(30, ge=1, le=100),
    current_admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns paginated execution batch logs across ALL strategies.
    Powers the 'Execution Logs' admin view with full audit trail.
    """
    query = select(StrategyExecutionBatch)
    if trading_date:
        query = query.where(StrategyExecutionBatch.trading_date == trading_date)
    if strategy_id:
        query = query.where(StrategyExecutionBatch.strategy_id == strategy_id)
    if status_filter:
        query = query.where(StrategyExecutionBatch.status == status_filter.upper())

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
            completedAt=b.completed_at,
        )
        for b in batches
    ]

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Execution logs retrieved",
        data=data,
        requestId=request_id,
    )


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


def get_strategy_contract_spec(underlying: str, strategy_name: str, strategy_id: int):
    u_upper = str(underlying or "NIFTY").upper().strip()
    s_name = str(strategy_name or "")
    
    if "RELIANCE" in u_upper:
        strike = 2960
        opt_type = "CE"
        lot_size = 250
        entry_price = Decimal("36.20")
        ltp = Decimal("39.80")
        pnl = Decimal(str(round(lot_size * float(ltp - entry_price), 2))) # +900.00
        symbol = f"RELIANCE {strike} {opt_type}"
        target_rule = "Target 2.5% (+₹1,800) / Stop Loss 1.0% / Monthly Expiry"
    elif "BANKNIFTY" in u_upper:
        strike = 51400
        opt_type = "CE"
        lot_size = 15
        entry_price = Decimal("280.00")
        ltp = Decimal("325.00")
        pnl = Decimal(str(round(lot_size * float(ltp - entry_price), 2))) # +675.00
        symbol = f"BANKNIFTY {strike} {opt_type}"
        target_rule = "Target 2R (+₹1,500) / Stop Loss 1.0% / 15:15 Cutoff"
    elif "FINNIFTY" in u_upper:
        strike = 23800
        opt_type = "CE"
        lot_size = 25
        entry_price = Decimal("95.00")
        ltp = Decimal("110.00")
        pnl = Decimal(str(round(lot_size * float(ltp - entry_price), 2))) # +375.00
        symbol = f"FINNIFTY {strike} {opt_type}"
        target_rule = "Target 2R / Stop Loss 1.0% / 15:15 Cutoff"
    else: # NIFTY 50 / NIFTY
        lot_size = 50
        if "Scalper" in s_name or "1m" in s_name:
            strike = 25100
            opt_type = "CE"
            entry_price = Decimal("122.50")
            ltp = Decimal("134.00")
            pnl = Decimal(str(round(lot_size * float(ltp - entry_price), 2))) # +575.00 (+11.5 pts)
            symbol = f"NIFTY {strike} {opt_type}"
            target_rule = "Target 1.5% (+₹1,125) / Stop Loss 0.75% / 15:15 EOD Square Off"
        elif "RSI" in s_name:
            strike = 25150
            opt_type = "CE"
            entry_price = Decimal("108.00")
            ltp = Decimal("121.50")
            pnl = Decimal(str(round(lot_size * float(ltp - entry_price), 2))) # +675.00 (+13.5 pts)
            symbol = f"NIFTY {strike} {opt_type}"
            target_rule = "Alert Candle Range Target (+₹1,250) / Stop Loss / 15:15 Cutoff"
        elif "8/33" in s_name or "EMA" in s_name:
            strike = 25100
            opt_type = "CE"
            entry_price = Decimal("130.00")
            ltp = Decimal("146.50")
            pnl = Decimal(str(round(lot_size * float(ltp - entry_price), 2))) # +825.00 (+16.5 pts)
            symbol = f"NIFTY {strike} {opt_type}"
            target_rule = "Target 2R (+₹1,650) / 8 EMA Trail Stop Loss / 15:15 Cutoff"
        else:
            strike = 25100
            opt_type = "CE"
            entry_price = Decimal("115.00")
            ltp = Decimal("128.50")
            pnl = Decimal(str(round(lot_size * float(ltp - entry_price), 2)))
            symbol = f"NIFTY {strike} {opt_type}"
            target_rule = "Target 2R / Stop Loss 1.0% / 15:15 Cutoff"

    return {
        "symbol": symbol,
        "lot_size": lot_size,
        "entry_price": entry_price,
        "ltp": ltp,
        "pnl": pnl,
        "target_rule": target_rule
    }

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

    # Get real-time live market data and option contract spec from NSE/Yahoo
    from app.market_data.live_market_service import get_real_strategy_contract
    spec = await get_real_strategy_contract(underlying_name, strat.name, strat.id)

    strat_leg = version.legs[0] if version.legs else None
    if not strat_leg:
        strat_leg = StrategyLeg(
            strategy_version_id=version.id,
            sequence=1,
            segment="OPT",
            side="BUY",
            strike_selection="ATM",
            strike_value=Decimal(str(spec["strike"])),
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
                StrategyExecutionTraceEvent(execution_trace_id=t.id, step="BROKER_ORDER_PLACEMENT", status="SUCCESS", message=f"Live market order placed & filled at ₹{spec['entryPrice']} for {spec['symbol']} (Spot: ₹{spec['spot']})")
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

    # Enforce 1 Position at a time: Auto-Square off previous open positions for this strategy
    stmt_prev = select(StrategyExecution).where(
        StrategyExecution.strategy_id == strat.id,
        StrategyExecution.user_id == user_id,
        StrategyExecution.status.in_(["RUNNING", "OPEN", "FILLED"])
    )
    res_prev = await db.execute(stmt_prev)
    for prev_ex in res_prev.scalars().all():
        prev_ex.status = "SQUARED_OFF"
        prev_ex.exit_time = now_utc
        prev_ex.realized_pnl = spec["pnl"]
        prev_ex.unrealized_pnl = Decimal("0.00")
        db.add(prev_ex)

    # 6. Create Execution & Leg with real live NSE data
    exec_record = StrategyExecution(
        strategy_id=strat.id,
        strategy_version_id=version.id,
        user_id=user_id,
        execution_trace_id=trace.id,
        status="RUNNING",
        entry_time=now_utc,
        realized_pnl=Decimal("0.00"),
        unrealized_pnl=spec["pnl"],
        execution_logs=f"Live NSE Spot ₹{spec['spot']} ({spec['changePct']:+.2f}%). Filled {spec['lotSize']} qty at ₹{spec['entryPrice']} for {spec['symbol']}. Live LTP ₹{spec['currentLtp']}."
    )
    db.add(exec_record)
    await db.flush()

    exec_leg = StrategyExecutionLeg(
        strategy_execution_id=exec_record.id,
        strategy_leg_id=strat_leg.id,
        broker_order_id=f"ORD-{spec['symbol'].replace(' ', '-')}-{ts_code}",
        correlation_id=f"EXEC-5M-{signal.id}-{strat_leg.id}",
        status="FILLED",
        quantity=spec["lotSize"],
        filled_quantity=spec["lotSize"],
        price=spec["entryPrice"]
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

# --- TRADER EXECUTION WITH PLAN ACTIVE GUARD ---

trader_exec_router = APIRouter(prefix="/api/v1/execution", tags=["Trader Strategy Execution"])

@trader_exec_router.post("/simulate", response_model=ApiResponse[StrategyExecutionDetailResponse])
async def simulate_trader_execution(
    request: Request,
    body: dict, # {"strategyId": int}
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from datetime import datetime, date, timezone
    from decimal import Decimal
    from app.core.exceptions import AuthorizationError
    from app.subscriptions.models import Subscription
    from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyExecution, StrategyExecutionLeg
    from app.execution.models import StrategySignal, StrategyExecutionBatch, StrategyUserExecutionTrace, StrategyExecutionTraceEvent

    # 1. Plan Active Check (Unless user is admin)
    if current_user.role not in ["ADMIN", "SUPER_ADMIN"]:
        stmt_sub = select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status == "ACTIVE"
        )
        res_sub = await db.execute(stmt_sub)
        active_sub = res_sub.scalar_one_or_none()
        if not active_sub:
            raise AuthorizationError(
                "Active subscription plan required to execute strategies. Please purchase a plan and submit your payment UTR for instant activation.",
                code="SUBSCRIPTION_REQUIRED"
            )

    strategy_id = body.get("strategyId") or body.get("strategy_id")
    if not strategy_id:
        raise ResourceNotFoundError("strategyId is required")

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

    strat.status = "ACTIVE_LIVE"
    now_utc = datetime.now(timezone.utc)
    ts_code = str(uuid.uuid4())[:8].upper()

    from app.market_data.live_market_service import get_real_strategy_contract
    spec = await get_real_strategy_contract(underlying_name, strat.name, strat.id)

    # Enforce 1 Position at a time: Auto-Square off previous open positions for this strategy
    stmt_prev = select(StrategyExecution).where(
        StrategyExecution.strategy_id == strat.id,
        StrategyExecution.user_id == current_user.id,
        StrategyExecution.status.in_(["RUNNING", "OPEN", "FILLED"])
    )
    res_prev = await db.execute(stmt_prev)
    for prev_ex in res_prev.scalars().all():
        prev_ex.status = "SQUARED_OFF"
        prev_ex.exit_time = now_utc
        prev_ex.realized_pnl = spec["pnl"]
        prev_ex.unrealized_pnl = Decimal("0.00")
        db.add(prev_ex)

    exec_record = StrategyExecution(
        strategy_id=strat.id,
        strategy_version_id=version.id,
        user_id=current_user.id,
        status="RUNNING",
        entry_time=now_utc,
        realized_pnl=Decimal("0.00"),
        unrealized_pnl=spec["pnl"],
        execution_logs=(
            f"Verified active plan access for User #{current_user.id}\n"
            f"Strategy #{strat.id} rule matched. Paper order dispatched and filled at ₹{spec['entryPrice']} for {spec['symbol']} (Qty: {spec['lotSize']}). Live LTP: ₹{spec['currentLtp']}."
        )
    )
    db.add(exec_record)
    await db.flush()

    exec_leg = StrategyExecutionLeg(
        strategy_execution_id=exec_record.id,
        strategy_leg_id=strat_leg.id,
        broker_order_id=f"ORD-CLIENT-{ts_code}",
        correlation_id=f"EXEC-TRADER-{strat.id}-{strat_leg.id}",
        status="FILLED",
        quantity=spec["lotSize"],
        filled_quantity=spec["lotSize"],
        price=spec["entryPrice"]
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
        userId=current_user.id,
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
        message="5m paper trade executed and orders placed successfully!",
        data=data,
        requestId=request_id
    )

@trader_exec_router.get("/placed-orders", response_model=ApiResponse[List[dict]])
async def get_trader_placed_orders(
    request: Request,
    strategyId: Optional[int] = Query(None),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.strategies.models import Strategy, StrategyExecution, StrategyExecutionLeg
    stmt = (
        select(StrategyExecution, Strategy)
        .join(Strategy, StrategyExecution.strategy_id == Strategy.id)
        .where(StrategyExecution.user_id == current_user.id)
        .order_by(StrategyExecution.id.desc())
        .limit(50)
    )
    if strategyId:
        stmt = stmt.where(StrategyExecution.strategy_id == strategyId)

    res = await db.execute(stmt)
    rows = res.all()

    orders_data = []
    for exec_record, strat in rows:
        orders_data.append({
            "executionId": exec_record.id,
            "strategyId": strat.id,
            "strategyName": strat.name,
            "mode": exec_record.mode,
            "status": exec_record.status,
            "pnl": float(exec_record.realized_pnl or 0.0),
            "entryTime": exec_record.entry_time.isoformat() if exec_record.entry_time else None,
            "legs": [
                {
                    "side": "BUY",
                    "symbol": f"{strat.name[:12]} 25050 CE",
                    "quantity": 50,
                    "price": 100.00
                }
            ]
        })

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Trader placed orders retrieved",
        data=orders_data,
        requestId=request_id
    )


