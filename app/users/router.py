from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import List

from app.core.database import get_db
from app.core.schemas import ApiResponse
from app.core.dependencies import require_admin, get_current_user
from app.users.schemas import ProvisionUserRequest, UserStatusUpdateRequest, UserDto
from app.users import service

router = APIRouter(prefix="/api/v1/admin/users", tags=["Admin User Management"])

@router.post("", response_model=ApiResponse[UserDto], status_code=status.HTTP_201_CREATED)
async def provision(
    request: Request,
    body: ProvisionUserRequest,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    user = await service.provision_user(db, body, current_admin.email)
    user_dto = UserDto.model_validate(user)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="User account successfully provisioned",
        data=user_dto,
        requestId=request_id
    )

@router.get("", response_model=ApiResponse[List[UserDto]])
async def list_users(
    request: Request,
    page: int = Query(0, ge=0),
    size: int = Query(50, ge=1, le=100),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    users = await service.get_all_users(db, page=page, size=size, search=search, role=role, is_active=is_active)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Successfully retrieved users",
        data=users,
        requestId=request_id
    )

@router.put("/{userId}/status", response_model=ApiResponse[UserDto])
async def update_status(
    request: Request,
    userId: int,
    body: UserStatusUpdateRequest,
    current_admin = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    user = await service.update_user_status(db, userId, body, current_admin.email)
    user_dto = UserDto.model_validate(user)
    action = "activated" if body.active else "deactivated"
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=f"User account successfully {action}",
        data=user_dto,
        requestId=request_id
    )
