import uuid
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_trader
from app.core.responses import ApiResponse
from app.users.models import User
from app.partners.schemas import (
    PartnerDashboardStatsResponse,
    ReferredClientResponse,
    CommissionTransactionResponse,
    PayoutRequest,
    PayoutResponse,
    PartnerMarketingLinksResponse,
)
from app.partners.service import PartnerService

router = APIRouter(prefix="/partner", tags=["Partners & Affiliates"])

@router.get("/dashboard", response_model=ApiResponse[PartnerDashboardStatsResponse])
async def get_partner_dashboard(
    request: Request,
    current_user: User = Depends(require_trader),
    db: AsyncSession = Depends(get_db)
):
    data = await PartnerService.get_dashboard_stats(db, current_user)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Partner dashboard metrics loaded",
        data=data,
        requestId=request_id
    )

@router.get("/referrals", response_model=ApiResponse[List[ReferredClientResponse]])
async def list_referred_clients(
    request: Request,
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    current_user: User = Depends(require_trader),
    db: AsyncSession = Depends(get_db)
):
    data = await PartnerService.list_referred_clients(db, current_user, page, size, search)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Referred clients retrieved successfully",
        data=data,
        requestId=request_id
    )

@router.get("/commissions", response_model=ApiResponse[List[CommissionTransactionResponse]])
async def list_commissions(
    request: Request,
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_trader),
    db: AsyncSession = Depends(get_db)
):
    data = await PartnerService.list_commissions(db, current_user, page, size)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Commission transactions loaded",
        data=data,
        requestId=request_id
    )

@router.post("/payouts/request", response_model=ApiResponse[PayoutResponse])
async def request_payout(
    request: Request,
    req_body: PayoutRequest,
    current_user: User = Depends(require_trader),
    db: AsyncSession = Depends(get_db)
):
    data = await PartnerService.request_payout(db, current_user, req_body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Payout request submitted successfully. Processing within 24 hours.",
        data=data,
        requestId=request_id
    )

@router.get("/payouts", response_model=ApiResponse[List[PayoutResponse]])
async def list_payouts(
    request: Request,
    current_user: User = Depends(require_trader),
    db: AsyncSession = Depends(get_db)
):
    data = await PartnerService.list_payouts(db, current_user)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Payout history retrieved",
        data=data,
        requestId=request_id
    )

@router.get("/links", response_model=ApiResponse[PartnerMarketingLinksResponse])
async def get_marketing_links(
    request: Request,
    current_user: User = Depends(require_trader)
):
    data = PartnerService.get_marketing_links(current_user)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Marketing links generated",
        data=data,
        requestId=request_id
    )
