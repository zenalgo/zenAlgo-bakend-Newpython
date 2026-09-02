from fastapi import APIRouter, Depends, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import pytz
from datetime import datetime, date
from typing import List, Optional

from app.core.database import get_db
from app.core.schemas import ApiResponse
from app.core.dependencies import get_current_user, require_admin, require_permission
from app.subscriptions.schemas import (
    PlanRequest, PlanResponse, PlanSummary, SubscriptionResponse,
    UsageResponse, EligibilityResult, SubscriptionRequest, UpgradeRequest,
    DowngradeRequest, CancelRequest, SubscribeResponse, AdminSubscriptionResponse,
    AdminPaymentMethodRequest, AdminPaymentMethodResponse, PlanPurchaseRequest,
    PendingSubscriptionRequestResponse, SubscriptionApprovalActionRequest,
    AdminPlanWalletLedgerResponse
)
from app.subscriptions import service_plan, service_eligibility, service_billing
from app.subscriptions.service_manual_payments import ManualPaymentService
from app.subscriptions.models import Subscription, Plan, UserDailyStrategyUsage

# Router declarations
trader_router = APIRouter(prefix="/api/v1/subscriptions", tags=["Trader Subscriptions"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["Admin Plans Management"])

# --- TRADER SUBSCRIPTION ENDPOINTS ---

@trader_router.get("/plans", response_model=ApiResponse[List[PlanResponse]])
async def list_public_plans(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    plans = await service_plan.get_all_plans(
        db, page=0, size=50, is_active=True
    )
    dtos = [PlanResponse.model_validate(p) for p in plans]
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Retrieved available subscription plans",
        data=dtos,
        requestId=request_id
    )

@trader_router.get("/me", response_model=ApiResponse[SubscriptionResponse])
async def get_my_subscription(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy.future import select
    stmt = select(Subscription).where(
        Subscription.user_id == current_user.id,
        Subscription.status == "ACTIVE"
    )
    res = await db.execute(stmt)
    sub = res.scalar_one_or_none()
    
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    if not sub:
        return ApiResponse(
            success=False,
            code="NO_ACTIVE_SUBSCRIPTION",
            message="No active subscription found for user.",
            data=None,
            requestId=request_id
        )

    stmt_plan = select(Plan).where(Plan.id == sub.plan_id)
    res_plan = await db.execute(stmt_plan)
    plan = res_plan.scalar_one()

    # Calculate remaining days
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    # Make period end timezone aware for subtraction
    end_date = sub.current_period_end.astimezone(pytz.timezone("Asia/Kolkata"))
    days_remaining = max(0, (end_date - now).days)

    sub_dto = SubscriptionResponse(
        subscriptionId=sub.id,
        plan=PlanSummary(id=plan.id, code=plan.code, name=plan.name),
        status=sub.status,
        startAt=sub.start_at,
        currentPeriodStart=sub.current_period_start,
        currentPeriodEnd=sub.current_period_end,
        autoRenew=sub.auto_renew,
        daysRemaining=days_remaining
    )

    return ApiResponse(
        success=True,
        message="Active subscription retrieved successfully",
        data=sub_dto,
        requestId=request_id
    )

@trader_router.get("/me/usage", response_model=ApiResponse[UsageResponse])
async def get_my_usage(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy.future import select
    stmt_sub = select(Subscription).where(
        Subscription.user_id == current_user.id,
        Subscription.status == "ACTIVE"
    )
    res_sub = await db.execute(stmt_sub)
    active_sub = res_sub.scalar_one_or_none()
    
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    if not active_sub:
        return ApiResponse(
            success=False,
            code="NO_ACTIVE_SUBSCRIPTION",
            message="No active subscription found",
            requestId=request_id
        )

    stmt_plan = select(Plan).where(Plan.id == active_sub.plan_id)
    res_plan = await db.execute(stmt_plan)
    plan = res_plan.scalar_one()

    today = datetime.now(pytz.timezone("Asia/Kolkata")).date()
    
    stmt_usage = select(UserDailyStrategyUsage).where(
        UserDailyStrategyUsage.user_id == current_user.id,
        UserDailyStrategyUsage.trading_date == today
    )
    res_usage = await db.execute(stmt_usage)
    usage = res_usage.scalar_one_or_none()
    used_today = usage.strategy_execution_count if usage else 0
    limit = plan.max_strategy_executions_per_day if plan.max_strategy_executions_per_day is not None else 999999

    usage_dto = UsageResponse(
        plan=plan.name,
        dailyStrategyLimit=limit,
        usedToday=used_today,
        remainingToday=max(0, limit - used_today),
        tradingDate=today
    )

    return ApiResponse(
        success=True,
        message="Usage stats retrieved successfully",
        data=usage_dto,
        requestId=request_id
    )

@trader_router.get("/me/strategy-eligibility/{strategyId}", response_model=ApiResponse[EligibilityResult])
async def check_eligibility(
    request: Request,
    strategyId: int,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await service_eligibility.check_strategy_eligibility(db, current_user.id, strategyId)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=result.eligible,
        code=result.reason if not result.eligible else None,
        message="Eligibility verification completed" if result.eligible else f"Rejection reason: {result.reason}",
        data=result,
        requestId=request_id
    )

@trader_router.post("", response_model=ApiResponse[SubscribeResponse])
async def subscribe_to_plan(
    request: Request,
    body: SubscriptionRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await service_billing.subscribe(db, current_user.id, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Subscription order created in PENDING state",
        data=res,
        requestId=request_id
    )

@trader_router.post("/me/upgrade", response_model=ApiResponse[SubscribeResponse])
async def upgrade(
    request: Request,
    body: UpgradeRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await service_billing.upgrade_subscription(db, current_user.id, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Upgrade initiated successfully",
        data=res,
        requestId=request_id
    )

@trader_router.post("/me/downgrade", response_model=ApiResponse[str])
async def downgrade(
    request: Request,
    body: DowngradeRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await service_billing.downgrade_subscription(db, current_user.id, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Plan downgrade scheduled on current period end date.",
        data="SCHEDULED",
        requestId=request_id
    )

@trader_router.post("/me/cancel", response_model=ApiResponse[str])
async def cancel(
    request: Request,
    body: CancelRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await service_billing.cancel_subscription(db, current_user.id, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Auto-renewal disabled successfully.",
        data="AUTO_RENEW_DISABLED",
        requestId=request_id
    )

@trader_router.post("/me/reactivate", response_model=ApiResponse[str])
async def reactivate(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await service_billing.reactivate_subscription(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Auto-renewal reactivated successfully.",
        data="AUTO_RENEW_ENABLED",
        requestId=request_id
    )


# --- ADMIN PLAN MANAGEMENT ENDPOINTS ---

@admin_router.post("/plans", response_model=ApiResponse[PlanResponse], status_code=status.HTTP_201_CREATED)
async def create_plan(
    request: Request,
    body: PlanRequest,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    plan = await service_plan.create_plan(db, body)
    plan_dto = PlanResponse.model_validate(plan)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Subscription plan successfully created",
        data=plan_dto,
        requestId=request_id
    )

@admin_router.get("/plans", response_model=ApiResponse[List[PlanResponse]])
async def list_plans(
    request: Request,
    page: int = Query(0, ge=0),
    size: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    subscription_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    plans = await service_plan.get_all_plans(
        db, page=page, size=size, search=search, subscription_type=subscription_type, is_active=is_active
    )
    dtos = [PlanResponse.model_validate(p) for p in plans]
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Retrieved plans list",
        data=dtos,
        requestId=request_id
    )

@admin_router.get("/plans/{planId}", response_model=ApiResponse[PlanResponse])
async def get_plan(
    request: Request,
    planId: int,
    db: AsyncSession = Depends(get_db)
):
    plan = await service_plan.get_plan_details(db, planId)
    plan_dto = PlanResponse.model_validate(plan)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Plan details retrieved",
        data=plan_dto,
        requestId=request_id
    )

@admin_router.put("/plans/{planId}", response_model=ApiResponse[PlanResponse])
async def update_plan(
    request: Request,
    planId: int,
    body: PlanRequest,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    plan = await service_plan.update_plan(db, planId, body)
    plan_dto = PlanResponse.model_validate(plan)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Plan details updated successfully",
        data=plan_dto,
        requestId=request_id
    )

@admin_router.delete("/plans/{planId}", response_model=ApiResponse[str])
async def delete_plan(
    request: Request,
    planId: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    await service_plan.delete_plan(db, planId)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Plan deleted successfully",
        data="DELETED",
        requestId=request_id
    )

@admin_router.put("/plans/{planId}/status", response_model=ApiResponse[PlanResponse])
async def update_plan_status(
    request: Request,
    planId: int,
    body: dict, # expects {"active": bool}
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    active = body.get("active", True)
    plan = await service_plan.set_plan_active_status(db, planId, active)
    plan_dto = PlanResponse.model_validate(plan)
    status_str = "activated" if active else "deactivated"
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"Plan status successfully {status_str}",
        data=plan_dto,
        requestId=request_id
    )

@admin_router.get("/plans/{planId}/strategies", response_model=ApiResponse[List[int]])
async def list_plan_strategies(
    request: Request,
    planId: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    strategies = await service_plan.get_mapped_strategies(db, planId)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Retrieved mapped strategies list",
        data=strategies,
        requestId=request_id
    )

@admin_router.post("/plans/{planId}/strategies/{strategyId}", response_model=ApiResponse[str])
async def map_strategy(
    request: Request,
    planId: int,
    strategyId: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    await service_plan.map_strategy_to_plan(db, planId, strategyId)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy mapped to plan successfully",
        data="MAPPED",
        requestId=request_id
    )

@admin_router.put("/plans/{planId}/strategies/{strategyId}", response_model=ApiResponse[str])
async def update_strategy_map(
    request: Request,
    planId: int,
    strategyId: int,
    body: dict, # expects {"enabled": bool}
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    enabled = body.get("enabled", True)
    await service_plan.update_strategy_mapping(db, planId, strategyId, enabled)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy mapping updated successfully",
        data="UPDATED",
        requestId=request_id
    )

@admin_router.delete("/plans/{planId}/strategies/{strategyId}", response_model=ApiResponse[str])
async def unmap_strategy(
    request: Request,
    planId: int,
    strategyId: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    await service_plan.delete_strategy_mapping(db, planId, strategyId)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Strategy mapping deleted successfully",
        data="UNMAPPED",
        requestId=request_id
    )

# --- CLIENT / TRADER MANUAL UTR PAYMENT ENDPOINTS ---

@trader_router.get("/payment-methods/active", response_model=ApiResponse[List[AdminPaymentMethodResponse]])
async def get_active_payment_methods(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    methods = await ManualPaymentService.list_active_payment_methods(db)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Active payment methods retrieved",
        data=methods,
        requestId=request_id
    )

@trader_router.post("/request-activation", response_model=ApiResponse[PendingSubscriptionRequestResponse])
async def request_plan_activation(
    request: Request,
    body: PlanPurchaseRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res = await ManualPaymentService.request_plan_activation(db, current_user, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Plan purchase request submitted! Pending administrator UTR verification.",
        data=res,
        requestId=request_id
    )

# --- ADMIN PAYMENT METHODS & UTR APPROVAL ENDPOINTS ---

@admin_router.get("/payment-methods", response_model=ApiResponse[List[AdminPaymentMethodResponse]])
async def list_admin_payment_methods(
    request: Request,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    methods = await ManualPaymentService.list_all_payment_methods(db)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Payment methods retrieved",
        data=methods,
        requestId=request_id
    )

@admin_router.post("/payment-methods", response_model=ApiResponse[AdminPaymentMethodResponse], status_code=status.HTTP_201_CREATED)
async def create_admin_payment_method(
    request: Request,
    body: AdminPaymentMethodRequest,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    pm = await ManualPaymentService.create_payment_method(db, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Payment method created successfully",
        data=pm,
        requestId=request_id
    )

@admin_router.put("/payment-methods/{methodId}", response_model=ApiResponse[AdminPaymentMethodResponse])
async def update_admin_payment_method(
    request: Request,
    methodId: int,
    body: AdminPaymentMethodRequest,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    pm = await ManualPaymentService.update_payment_method(db, methodId, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Payment method updated successfully",
        data=pm,
        requestId=request_id
    )

@admin_router.put("/payment-methods/{methodId}/status", response_model=ApiResponse[AdminPaymentMethodResponse])
async def toggle_admin_payment_method_status(
    request: Request,
    methodId: int,
    body: dict, # {"isActive": bool}
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    is_active = body.get("isActive", True)
    pm = await ManualPaymentService.toggle_payment_method_status(db, methodId, is_active)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"Payment method marked as {'active' if is_active else 'inactive'}",
        data=pm,
        requestId=request_id
    )

@admin_router.delete("/payment-methods/{methodId}", response_model=ApiResponse[bool])
async def delete_admin_payment_method(
    request: Request,
    methodId: int,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    await ManualPaymentService.delete_payment_method(db, methodId)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Payment method removed",
        data=True,
        requestId=request_id
    )

@admin_router.get("/subscriptions/pending-requests", response_model=ApiResponse[List[PendingSubscriptionRequestResponse]])
async def list_pending_subscription_requests(
    request: Request,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    pending = await ManualPaymentService.list_pending_subscription_requests(db)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Pending subscription purchase requests retrieved",
        data=pending,
        requestId=request_id
    )

@admin_router.post("/subscriptions/{paymentId}/approve", response_model=ApiResponse[PendingSubscriptionRequestResponse])
async def approve_subscription_request(
    request: Request,
    paymentId: int,
    body: SubscriptionApprovalActionRequest = SubscriptionApprovalActionRequest(),
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    res = await ManualPaymentService.approve_subscription_request(db, paymentId, current_admin, body.adminNotes)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"Plan subscription for User #{res.userId} ({res.userEmail}) approved & activated! Revenue credited to Admin Plan Wallet.",
        data=res,
        requestId=request_id
    )

@admin_router.post("/subscriptions/{paymentId}/reject", response_model=ApiResponse[PendingSubscriptionRequestResponse])
async def reject_subscription_request(
    request: Request,
    paymentId: int,
    body: SubscriptionApprovalActionRequest = SubscriptionApprovalActionRequest(),
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    res = await ManualPaymentService.reject_subscription_request(db, paymentId, current_admin, body.adminNotes)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"Subscription request #{paymentId} rejected.",
        data=res,
        requestId=request_id
    )

@admin_router.get("/plan-wallet/ledger", response_model=ApiResponse[AdminPlanWalletLedgerResponse])
async def get_admin_plan_wallet_ledger(
    request: Request,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    data = await ManualPaymentService.get_admin_plan_wallet_ledger(db)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Admin plan wallet ledger retrieved",
        data=data,
        requestId=request_id
    )
