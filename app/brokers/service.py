from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, date, timezone, timedelta
import uuid
import httpx
from typing import Optional

from app.brokers.models import DhanBrokerSession
from app.brokers.schemas import GenerateTokenRequest, SetIpRequest, DhanProfileResponse
from app.core.exceptions import ResourceNotFoundError, ValidationError
from app.core.config import settings

SANDBOX_MODE = True # Match config flag

async def place_dhan_order(
    email: str,
    token: str,
    client_id: str,
    trading_symbol: str,
    security_id: str,
    transaction_type: str,
    quantity: int
) -> dict:
    """Places market order to Dhan HQ API or returns mock details in sandbox mode."""
    if SANDBOX_MODE:
        # Mock order success
        return {
            "orderId": f"order_mock_{str(uuid.uuid4())[:8]}",
            "orderStatus": "SUCCESS"
        }
        
    url = f"{settings.DHAN_API_BASE_URL}/orders"
    headers = {
        "access-token": token,
        "client-id": client_id,
        "Content-Type": "application/json"
    }
    payload = {
        "dhanClientId": client_id,
        "transactionType": transaction_type.upper(),
        "exchangeSegment": "NSE_FN",
        "productType": "MIS",
        "orderType": "MARKET",
        "validity": "DAY",
        "securityId": security_id,
        "tradingSymbol": trading_symbol,
        "quantity": quantity,
        "price": 0.0
    }
    
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(url, json=payload, headers=headers, timeout=10.0)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            raise ValidationError(f"Dhan HQ placing order error: {str(e)}")

async def get_session(db: AsyncSession, user_id: int) -> DhanBrokerSession:
    """Resolves active broker session details for a user."""
    stmt = select(DhanBrokerSession).where(DhanBrokerSession.user_id == user_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise ResourceNotFoundError("No connected broker session found")
    return session

async def create_or_update_session(db: AsyncSession, user_id: int, request: GenerateTokenRequest) -> DhanBrokerSession:
    """Creates a new session or updates an existing session with credentials."""
    stmt = select(DhanBrokerSession).where(DhanBrokerSession.user_id == user_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    expiry = request.expiryTime if request.expiryTime else (now + timedelta(days=30))

    if session:
        session.dhan_client_id = request.clientId
        session.access_token = request.accessToken
        session.expiry_time = expiry
        session.status = "ACTIVE"
        session.connection_date = now.date()
        session.updated_at = now
    else:
        session = DhanBrokerSession(
            user_id=user_id,
            dhan_client_id=request.clientId,
            access_token=request.accessToken,
            expiry_time=expiry,
            status="ACTIVE",
            connection_date=now.date(),
            broker_name="DHAN"
        )
    db.add(session)
    await db.flush()
    return session

async def delete_session(db: AsyncSession, user_id: int) -> None:
    """Disconnects session."""
    session = await get_session(db, user_id)
    await db.delete(session)
    await db.flush()

async def set_ips(db: AsyncSession, user_id: int, request: SetIpRequest) -> DhanBrokerSession:
    """Configures primary/secondary routing IPs."""
    session = await get_session(db, user_id)
    session.primary_ip = request.primaryIp
    session.secondary_ip = request.secondaryIp
    db.add(session)
    await db.flush()
    return session

async def get_profile(db: AsyncSession, user_id: int) -> DhanProfileResponse:
    """Retrieves broker user profile info."""
    session = await get_session(db, user_id)
    
    if SANDBOX_MODE:
        return DhanProfileResponse(
            clientId=session.dhan_client_id,
            name="Mocked Dhan Trader",
            ucc="MOCK12345",
            email="mocked_trader@dhan.co",
            mobileNo="9876543210"
        )
        
    url = f"{settings.DHAN_API_BASE_URL}/profile"
    headers = {
        "access-token": session.access_token,
        "client-id": session.dhan_client_id
    }
    
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url, headers=headers, timeout=10.0)
            res.raise_for_status()
            data = res.json()
            # map response fields
            return DhanProfileResponse(
                clientId=session.dhan_client_id,
                name=data.get("name", "Dhan User"),
                ucc=data.get("ucc", ""),
                email=data.get("email", ""),
                mobileNo=data.get("mobile", "")
            )
        except Exception as e:
            raise ValidationError(f"Failed to fetch profile from Dhan HQ: {str(e)}")
