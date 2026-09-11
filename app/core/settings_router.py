from decimal import Decimal
import uuid
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.schemas import ApiResponse
from app.core.settings_service import SystemSettingsService

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"])

class OrderCapUpdateRequest(BaseModel):
    maxOrderValueCap: Decimal = Field(..., gt=0, description="Max allowed order value in INR")

class OrderCapResponse(BaseModel):
    maxOrderValueCap: Decimal
    currency: str = "INR"

@router.get("/order-cap", response_model=ApiResponse[OrderCapResponse])
async def get_order_cap(
    request: Request,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Returns the current admin-configured max order value safety cap."""
    cap = await SystemSettingsService.get_max_order_value_cap(db)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Current order value safety cap retrieved",
        data=OrderCapResponse(maxOrderValueCap=cap, currency="INR"),
        requestId=request_id
    )

@router.put("/order-cap", response_model=ApiResponse[OrderCapResponse])
@router.post("/order-cap", response_model=ApiResponse[OrderCapResponse])
async def update_order_cap(
    request: Request,
    body: OrderCapUpdateRequest,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Updates the platform-wide max order value safety cap."""
    if body.maxOrderValueCap <= Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Safety cap must be greater than zero."
        )

    updated_cap = await SystemSettingsService.set_max_order_value_cap(
        db=db,
        new_cap=body.maxOrderValueCap,
        updated_by=current_admin.email
    )

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"Order value safety cap successfully updated to ₹{updated_cap:,.2f}",
        data=OrderCapResponse(maxOrderValueCap=updated_cap, currency="INR"),
        requestId=request_id
    )
