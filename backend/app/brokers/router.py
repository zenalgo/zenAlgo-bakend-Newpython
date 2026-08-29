from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.core.database import get_db
from app.core.schemas import ApiResponse
from app.core.dependencies import get_current_user
from app.brokers.schemas import GenerateTokenRequest, SetIpRequest, DhanProfileResponse, BrokerSessionResponse
from app.brokers import service

router = APIRouter(prefix="/api/v1/dhan", tags=["Dhan HQ Integration"])

# --- AUTH & SESSIONS ---

@router.post("/auth/individual/generate-token", response_model=ApiResponse[BrokerSessionResponse])
async def generate_token(
    request: Request,
    body: GenerateTokenRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.create_or_update_session(db, current_user.id, body)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.dhan_client_id,
        brokerName=session.broker_name,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Session token registered successfully", data=dto, requestId=request_id)

@router.post("/auth/individual/renew-token", response_model=ApiResponse[BrokerSessionResponse])
async def renew_token(
    request: Request,
    body: GenerateTokenRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.create_or_update_session(db, current_user.id, body)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.dhan_client_id,
        brokerName=session.broker_name,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Session token renewed successfully", data=dto, requestId=request_id)

@router.post("/auth/connect-token", response_model=ApiResponse[BrokerSessionResponse])
async def connect_token(
    request: Request,
    body: GenerateTokenRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.create_or_update_session(db, current_user.id, body)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.dhan_client_id,
        brokerName=session.broker_name,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Connected token successfully", data=dto, requestId=request_id)

@router.get("/auth/session/me", response_model=ApiResponse[BrokerSessionResponse])
async def get_session_info(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.get_session(db, current_user.id)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.dhan_client_id,
        brokerName=session.broker_name,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Session details retrieved", data=dto, requestId=request_id)

@router.delete("/auth/session", response_model=ApiResponse[str])
async def disconnect_session(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await service.delete_session(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Disconnected session", data="DISCONNECTED", requestId=request_id)


# --- IP MANAGEMENT ---

@router.post("/ip/set", response_model=ApiResponse[BrokerSessionResponse])
async def set_ip(
    request: Request,
    body: SetIpRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.set_ips(db, current_user.id, body)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.dhan_client_id,
        brokerName=session.broker_name,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="IP configured successfully", data=dto, requestId=request_id)

@router.put("/ip/modify", response_model=ApiResponse[BrokerSessionResponse])
async def modify_ip(
    request: Request,
    body: SetIpRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.set_ips(db, current_user.id, body)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.dhan_client_id,
        brokerName=session.broker_name,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="IP modified successfully", data=dto, requestId=request_id)

@router.get("/ip", response_model=ApiResponse[dict])
async def get_ip(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.get_session(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="IP config retrieved",
        data={"primaryIp": session.primary_ip, "secondaryIp": session.secondary_ip},
        requestId=request_id
    )


# --- USER PROFILE ---

@router.get("/profile", response_model=ApiResponse[DhanProfileResponse])
async def get_profile(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    profile = await service.get_profile(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan profile retrieved successfully", data=profile, requestId=request_id)
