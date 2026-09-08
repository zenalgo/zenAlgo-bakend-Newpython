"""
Admin: Reports Router
Aggregated analytics — execution summaries, daily breakdowns, user P&L.
"""
import uuid
from typing import List, Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_, case
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.schemas import ApiResponse
from app.execution.models import StrategyExecutionBatch, StrategyUserExecutionTrace
from app.strategies.models import Strategy, StrategyExecution, StrategyExecutionLeg
from app.users.models import User
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/admin/reports", tags=["Admin: Reports & Analytics"])


class StrategyExecutionSummaryItem(BaseModel):
    strategyId: int = Field(..., alias="strategyId")
    strategyName: str = Field(..., alias="strategyName")
    totalBatches: int = Field(..., alias="totalBatches")
    totalUsersServed: int = Field(..., alias="totalUsersServed")
    totalSuccessful: int = Field(..., alias="totalSuccessful")
    totalFailed: int = Field(..., alias="totalFailed")
    successRate: float = Field(..., alias="successRate")
    lastExecutedDate: Optional[date] = Field(None, alias="lastExecutedDate")

    model_config = {"populate_by_name": True}


class DailyActivityItem(BaseModel):
    tradingDate: date = Field(..., alias="tradingDate")
    totalBatches: int = Field(..., alias="totalBatches")
    totalUsers: int = Field(..., alias="totalUsers")
    successfulUsers: int = Field(..., alias="successfulUsers")
    failedUsers: int = Field(..., alias="failedUsers")
    successRate: float = Field(..., alias="successRate")

    model_config = {"populate_by_name": True}


class UserPerformanceItem(BaseModel):
    userId: int = Field(..., alias="userId")
    userName: str = Field(..., alias="userName")
    userEmail: str = Field(..., alias="userEmail")
    totalExecutions: int = Field(..., alias="totalExecutions")
    successfulExecutions: int = Field(..., alias="successfulExecutions")
    failedExecutions: int = Field(..., alias="failedExecutions")
    successRate: float = Field(..., alias="successRate")
    totalRealizedPnl: float = Field(..., alias="totalRealizedPnl")

    model_config = {"populate_by_name": True}


class ReportsSummaryResponse(BaseModel):
    totalStrategies: int = Field(..., alias="totalStrategies")
    totalBatchesRun: int = Field(..., alias="totalBatchesRun")
    totalOrdersPlaced: int = Field(..., alias="totalOrdersPlaced")
    overallSuccessRate: float = Field(..., alias="overallSuccessRate")
    activeUsers: int = Field(..., alias="activeUsers")

    model_config = {"populate_by_name": True}


