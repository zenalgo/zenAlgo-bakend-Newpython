from fastapi import APIRouter, Depends, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import uuid
from typing import List

from app.core.database import get_db
from app.core.schemas import ApiResponse
from app.core.dependencies import get_current_user, require_admin
from app.strategies.schemas import (
    StrategyRequest, StrategyResponse, StrategyValidationResponse,
    StrategyValidationError
)
from app.strategies import service
from app.strategies.models import Strategy
from app.strategies.validator import validate_strategy_request

router = APIRouter(prefix="/api/v1", tags=["Strategy Engine"])

# =========================================================================
# 1. ADMIN STRATEGY CONFIGURATION ENDPOINTS
# =========================================================================

@router.post("/admin/strategies", response_model=ApiResponse[StrategyResponse], status_code=status.HTTP_201_CREATED)
async def create_strategy(
    request: Request,
    body: StrategyRequest,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    res = await service.create_strategy(db, body, current_admin.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy created successfully",
        data=res,
        requestId=request_id
    )

@router.put("/admin/strategies/{id}", response_model=ApiResponse[StrategyResponse])
async def update_strategy(
    request: Request,
    id: int,
    body: StrategyRequest,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    res = await service.update_strategy(db, id, body, current_admin.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy updated successfully",
        data=res,
        requestId=request_id
    )

@router.get("/admin/strategies", response_model=ApiResponse[List[StrategyResponse]])
async def get_all_strategies(
    request: Request,
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1),
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    # Query with pagination
    stmt = select(Strategy).order_by(Strategy.id.desc()).offset(page * size).limit(size)
    res = await db.execute(stmt)
    strategies = res.scalars().all()

    dtos = []
    for s in strategies:
        dtos.append(await service.build_strategy_response(db, s))

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="All strategies retrieved successfully",
        data=dtos,
        requestId=request_id
    )

@router.get("/admin/strategies/{id}", response_model=ApiResponse[StrategyResponse])
async def get_strategy_by_id_for_admin(
    request: Request,
    id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Strategy).where(Strategy.id == id)
    res = await db.execute(stmt)
    strategy = res.scalar_one_or_none()
    if not strategy:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError(f"Strategy not found with ID: {id}")

    dto = await service.build_strategy_response(db, strategy)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy details retrieved",
        data=dto,
        requestId=request_id
    )

@router.post("/admin/strategies/{id}/validate", response_model=ApiResponse[StrategyValidationResponse])
async def validate_strategy(
    request: Request,
    id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    # Retrieve strategy & map to request structure for validation
    stmt = select(Strategy).where(Strategy.id == id)
    res = await db.execute(stmt)
    strategy = res.scalar_one_or_none()
    if not strategy:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError(f"Strategy not found with ID: {id}")

    # Map version details
    dto = await service.build_strategy_response(db, strategy)
    
    # Simple manual convert to request structure for validation
    # Create request model from response DTO
    legs_req = []
    for leg in dto.legs:
        legs_req.append({
            "sequence": leg.sequence,
            "segment": leg.segment,
            "side": leg.side,
            "strikeSelection": leg.strikeSelection,
            "strikeValue": leg.strikeValue,
            "expiry": leg.expiry,
            "lots": leg.lots,
            "targetType": leg.targetType,
            "targetValue": leg.targetValue,
            "stopLossType": leg.stopLossType,
            "stopLossValue": leg.stopLossValue,
            "trailingSlEnabled": leg.trailingSlEnabled,
            "trailingSlActivateType": leg.trailingSlActivateType,
            "trailingSlActivateValue": leg.trailingSlActivateValue,
            "trailingSlIncreaseBy": leg.trailingSlIncreaseBy,
            "trailingSlBy": leg.trailingSlBy
        })

    from app.strategies.schemas import StrategyLegRequest, StrategyEntrySettingRequest, StrategyExitSettingRequest
    entry_req = StrategyEntrySettingRequest(entryTime=dto.entrySetting.entryTime)
    exit_req = StrategyExitSettingRequest(
        profitMtmType=dto.exitSetting.profitMtmType,
        profitMtmValue=dto.exitSetting.profitMtmValue,
        stopLossMtmType=dto.exitSetting.stopLossMtmType,
        stopLossMtmValue=dto.exitSetting.stopLossMtmValue,
        exitTime=dto.exitSetting.exitTime,
        exitOnExpiry=dto.exitSetting.exitOnExpiry,
        exitAfterEntryType=dto.exitSetting.exitAfterEntryType,
        exitAfterEntryValue=dto.exitSetting.exitAfterEntryValue
    )

    strat_req = StrategyRequest(
        name=dto.name,
        description=dto.description,
        underlying=dto.underlying,
        capital=dto.capital,
        tradingType=dto.tradingType,
        mode=dto.mode,
        legs=[StrategyLegRequest.model_validate(l) for l in legs_req],
        entrySetting=entry_req,
        entryDays=dto.entryDays,
        exitSetting=exit_req
    )

    val_res = validate_strategy_request(strat_req)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy validation completed",
        data=val_res,
        requestId=request_id
    )

