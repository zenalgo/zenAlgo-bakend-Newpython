from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.database import get_db
from app.core.schemas import ApiResponse
from app.auth.schemas import RegisterRequest, LoginRequest, TokenRefreshRequest, AuthResponse
from app.users.schemas import UserDto
from app.auth import service

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

@router.post("/register", response_model=ApiResponse[UserDto], status_code=status.HTTP_201_CREATED)
async def register(request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await service.register_user(db, body)
    user_dto = UserDto.model_validate(user)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="User registered successfully",
        data=user_dto,
        requestId=request_id
    )

@router.post("/login", response_model=ApiResponse[AuthResponse])
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    auth_data = await service.login_user(db, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Login successful",
        data=auth_data,
        requestId=request_id
    )

@router.post("/admin/login", response_model=ApiResponse[AuthResponse])
async def admin_login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    auth_data = await service.login_admin(db, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Admin login successful",
        data=auth_data,
        requestId=request_id
    )

@router.post("/refresh", response_model=ApiResponse[AuthResponse])
async def refresh(request: Request, body: TokenRefreshRequest, db: AsyncSession = Depends(get_db)):
    auth_data = await service.refresh_session_token(db, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Token refreshed successfully",
        data=auth_data,
        requestId=request_id
    )
