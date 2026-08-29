from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Dict, Any

from app.brokers.models import BrokerAccount, DhanBrokerSession
from app.brokers.schemas import GenerateTokenRequest, SetIpRequest, DhanProfileResponse, BrokerAccountResponse
from app.brokers.base.schemas import OrderRequest, OrderResult, BrokerFormConfig, BrokerMetadata
from app.brokers.registry import broker_registry
from app.brokers.dhan.adapter import DhanAdapter
from app.brokers.mock.adapter import MockBrokerAdapter
from app.core.exceptions import ResourceNotFoundError, ValidationError, BrokerError

# Auto-register supported broker adapters
broker_registry.register(DhanAdapter())
broker_registry.register(MockBrokerAdapter())


def list_supported_brokers() -> List[BrokerMetadata]:
    """Returns list of supported broker metadata."""
    return broker_registry.list_supported_brokers()


def get_broker_config(broker_code: str) -> BrokerFormConfig:
    """Retrieves form configuration metadata for given broker code."""
    adapter = broker_registry.get(broker_code)
    return adapter.get_form_config()


async def get_user_account(db: AsyncSession, user_id: int, broker_code: Optional[str] = None) -> BrokerAccount:
    """Resolves active broker account for a user."""
    stmt = select(BrokerAccount).where(BrokerAccount.user_id == user_id)
    if broker_code:
        stmt = stmt.where(BrokerAccount.broker_code == broker_code.upper())
    
    res = await db.execute(stmt)
    accounts = res.scalars().all()
    if not accounts:
        raise ResourceNotFoundError("No connected broker account found")
    
    # Return first active account, or first account if none marked active
    active = next((acc for acc in accounts if acc.status.upper() == "ACTIVE"), accounts[0])
    return active


async def get_user_accounts(db: AsyncSession, user_id: int) -> List[BrokerAccount]:
    """Retrieves all connected broker accounts for a user."""
    stmt = select(BrokerAccount).where(BrokerAccount.user_id == user_id)
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def connect_broker(
    db: AsyncSession,
    user_id: int,
    broker_code: str,
    credentials: Dict[str, Any]
) -> BrokerAccount:
    """Validates credentials and connects user account to a broker."""
    code = broker_code.upper()
    adapter = broker_registry.get(code)

    # 1. Validate credentials via broker adapter
    val_res = await adapter.validate_credentials(credentials)
    if not val_res.is_valid:
        raise ValidationError(val_res.message or f"Failed to authenticate with {adapter.name}")

    account_client_id = credentials.get("clientId") or credentials.get("client_id") or f"{code}_{user_id}"
    now = datetime.now(timezone.utc)
    expiry = val_res.expiry_time or (now + timedelta(days=30))

    # 2. Check if existing session exists for (user_id, broker_code)
    stmt = select(BrokerAccount).where(
        BrokerAccount.user_id == user_id,
        BrokerAccount.broker_code == code
    )
    res = await db.execute(stmt)
    account = res.scalar_one_or_none()

    if account:
        account.account_client_id = account_client_id
        account.set_credentials(credentials)
        account.expiry_time = expiry
        account.status = val_res.status or "ACTIVE"
        account.connection_date = now.date()
        account.updated_at = now
    else:
        account = BrokerAccount(
            user_id=user_id,
            broker_code=code,
            account_client_id=account_client_id,
            auth_type=adapter.get_form_config().auth_type,
            expiry_time=expiry,
            status=val_res.status or "ACTIVE",
            connection_date=now.date()
        )
        account.set_credentials(credentials)

    db.add(account)
    await db.flush()
    return account


async def create_or_update_session(db: AsyncSession, user_id: int, request: GenerateTokenRequest) -> BrokerAccount:
    """Legacy helper for Dhan token setup."""
    credentials = {
        "clientId": request.clientId,
        "accessToken": request.accessToken,
        "expiryTime": request.expiryTime
    }
    return await connect_broker(db, user_id, "DHAN", credentials)


async def disconnect_account(db: AsyncSession, user_id: int, account_id: Optional[int] = None, broker_code: Optional[str] = None) -> None:
    """Disconnects broker account."""
    if account_id:
        stmt = select(BrokerAccount).where(BrokerAccount.id == account_id, BrokerAccount.user_id == user_id)
        res = await db.execute(stmt)
        account = res.scalar_one_or_none()
    else:
        account = await get_user_account(db, user_id, broker_code)
    
    if account:
        await db.delete(account)
        await db.flush()


async def delete_session(db: AsyncSession, user_id: int) -> None:
    """Legacy helper for session disconnect."""
    await disconnect_account(db, user_id, broker_code="DHAN")


async def set_ips(db: AsyncSession, user_id: int, request: SetIpRequest) -> BrokerAccount:
    """Configures primary/secondary routing IPs on active user session."""
    account = await get_user_account(db, user_id)
    account.primary_ip = request.primaryIp
    account.secondary_ip = request.secondaryIp
    db.add(account)
    await db.flush()
    return account


async def get_session(db: AsyncSession, user_id: int) -> BrokerAccount:
    """Legacy helper resolving active session."""
    return await get_user_account(db, user_id)


async def get_profile(db: AsyncSession, user_id: int, broker_code: Optional[str] = None) -> DhanProfileResponse:
    """Retrieves user profile info from broker adapter."""
    account = await get_user_account(db, user_id, broker_code)
    adapter = broker_registry.get(account.broker_code)
    profile = await adapter.get_profile(account, account.credentials)
    
    return DhanProfileResponse(
        clientId=profile.client_id,
        name=profile.name,
        ucc=profile.ucc or "",
        email=profile.email or "",
        mobileNo=profile.mobile_no or ""
    )


async def place_dhan_order(
    email: str,
    token: str,
    client_id: str,
    trading_symbol: str,
    security_id: str,
    transaction_type: str,
    quantity: int
) -> dict:
    """Legacy function delegating order placement to DhanAdapter via broker registry."""
    adapter = broker_registry.get("DHAN")
    credentials = {"clientId": client_id, "accessToken": token}
    order_req = OrderRequest(
        trading_symbol=trading_symbol,
        security_id=security_id,
        transaction_type=transaction_type,
        quantity=quantity
    )
    result = await adapter.place_order(None, credentials, order_req)
    return result.raw_response or {"orderId": result.broker_order_id, "orderStatus": result.order_status}