# =========================================================================
# 2. ADMIN LIFECYCLE CONTROLS
# =========================================================================

@router.post("/admin/strategies/{id}/activate-paper", response_model=ApiResponse[StrategyResponse])
async def activate_paper(
    request: Request,
    id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    # Set mode = PAPER
    stmt = select(Strategy).where(Strategy.id == id)
    res = await db.execute(stmt)
    strategy = res.scalar_one_or_none()
    if not strategy:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError(f"Strategy not found with ID: {id}")

    strategy.mode = "PAPER"
    db.add(strategy)
    await db.flush()

    res_dto = await service.update_status(db, id, "PAPER", current_admin.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy paper trading activated",
        data=res_dto,
        requestId=request_id
    )

@router.post("/admin/strategies/{id}/activate-live", response_model=ApiResponse[StrategyResponse])
async def activate_live(
    request: Request,
    id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    # Set mode = LIVE
    stmt = select(Strategy).where(Strategy.id == id)
    res = await db.execute(stmt)
    strategy = res.scalar_one_or_none()
    if not strategy:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError(f"Strategy not found with ID: {id}")

    strategy.mode = "LIVE"
    db.add(strategy)
    await db.flush()

    res_dto = await service.update_status(db, id, "ACTIVE_LIVE", current_admin.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy live trading activated",
        data=res_dto,
        requestId=request_id
    )

@router.post("/admin/strategies/{id}/pause", response_model=ApiResponse[StrategyResponse])
async def pause_strategy(
    request: Request,
    id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    res_dto = await service.update_status(db, id, "PAUSED", current_admin.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy execution paused successfully",
        data=res_dto,
        requestId=request_id
    )

@router.post("/admin/strategies/{id}/resume", response_model=ApiResponse[StrategyResponse])
async def resume_strategy(
    request: Request,
    id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    # Check current mode to resume to live or paper
    stmt = select(Strategy).where(Strategy.id == id)
    res = await db.execute(stmt)
    strategy = res.scalar_one_or_none()
    if not strategy:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError(f"Strategy not found with ID: {id}")

    target_status = "ACTIVE_LIVE" if strategy.mode == "LIVE" else "PAPER"
    res_dto = await service.update_status(db, id, target_status, current_admin.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy execution resumed successfully",
        data=res_dto,
        requestId=request_id
    )

@router.post("/admin/strategies/{id}/stop", response_model=ApiResponse[StrategyResponse])
async def stop_strategy(
    request: Request,
    id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    res_dto = await service.update_status(db, id, "STOPPED", current_admin.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy execution stopped successfully",
        data=res_dto,
        requestId=request_id
    )

# =========================================================================
# 3. TRADER PORTFOLIO STRATEGY ENDPOINTS
# =========================================================================

@router.get("/strategies/my", response_model=ApiResponse[List[StrategyResponse]])
async def get_my_strategies(
    request: Request,
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Paginated user strategies query
    stmt = select(Strategy).where(Strategy.user_id == current_user.id).order_by(Strategy.id.desc()).offset(page * size).limit(size)
    res = await db.execute(stmt)
    strategies = res.scalars().all()

    dtos = []
    for s in strategies:
        dtos.append(await service.build_strategy_response(db, s))

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="My strategies retrieved successfully",
        data=dtos,
        requestId=request_id
    )

@router.get("/strategies/{id}", response_model=ApiResponse[StrategyResponse])
async def get_my_strategy_by_id(
    request: Request,
    id: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await service.get_strategy_details(db, id, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy details retrieved",
        data=res,
        requestId=request_id
    )

# =========================================================================
# 4. ADMIN BATCH & USER TRACING ENDPOINTS
# =========================================================================

from app.execution.schemas import StrategyExecutionBatchResponse, StrategyUserExecutionTraceResponse, ExecutionFailureSummaryResponse, StrategyExecutionTraceEventResponse
from app.execution import service as exec_service
from app.execution.models import StrategyExecutionBatch, StrategyUserExecutionTrace, StrategyExecutionTraceEvent

@router.get("/admin/strategies/{id}/execution-batches", response_model=ApiResponse[List[StrategyExecutionBatchResponse]])
async def get_strategy_batches(
    request: Request,
    id: int,
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1),
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(StrategyExecutionBatch).where(StrategyExecutionBatch.strategy_id == id).order_by(StrategyExecutionBatch.id.desc()).offset(page * size).limit(size)
    res = await db.execute(stmt)
    batches = res.scalars().all()
    
    dtos = []
    for b in batches:
        dtos.append(StrategyExecutionBatchResponse(
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
            failed_users=b.failed_users, # wait, matches schema
            failedUsers=b.failed_users,
            notExecutedUsers=b.not_executed_users,
            status=b.status,
            createdAt=b.createdAt or b.created_at, # handles compat
            completedAt=b.completed_at
        ))
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Execution batches retrieved",
        data=dtos,
        requestId=request_id
    )

@router.get("/admin/execution-batches/{batchId}/summary", response_model=ApiResponse[StrategyExecutionBatchResponse])
async def get_batch_summary(
    request: Request,
    batchId: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(StrategyExecutionBatch).where(StrategyExecutionBatch.id == batchId)
    res = await db.execute(stmt)
    b = res.scalar_one_or_none()
    if not b:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError(f"Batch not found: {batchId}")
        
    dto = StrategyExecutionBatchResponse(
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
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Batch summary retrieved", data=dto, requestId=request_id)

@router.get("/admin/execution-batches/{batchId}/users", response_model=ApiResponse[List[StrategyUserExecutionTraceResponse]])
async def get_batch_users(
    request: Request,
    batchId: int,
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1),
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(StrategyUserExecutionTrace).where(StrategyUserExecutionTrace.execution_batch_id == batchId).order_by(StrategyUserExecutionTrace.id.asc()).offset(page * size).limit(size)
    res = await db.execute(stmt)
    traces = res.scalars().all()
    
    dtos = []
    for t in traces:
        dtos.append(StrategyUserExecutionTraceResponse(
            userId=t.user_id,
            status=t.status,
            currentStep=t.current_step,
            failureCode=t.failure_code,
            failureReason=t.failure_reason,
            executionId=None # resolved on trace details
        ))
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="User execution traces retrieved", data=dtos, requestId=request_id)

@router.get("/admin/execution-batches/{batchId}/users/{userId}", response_model=ApiResponse[StrategyUserExecutionTraceResponse])
async def get_user_trace_detail(
    request: Request,
    batchId: int,
    userId: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(StrategyUserExecutionTrace).where(
        StrategyUserExecutionTrace.execution_batch_id == batchId,
        StrategyUserExecutionTrace.user_id == userId
    )
    res = await db.execute(stmt)
    t = res.scalar_one_or_none()
    if not t:
        from app.core.exceptions import ResourceNotFoundError
        raise ResourceNotFoundError("Trace not found")

    stmt_events = select(StrategyExecutionTraceEvent).where(StrategyExecutionTraceEvent.execution_trace_id == t.id).order_by(StrategyExecutionTraceEvent.created_at.asc())
    res_events = await db.execute(stmt_events)
    events = res_events.scalars().all()

    timeline = [StrategyExecutionTraceEventResponse(
        step=e.step,
        status=e.status,
        message=e.message,
        errorCode=e.error_code,
        timestamp=e.created_at
    ) for e in events]

    dto = StrategyUserExecutionTraceResponse(
        userId=t.user_id,
        status=t.status,
        currentStep=t.current_step,
        failureCode=t.failure_code,
        failureReason=t.failure_reason,
        executionId=None,
        timeline=timeline
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="User trace timeline retrieved", data=dto, requestId=request_id)
    

@router.get("/admin/execution-batches/{batchId}/failure-summary", response_model=ApiResponse[ExecutionFailureSummaryResponse])
async def get_failure_summary(
    request: Request,
    batchId: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(StrategyUserExecutionTrace).where(
        StrategyUserExecutionTrace.execution_batch_id == batchId,
        StrategyUserExecutionTrace.failure_code.isnot(None)
    )
    res = await db.execute(stmt)
    traces = res.scalars().all()
    
    counts = {}
    for t in traces:
        counts[t.failure_code] = counts.get(t.failure_code, 0) + 1
        
    reasons = [FailureReasonCount(code=k, count=v) for k, v in counts.items()]
    dto = ExecutionFailureSummaryResponse(totalFailures=len(traces), reasons=reasons)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Failure summary breakdown retrieved", data=dto, requestId=request_id)

@router.post("/admin/strategies/{id}/exit-all", response_model=ApiResponse[None])
async def exit_all(
    request: Request,
    id: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    await exec_service.exit_all_positions(db, id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Square off request submitted for all strategy positions", data=None, requestId=request_id)

