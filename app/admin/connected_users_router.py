"""
Admin: Connected Broker Users Router
Provides endpoints for viewing all users and their broker connection status.
"""
import uuid
from typing import List, Optional
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.core.schemas import ApiResponse
from app.brokers.models import BrokerAccount, UserDailyBrokerConnection
from app.users.models import User
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/admin/broker-connections", tags=["Admin: Connected Broker Users"])


class ConnectedBrokerUserResponse(BaseModel):
    userId: int = Field(..., alias="userId")
    userName: str = Field(..., alias="userName")
    userEmail: str = Field(..., alias="userEmail")
    brokerCode: str = Field(..., alias="brokerCode")
    clientId: str = Field(..., alias="clientId")
    accountName: Optional[str] = Field(None, alias="accountName")
    status: str  # ACTIVE, EXPIRED, DISABLED
    connectionDate: Optional[date] = Field(None, alias="connectionDate")
    tokenExpiry: Optional[datetime] = Field(None, alias="tokenExpiry")
    lastSyncAt: Optional[datetime] = Field(None, alias="lastSyncAt")
    isConnectedToday: bool = Field(False, alias="isConnectedToday")

    model_config = {"populate_by_name": True}


class BrokerConnectionStatsResponse(BaseModel):
    totalAccounts: int = Field(..., alias="totalAccounts")
    activeAccounts: int = Field(..., alias="activeAccounts")
    connectedToday: int = Field(..., alias="connectedToday")
    expiredTokens: int = Field(..., alias="expiredTokens")
    disabledAccounts: int = Field(..., alias="disabledAccounts")

    model_config = {"populate_by_name": True}


@router.get(
    "/stats",
    response_model=ApiResponse[BrokerConnectionStatsResponse],
    summary="Get broker connection statistics summary"
)
async def get_broker_connection_stats(
    request: Request,
    current_admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """Returns summary stats: total connected users, active today, expired tokens."""
    today = date.today()

    total_stmt = select(func.count(BrokerAccount.id))
    active_stmt = select(func.count(BrokerAccount.id)).where(BrokerAccount.status == "ACTIVE")
    expired_stmt = select(func.count(BrokerAccount.id)).where(BrokerAccount.status == "EXPIRED")
    disabled_stmt = select(func.count(BrokerAccount.id)).where(BrokerAccount.status == "DISABLED")
    today_stmt = select(func.count(UserDailyBrokerConnection.id)).where(
        UserDailyBrokerConnection.connection_date == today,
        UserDailyBrokerConnection.status == "ACTIVE"
    )

    total = (await db.execute(total_stmt)).scalar() or 0
    active = (await db.execute(active_stmt)).scalar() or 0
    expired = (await db.execute(expired_stmt)).scalar() or 0
    disabled = (await db.execute(disabled_stmt)).scalar() or 0
    connected_today = (await db.execute(today_stmt)).scalar() or 0

    data = BrokerConnectionStatsResponse(
        totalAccounts=total,
        activeAccounts=active,
        connectedToday=connected_today,
        expiredTokens=expired,
        disabledAccounts=disabled,
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Stats retrieved", data=data, requestId=request_id)


@router.get(
    "",
    response_model=ApiResponse[List[ConnectedBrokerUserResponse]],
    summary="Get all users with their broker connection details"
)
async def list_connected_broker_users(
    request: Request,
    broker_code: Optional[str] = Query(None, alias="brokerCode"),
    status: Optional[str] = Query(None, description="ACTIVE, EXPIRED, DISABLED"),
    search: Optional[str] = Query(None, description="Search by user email or client ID"),
    page: int = Query(0, ge=0),
    size: int = Query(50, ge=1, le=200),
    current_admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all broker accounts linked to users with detailed status information.
    Used to power the 'Connected Broker Users' admin table.
    """
    today = date.today()

    # Fetch today's connections for quick lookup
    today_conn_stmt = select(UserDailyBrokerConnection.user_id).where(
        UserDailyBrokerConnection.connection_date == today,
        UserDailyBrokerConnection.status == "ACTIVE"
    )
    today_res = await db.execute(today_conn_stmt)
    connected_today_ids = set(today_res.scalars().all())

    # Build main query: join BrokerAccount -> User
    query = (
        select(BrokerAccount)
        .options(selectinload(BrokerAccount.user))
    )

    if broker_code:
        query = query.where(BrokerAccount.broker_code == broker_code.upper())
    if status:
        query = query.where(BrokerAccount.status == status.upper())
    if search:
        query = query.join(User, User.id == BrokerAccount.user_id).where(
            User.email.ilike(f"%{search}%") |
            BrokerAccount.account_client_id.ilike(f"%{search}%")
        )

    query = query.order_by(BrokerAccount.updated_at.desc()).offset(page * size).limit(size)
    res = await db.execute(query)
    accounts = list(res.scalars().all())

    data = []
    for acct in accounts:
        u = acct.user
        first = u.first_name or "" if u else ""
        last = u.last_name or "" if u else ""
        user_name = f"{first} {last}".strip() or f"User #{acct.user_id}"
        user_email = u.email if u else f"user_{acct.user_id}@zenalgo.com"

        data.append(ConnectedBrokerUserResponse(
            userId=acct.user_id,
            userName=user_name,
            userEmail=user_email,
            brokerCode=acct.broker_code,
            clientId=acct.account_client_id,
            accountName=acct.account_name,
            status=acct.status,
            connectionDate=acct.connection_date,
            tokenExpiry=acct.expiry_time,
            lastSyncAt=acct.last_sync_at,
            isConnectedToday=acct.user_id in connected_today_ids,
        ))

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Connected broker users retrieved",
        data=data,
        requestId=request_id
    )