@router.get(
    "/summary",
    response_model=ApiResponse[ReportsSummaryResponse],
    summary="Get overall platform execution summary"
)
async def get_reports_summary(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Look-back window in days"),
    current_admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Returns top-level platform metrics for the reports dashboard."""
    since = date.today() - timedelta(days=days)

    total_strategies = (await db.execute(select(func.count(Strategy.id)))).scalar() or 0
    total_batches = (await db.execute(
        select(func.count(StrategyExecutionBatch.id))
        .where(StrategyExecutionBatch.trading_date >= since)
    )).scalar() or 0

    agg = (await db.execute(
        select(
            func.sum(StrategyExecutionBatch.total_users),
            func.sum(StrategyExecutionBatch.successful_users),
        ).where(StrategyExecutionBatch.trading_date >= since)
    )).first()

    total_orders = int(agg[0] or 0)
    total_success = int(agg[1] or 0)
    success_rate = round((total_success / total_orders * 100) if total_orders else 0, 2)

    active_users = (await db.execute(
        select(func.count(func.distinct(StrategyUserExecutionTrace.user_id)))
        .join(StrategyExecutionBatch, StrategyExecutionBatch.id == StrategyUserExecutionTrace.execution_batch_id)
        .where(StrategyExecutionBatch.trading_date >= since)
    )).scalar() or 0

    data = ReportsSummaryResponse(
        totalStrategies=total_strategies,
        totalBatchesRun=total_batches,
        totalOrdersPlaced=total_orders,
        overallSuccessRate=success_rate,
        activeUsers=active_users,
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Summary retrieved", data=data, requestId=request_id)


@router.get(
    "/execution-summary",
    response_model=ApiResponse[List[StrategyExecutionSummaryItem]],
    summary="Per-strategy execution summary — batches, users served, success rate"
)
async def get_strategy_execution_summary(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    current_admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    since = date.today() - timedelta(days=days)

    stmt = (
        select(
            StrategyExecutionBatch.strategy_id,
            func.count(StrategyExecutionBatch.id).label("total_batches"),
            func.sum(StrategyExecutionBatch.total_users).label("total_users"),
            func.sum(StrategyExecutionBatch.successful_users).label("total_success"),
            func.sum(StrategyExecutionBatch.failed_users).label("total_failed"),
            func.max(StrategyExecutionBatch.trading_date).label("last_date"),
        )
        .where(StrategyExecutionBatch.trading_date >= since)
        .group_by(StrategyExecutionBatch.strategy_id)
        .order_by(func.count(StrategyExecutionBatch.id).desc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    # Fetch strategy names
    strategy_ids = [r[0] for r in rows]
    strat_map = {}
    if strategy_ids:
        s_res = await db.execute(select(Strategy).where(Strategy.id.in_(strategy_ids)))
        for s in s_res.scalars().all():
            strat_map[s.id] = s.name

    data = []
    for r in rows:
        sid, batches, total_u, success_u, failed_u, last_date = r
        total_u = int(total_u or 0)
        success_u = int(success_u or 0)
        failed_u = int(failed_u or 0)
        rate = round((success_u / total_u * 100) if total_u else 0, 2)
        data.append(StrategyExecutionSummaryItem(
            strategyId=sid,
            strategyName=strat_map.get(sid, f"Strategy #{sid}"),
            totalBatches=batches,
            totalUsersServed=total_u,
            totalSuccessful=success_u,
            totalFailed=failed_u,
            successRate=rate,
            lastExecutedDate=last_date,
        ))

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Strategy execution summary", data=data, requestId=request_id)


@router.get(
    "/daily",
    response_model=ApiResponse[List[DailyActivityItem]],
    summary="Day-wise execution activity — success vs failures"
)
async def get_daily_activity(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    current_admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    since = date.today() - timedelta(days=days)

    stmt = (
        select(
            StrategyExecutionBatch.trading_date,
            func.count(StrategyExecutionBatch.id).label("total_batches"),
            func.sum(StrategyExecutionBatch.total_users).label("total_users"),
            func.sum(StrategyExecutionBatch.successful_users).label("success"),
            func.sum(StrategyExecutionBatch.failed_users).label("failed"),
        )
        .where(StrategyExecutionBatch.trading_date >= since)
        .group_by(StrategyExecutionBatch.trading_date)
        .order_by(StrategyExecutionBatch.trading_date.asc())
    )
    res = await db.execute(stmt)
    rows = res.all()

    data = []
    for r in rows:
        d, batches, total_u, success_u, failed_u = r
        total_u = int(total_u or 0)
        success_u = int(success_u or 0)
        failed_u = int(failed_u or 0)
        rate = round((success_u / total_u * 100) if total_u else 0, 2)
        data.append(DailyActivityItem(
            tradingDate=d,
            totalBatches=batches,
            totalUsers=total_u,
            successfulUsers=success_u,
            failedUsers=failed_u,
            successRate=rate,
        ))

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Daily activity retrieved", data=data, requestId=request_id)


@router.get(
    "/user-performance",
    response_model=ApiResponse[List[UserPerformanceItem]],
    summary="Per-user performance — executions, success rate, P&L"
)
async def get_user_performance(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    page: int = Query(0, ge=0),
    size: int = Query(50, ge=1, le=200),
    current_admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    since = date.today() - timedelta(days=days)

    # Per-user trace counts
    trace_stmt = (
        select(
            StrategyUserExecutionTrace.user_id,
            func.count(StrategyUserExecutionTrace.id).label("total"),
            func.sum(
                case((StrategyUserExecutionTrace.status == "EXECUTED", 1), else_=0)
            ).label("success"),
            func.sum(
                case((StrategyUserExecutionTrace.status == "FAILED", 1), else_=0)
            ).label("failed"),
        )
        .join(StrategyExecutionBatch, StrategyExecutionBatch.id == StrategyUserExecutionTrace.execution_batch_id)
        .where(StrategyExecutionBatch.trading_date >= since)
        .group_by(StrategyUserExecutionTrace.user_id)
        .order_by(func.count(StrategyUserExecutionTrace.id).desc())
        .offset(page * size).limit(size)
    )
    trace_res = await db.execute(trace_stmt)
    trace_rows = trace_res.all()

    user_ids = [r[0] for r in trace_rows]
    user_map = {}
    if user_ids:
        u_res = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in u_res.scalars().all():
            user_map[u.id] = u

    # Per-user P&L from StrategyExecution
    pnl_stmt = (
        select(
            StrategyExecution.user_id,
            func.sum(StrategyExecution.realized_pnl).label("total_pnl")
        )
        .where(StrategyExecution.user_id.in_(user_ids))
        .group_by(StrategyExecution.user_id)
    )
    pnl_res = await db.execute(pnl_stmt)
    pnl_map = {r[0]: float(r[1] or 0) for r in pnl_res.all()}

    data = []
    for r in trace_rows:
        uid, total, success, failed = r
        total = int(total or 0)
        success = int(success or 0)
        failed = int(failed or 0)
        rate = round((success / total * 100) if total else 0, 2)
        u = user_map.get(uid)
        first = (u.first_name or "") if u else ""
        last = (u.last_name or "") if u else ""
        name = f"{first} {last}".strip() or f"User #{uid}"
        email = u.email if u else f"user_{uid}@zenalgo.com"
        data.append(UserPerformanceItem(
            userId=uid,
            userName=name,
            userEmail=email,
            totalExecutions=total,
            successfulExecutions=success,
            failedExecutions=failed,
            successRate=rate,
            totalRealizedPnl=pnl_map.get(uid, 0.0),
        ))

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="User performance retrieved", data=data, requestId=request_id)
