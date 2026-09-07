from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from decimal import Decimal
from typing import List, Dict, Any, Optional

from app.core.database import get_db
from app.core.schemas import ApiResponse
from app.core.dependencies import get_current_user
from app.brokers.base.schemas import BrokerMetadata, BrokerFormConfig, BrokerProfile
from app.brokers.schemas import (
    ConnectBrokerRequest,
    BrokerAccountResponse,
    GenerateTokenRequest,
    SetIpRequest,
    DhanProfileResponse,
    BrokerSessionResponse
)
from app.brokers import service
from app.brokers.dhan.auth_service import dhan_auth_service

router = APIRouter()

# --- GENERIC BROKER MANAGEMENT ENDPOINTS (/api/v1/brokers) ---

generic_router = APIRouter(prefix="/api/v1/brokers", tags=["Broker Management"])

@generic_router.get("", response_model=ApiResponse[List[BrokerMetadata]])
async def list_brokers(request: Request):
    """Returns list of all supported broker integrations."""
    brokers = service.list_supported_brokers()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Supported brokers retrieved successfully", data=brokers, requestId=request_id)

@generic_router.get("/active-session", response_model=ApiResponse[dict])
async def check_active_broker_session(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Checks if an unexpired active broker token for user exists for today (Asia/Kolkata)."""
    data = await service.check_active_broker_session(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    msg = "Active broker session found for today" if data.get("connected") else "No active unexpired broker session found"
    return ApiResponse(success=True, message=msg, data=data, requestId=request_id)

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
    """Connects user account to specified broker using provided credentials.
    ENFORCES EXACTLY ONE BROKER PER USER PER CALENDAR DAY (Asia/Kolkata).
    """
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
    return ApiResponse(success=True, message=f"Successfully connected {account.broker_code} account for today", data=dto, requestId=request_id)

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

@generic_router.post("/accounts", response_model=ApiResponse[BrokerAccountResponse])
async def create_broker_account_legacy(
    body: Dict[str, Any],
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Alias for connecting broker account."""
    broker_code = body.get("brokerCode") or body.get("broker_code") or "DHAN"
    credentials = body.get("credentials") or {
        "clientId": body.get("accountClientId") or body.get("clientId"),
        "accessToken": body.get("accessToken")
    }
    account = await service.connect_broker(db, current_user.id, broker_code, credentials)
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


# --- POST-CONNECTION DHAN HQ ENDPOINTS (/api/v1/dhan) FOR BACKWARD COMPATIBILITY ---

dhan_router = APIRouter(prefix="/api/v1/dhan", tags=["Dhan HQ Integration"])

@dhan_router.post("/auth/individual/generate-token", response_model=ApiResponse[BrokerSessionResponse])
async def generate_token(
    request: Request,
    body: Dict[str, Any],
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Connects Dhan account via Client ID, PIN, and TOTP Authenticator Code (or Access Token)."""
    client_id = body.get("dhanClientId") or body.get("clientId")
    pin = body.get("pin")
    totp = body.get("totp")
    access_token = body.get("accessToken")

    if pin and totp and client_id:
        account = await dhan_auth_service.generate_token_totp(
            db=db,
            user_id=current_user.id,
            client_id=client_id,
            pin=pin,
            totp=totp
        )
    elif client_id and access_token:
        account = await dhan_auth_service.connect_direct_token(
            db=db,
            user_id=current_user.id,
            client_id=client_id,
            access_token=access_token
        )
    else:
        req = GenerateTokenRequest(clientId=client_id or "DHAN_USER", accessToken=access_token or "TOKEN")
        account = await service.create_or_update_session(db, current_user.id, req)

    dto = BrokerSessionResponse(
        userId=account.user_id,
        clientId=account.account_client_id,
        brokerName=account.broker_code,
        status=account.status,
        connectionDate=account.connection_date,
        expiryTime=account.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan account linked successfully via TOTP login", data=dto, requestId=request_id)

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

@dhan_router.get("/auth/initiate", response_model=ApiResponse[dict])
@dhan_router.post("/auth/partner/generate-consent", response_model=ApiResponse[dict])
@dhan_router.post("/auth/apikey/generate-consent", response_model=ApiResponse[dict])
async def initiate_dhan_consent(
    request: Request,
    body: Optional[Dict[str, Any]] = None,
    current_user = Depends(get_current_user)
):
    b = body or {}
    data = await dhan_auth_service.generate_partner_consent(
        partner_id=b.get("partnerId") or b.get("partner_id"),
        partner_secret=b.get("partnerSecret") or b.get("partner_secret"),
        redirect_url=b.get("redirectUrl") or b.get("redirect_url")
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message="Redirect user to loginUrl to complete Dhan authentication",
        data=data,
        requestId=request_id
    )

@dhan_router.get("/auth/callback", response_model=ApiResponse[BrokerSessionResponse])
@dhan_router.post("/auth/partner/consume-consent", response_model=ApiResponse[BrokerSessionResponse])
@dhan_router.post("/auth/apikey/consume-consent", response_model=ApiResponse[BrokerSessionResponse])
async def consume_dhan_consent(
    request: Request,
    tokenId: Optional[str] = None,
    consentId: Optional[str] = None,
    body: Optional[Dict[str, Any]] = None,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    b = body or {}
    t_id = tokenId or b.get("tokenId") or b.get("token_id")
    c_id = consentId or b.get("consentId") or b.get("consent_id")
    
    session = await dhan_auth_service.consume_partner_consent(
        db=db,
        user_id=current_user.id,
        token_id=t_id,
        consent_id=c_id
    )
    dto = BrokerSessionResponse(
        userId=session.user_id,
        clientId=session.account_client_id,
        brokerName=session.broker_code,
        status=session.status,
        connectionDate=session.connection_date,
        expiryTime=session.expiry_time
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan account linked successfully via OAuth consent", data=dto, requestId=request_id)

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
    profile: BrokerProfile = await service.get_profile(db, current_user.id, broker_code="DHAN")
    dto = DhanProfileResponse(
        clientId=profile.client_id,
        name=profile.name,
        ucc=profile.ucc or "",
        email=profile.email or "",
        mobileNo=profile.mobile_no or ""
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan profile retrieved successfully", data=dto, requestId=request_id)

# --- POST-CONNECTION PORTFOLIO, FUNDS & MARGIN ENDPOINTS ---

@dhan_router.get("/positions", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_positions(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    positions = await service.get_user_positions(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan positions fetched successfully", data=positions, requestId=request_id)

@dhan_router.post("/positions/convert", response_model=ApiResponse[Dict[str, Any]])
async def convert_position(
    body: Dict[str, Any],
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    res_data = await service.convert_user_position(db, current_user.id, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan position converted successfully", data=res_data, requestId=request_id)

@dhan_router.get("/holdings", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_holdings(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    holdings = await service.get_user_holdings(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan holdings fetched successfully", data=holdings, requestId=request_id)

@dhan_router.get("/funds", response_model=ApiResponse[Dict[str, Any]])
@dhan_router.get("/fundlimit", response_model=ApiResponse[Dict[str, Any]])
async def get_funds(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    funds = await service.get_user_funds(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan fund limits fetched successfully", data=funds, requestId=request_id)

@dhan_router.get("/portfolio-summary", response_model=ApiResponse[Dict[str, Any]])
async def get_portfolio_summary(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    summary = await service.get_user_portfolio_summary(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Unified portfolio summary retrieved successfully", data=summary, requestId=request_id)

@dhan_router.post("/margincalculator", response_model=ApiResponse[Dict[str, Any]])
async def calculate_margin(
    body: Dict[str, Any],
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    margin = await service.calculate_user_margin(db, current_user.id, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan margin calculated successfully", data=margin, requestId=request_id)

@dhan_router.get("/orders", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_orders(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    orders = await service.get_user_orders(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan orders retrieved successfully", data=orders, requestId=request_id)

@dhan_router.post("/orders", response_model=ApiResponse[Dict[str, Any]])
async def place_order(
    body: Dict[str, Any],
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await service.place_user_order(db, current_user.id, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan order placed successfully", data=result, requestId=request_id)

@dhan_router.delete("/orders/{order_id}", response_model=ApiResponse[Dict[str, Any]])
async def cancel_order(
    order_id: str,
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await service.cancel_user_order(db, current_user.id, order_id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan order cancelled successfully", data=result, requestId=request_id)

@dhan_router.get("/trades", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_trades(
    request: Request,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    trades = await service.get_user_trades(db, current_user.id)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(success=True, message="Dhan trades retrieved successfully", data=trades, requestId=request_id)



# --- STOP-LOSS ORDER ENDPOINTS ---

@dhan_router.post(
    "/orders/stop-loss",
    response_model=ApiResponse[Dict[str, Any]],
    summary="Place Stop-Loss or Stop-Loss Market order on Dhan",
    tags=["Dhan HQ Integration"],
)
async def place_stop_loss_order(
    body: Dict[str, Any],
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Places a **STOP_LOSS** or **STOP_LOSS_MARKET** protective order on Dhan
    via `POST https://api.dhan.co/v2/orders`.

    **Required fields:**
    - `securityId` / `security_id` — Dhan scrip-master security ID
    - `tradingSymbol` / `trading_symbol` — e.g. `"BANKNIFTY24500PE"`
    - `transactionType` — `"BUY"` or `"SELL"`
    - `exchangeSegment` — `"NSE_EQ"`, `"NSE_FNO"`, `"BSE_EQ"`, etc.
    - `productType` — `"INTRADAY"`, `"CNC"`, `"MARGIN"`
    - `orderType` — `"STOP_LOSS"` or `"STOP_LOSS_MARKET"`
    - `quantity` — number of shares / lots
    - `triggerPrice` — price at which the SL activates
    - `price` — limit price after trigger (**required for STOP_LOSS**, set `0` for STOP_LOSS_MARKET)

    **Business rules enforced:**
    - For `STOP_LOSS`: `triggerPrice > price` for SELL, `triggerPrice < price` for BUY.
    - For `STOP_LOSS_MARKET`: price is automatically set to `0`.
    """
    result = await service.place_stop_loss_order(db, current_user.id, body)
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=result.get("message", "Stop-loss order placed successfully"),
        data=result,
        requestId=request_id,
    )


@dhan_router.post(
    "/orders/strategy-stop-loss",
    response_model=ApiResponse[Dict[str, Any]],
    summary="Place a stop-loss order from an active strategy execution",
    tags=["Dhan HQ Integration"],
)
async def place_strategy_stop_loss_order(
    body: Dict[str, Any],
    request: Request,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Convenience endpoint: looks up the first FILLED leg of a
    `StrategyExecution` and places a stop-loss order automatically using
    the correct transaction type (reverse of entry side), quantity, and
    exchange segment.

    **Required fields:**
    - `strategyExecutionId` / `strategy_execution_id` — the execution to protect
    - `triggerPrice` — SL activation price

    **Optional fields:**
    - `price` — limit price (only for `orderType=STOP_LOSS`)
    - `orderType` — `"STOP_LOSS_MARKET"` (default) or `"STOP_LOSS"`
    - `quantity` — override filled qty (defaults to execution leg qty)
    """
    execution_id = body.get("strategyExecutionId") or body.get("strategy_execution_id")
    if not execution_id:
        from app.core.exceptions import ValidationError
        raise ValidationError("strategyExecutionId is required")

    trigger_raw = body.get("triggerPrice") or body.get("trigger_price")
    if not trigger_raw:
        from app.core.exceptions import ValidationError
        raise ValidationError("triggerPrice is required")

    trigger_price = Decimal(str(trigger_raw))
    price_raw = body.get("price")
    price = Decimal(str(price_raw)) if price_raw is not None else None
    order_type = str(body.get("orderType") or body.get("order_type", "STOP_LOSS_MARKET")).upper()
    quantity = int(body["quantity"]) if body.get("quantity") else None

    result = await service.place_strategy_stop_loss_order(
        db=db,
        user_id=current_user.id,
        strategy_execution_id=int(execution_id),
        trigger_price=trigger_price,
        price=price,
        order_type=order_type,
        quantity=quantity,
    )
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return ApiResponse(
        success=True,
        message=result.get("message", "Strategy stop-loss order placed successfully"),
        data=result,
        requestId=request_id,
    )


# Include both sub-routers into main router
router.include_router(generic_router)
router.include_router(dhan_router)
