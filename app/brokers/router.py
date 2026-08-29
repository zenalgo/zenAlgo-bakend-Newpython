from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from typing import List

from app.core.database import get_db
from app.core.schemas import ApiResponse
from app.core.dependencies import get_current_user
from app.brokers.base.schemas import BrokerMetadata, BrokerFormConfig
from app.brokers.schemas import (
    ConnectBrokerRequest,
    BrokerAccountResponse,
    GenerateTokenRequest,
    SetIpRequest,
    DhanProfileResponse,
    BrokerSessionResponse
)
from app.brokers import service

router = APIRouter()

# --- GENERIC BROKER MANAGEMENT ENDPOINTS (/api/v1/brokers) ---

generic_router = APIRouter(prefix="/api/v1/brokers", tags=["Broker Management"])

@generic_router.get("", response_model=ApiResponse[List[BrokerMetadata]])
async def list_brokers(request: Request):
    """Returns list of all supported broker integrations."""
    brokers = service.list_supported_brokers()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Supported brokers retrieved successfully", data=brokers, requestId=request_id)

@generic_router.get("/{broker_code}/config", response_model=ApiResponse[BrokerFormConfig])
async def get_broker_form_config(broker_code: str, request: Request):
    """Retrieves dynamic connection form configuration for specified broker."""
    form_config = service.get_broker_config(broker_code)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message=f"Form configuration for {broker_code.upper()} retrieved", data=form_config, requestId=request_id)

@generic_router.post("/{broker_code}/connect", response_model=ApiResponse[BrokerAccountResponse])
async def connect_broker_account(
    broker_code: str,
    body: ConnectBrokerRequest,
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Connects user account to specified broker using provided credentials."""
    account = await service.connect_broker(db, current_user.id, broker_code, body.credentials)
    dto = BrokerAccountResponse(
        id=account.id,
        userId=account.user_id,
        brokerCode=account.broker_code,
        brokerName=account.broker_code,
        accountClientId=account.account_client_id,
        status=account.status,
        connectionDate=account.connection_date,
        expiryTime=account.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message=f"Successfully connected {account.broker_code} account", data=dto, requestId=request_id)

@generic_router.get("/accounts", response_model=ApiResponse[List[BrokerAccountResponse]])
async def list_user_accounts(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists all connected broker accounts for current user."""
    accounts = await service.get_user_accounts(db, current_user.id)
    data = [
        BrokerAccountResponse(
            id=acc.id,
            userId=acc.user_id,
            brokerCode=acc.broker_code,
            brokerName=acc.broker_code,
            accountClientId=acc.account_client_id,
            status=acc.status,
            connectionDate=acc.connection_date,
            expiryTime=acc.expiry_time
        )
        for acc in accounts
    ]
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Connected broker accounts retrieved", data=data, requestId=request_id)

@generic_router.delete("/accounts/{account_id}", response_model=ApiResponse[str])
async def disconnect_user_account(
    account_id: int,
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Disconnects specified broker account."""
    await service.disconnect_account(db, current_user.id, account_id=account_id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Broker account disconnected", data="DISCONNECTED", requestId=request_id)


# --- LEGACY DHAN HQ ENDPOINTS (/api/v1/dhan) FOR BACKWARD COMPATIBILITY ---

dhan_router = APIRouter(prefix="/api/v1/dhan", tags=["Dhan HQ Integration"])

@dhan_router.post("/auth/individual/generate-token", response_model=ApiResponse[BrokerSessionResponse])
async def generate_token(
    request: Request,
    body: GenerateTokenRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.create_or_update_session(db, current_user.id, body)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.account_client_id,
        brokerName=session.broker_code,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Session token registered successfully", data=dto, requestId=request_id)

@dhan_router.post("/auth/individual/renew-token", response_model=ApiResponse[BrokerSessionResponse])
async def renew_token(
    request: Request,
    body: GenerateTokenRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.create_or_update_session(db, current_user.id, body)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.account_client_id,
        brokerName=session.broker_code,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Session token renewed successfully", data=dto, requestId=request_id)

@dhan_router.post("/auth/connect-token", response_model=ApiResponse[BrokerSessionResponse])
async def connect_token(
    request: Request,
    body: GenerateTokenRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.create_or_update_session(db, current_user.id, body)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.account_client_id,
        brokerName=session.broker_code,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Connected token successfully", data=dto, requestId=request_id)

@dhan_router.get("/auth/session/me", response_model=ApiResponse[BrokerSessionResponse])
async def get_session_info(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.get_session(db, current_user.id)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.account_client_id,
        brokerName=session.broker_code,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Session details retrieved", data=dto, requestId=request_id)

@dhan_router.delete("/auth/session", response_model=ApiResponse[str])
async def disconnect_session(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await service.delete_session(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Disconnected session", data="DISCONNECTED", requestId=request_id)

@dhan_router.post("/ip/set", response_model=ApiResponse[BrokerSessionResponse])
async def set_ip(
    request: Request,
    body: SetIpRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.set_ips(db, current_user.id, body)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.account_client_id,
        brokerName=session.broker_code,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="IP configured successfully", data=dto, requestId=request_id)

@dhan_router.put("/ip/modify", response_model=ApiResponse[BrokerSessionResponse])
async def modify_ip(
    request: Request,
    body: SetIpRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    session = await service.set_ips(db, current_user.id, body)
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.account_client_id,
        brokerName=session.broker_code,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="IP modified successfully", data=dto, requestId=request_id)

@dhan_router.get("/ip", response_model=ApiResponse[dict])
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

@dhan_router.get("/profile", response_model=ApiResponse[DhanProfileResponse])
async def get_profile(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    profile = await service.get_profile(db, current_user.id, broker_code="DHAN")
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan profile retrieved successfully", data=profile, requestId=request_id)


# Include both sub-routers into main router
router.include_router(generic_router)
router.include_router(dhan_router)
