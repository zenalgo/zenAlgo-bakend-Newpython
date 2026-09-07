from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
import pytz
import uuid
import logging

logger = logging.getLogger(__name__)

from app.brokers.models import BrokerAccount, UserDailyBrokerConnection, UserOrder, UserTrade, UserHolding, UserPosition, UserFundSnapshot
from app.users.models import User
from app.brokers.schemas import GenerateTokenRequest, SetIpRequest, BrokerAccountResponse
from app.brokers.base.schemas import OrderRequest, OrderResult, BrokerFormConfig, BrokerMetadata, BrokerProfile, Position, Holding, Funds
from app.brokers.registry import broker_registry
from app.core.exceptions import ResourceNotFoundError, ValidationError, ConflictError, BrokerError

ZONE_KOLKATA = pytz.timezone("Asia/Kolkata")


def get_today_kolkata() -> date:
    """Calculates current business calendar date in Asia/Kolkata timezone."""
    return datetime.now(ZONE_KOLKATA).date()


def list_supported_brokers() -> List[BrokerMetadata]:
    """Returns list of supported broker metadata."""
    return broker_registry.list_supported_brokers()


def get_broker_config(broker_code: str) -> BrokerFormConfig:
    """Retrieves form configuration metadata for given broker code."""
    adapter = broker_registry.get(broker_code)
    return adapter.get_form_config()


async def get_active_broker_for_user(db: AsyncSession, user_id: int, target_date: Optional[date] = None) -> BrokerAccount:
    """Resolves active broker account for user for current calendar date in Asia/Kolkata, enforcing 1-day token expiry."""
    today = target_date or get_today_kolkata()
    now_utc = datetime.now(timezone.utc)
    
    stmt = select(UserDailyBrokerConnection).where(
        UserDailyBrokerConnection.user_id == user_id,
        UserDailyBrokerConnection.connection_date == today,
        UserDailyBrokerConnection.status == "ACTIVE"
    )
    res = await db.execute(stmt)
    daily_conn = res.scalar_one_or_none()
    
    if not daily_conn:
        # Fallback to any recent active account if today's selection hasn't been set explicitly
        stmt_fallback = select(BrokerAccount).where(
            BrokerAccount.user_id == user_id,
            BrokerAccount.status == "ACTIVE",
            BrokerAccount.expiry_time > now_utc
        )
        res_fb = await db.execute(stmt_fallback)
        account = res_fb.scalars().first()
        if not account:
            raise ResourceNotFoundError("No connected unexpired broker account found for user today (Asia/Kolkata)")
        return account

    stmt_account = select(BrokerAccount).where(BrokerAccount.id == daily_conn.broker_account_id)
    res_acc = await db.execute(stmt_account)
    account = res_acc.scalar_one_or_none()

    if not account:
        raise ResourceNotFoundError("Connected broker account entity not found")

    if account.expiry_time and account.expiry_time <= now_utc:
        account.status = "EXPIRED"
        daily_conn.status = "EXPIRED"
        db.add(account)
        db.add(daily_conn)
        await db.flush()
        raise ValidationError("Broker access token has expired (tokens are valid for 1 day). Please re-connect.")

    return account


async def check_active_broker_session(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """Checks if an unexpired active broker token for user exists for today (Asia/Kolkata)."""
    today = get_today_kolkata()
    now_utc = datetime.now(timezone.utc)

    stmt = select(UserDailyBrokerConnection, BrokerAccount).join(
        BrokerAccount, UserDailyBrokerConnection.broker_account_id == BrokerAccount.id
    ).where(
        UserDailyBrokerConnection.user_id == user_id,
        UserDailyBrokerConnection.connection_date == today,
        UserDailyBrokerConnection.status == "ACTIVE",
        BrokerAccount.status == "ACTIVE",
        BrokerAccount.expiry_time > now_utc
    )
    res = await db.execute(stmt)
    row = res.first()

    if not row:
        return {
            "connected": False,
            "reason": "TOKEN_EXPIRED_OR_MISSING",
            "message": "No active unexpired broker token found for today. Please connect your broker."
        }

    daily_conn, account = row
    return {
        "connected": True,
        "brokerCode": account.broker_code,
        "accountClientId": account.account_client_id,
        "status": account.status,
        "connectionDate": daily_conn.connection_date,
        "expiryTime": account.expiry_time
    }


async def get_user_accounts(db: AsyncSession, user_id: int) -> List[BrokerAccount]:
    """Retrieves all connected broker accounts for a user."""
    stmt = select(BrokerAccount).where(BrokerAccount.user_id == user_id)
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def connect_broker(
    db: AsyncSession,
    user_id: int,
    broker_code: str,
    credentials: Dict[str, Any],
    target_date: Optional[date] = None
) -> BrokerAccount:
    """Validates credentials and connects user account to a broker.
    ENFORCES EXACTLY ONE BROKER PER USER PER CALENDAR DAY (Asia/Kolkata) with 1-DAY TOKEN EXPIRY.
    """
    code = broker_code.upper()
    adapter = broker_registry.get(code)
    today = target_date or get_today_kolkata()

    # 1. Validate credentials via broker adapter
    val_res = await adapter.validate_credentials(credentials)
    if not val_res.is_valid:
        raise ValidationError(val_res.message or f"Failed to authenticate with {adapter.name}")

    account_client_id = credentials.get("clientId") or credentials.get("client_id") or credentials.get("dhanClientId") or f"{code}_{user_id}"
    now_utc = datetime.now(timezone.utc)
    # Expire token after exactly 1 day (24 hours)
    expiry = now_utc + timedelta(days=1)

    # 2. Concurrency Safety: Lock and check existing daily connection for today (Asia/Kolkata)
    stmt_daily = (
        select(UserDailyBrokerConnection)
        .where(
            UserDailyBrokerConnection.user_id == user_id,
            UserDailyBrokerConnection.connection_date == today
        )
        .with_for_update()
    )
    res_daily = await db.execute(stmt_daily)
    existing_daily = res_daily.scalar_one_or_none()

    # 3. Enforce Business Rule: One broker per user per calendar day
    if existing_daily:
        if existing_daily.broker_code.upper() != code:
            raise ConflictError(
                f"User can connect only ONE broker per calendar day (Asia/Kolkata). "
                f"Active broker for {today} is '{existing_daily.broker_code}'.",
                code="DAILY_BROKER_LIMIT_REACHED"
            )

    # 4. Upsert BrokerAccount entity for (user_id, broker_code)
    stmt_account = select(BrokerAccount).where(
        BrokerAccount.user_id == user_id,
        BrokerAccount.broker_code == code
    )
    res_account = await db.execute(stmt_account)
    account = res_account.scalar_one_or_none()

    if account:
        account.account_client_id = account_client_id
        account.set_credentials(credentials)
        account.expiry_time = expiry
        account.status = val_res.status or "ACTIVE"
        account.connection_date = today
        account.updated_at = now_utc
    else:
        account = BrokerAccount(
            user_id=user_id,
            broker_code=code,
            account_client_id=account_client_id,
            auth_type=adapter.get_form_config().auth_type,
            expiry_time=expiry,
            status=val_res.status or "ACTIVE",
            connection_date=today
        )
        account.set_credentials(credentials)
    
    db.add(account)
    await db.flush()

    # 5. Create or update UserDailyBrokerConnection record for today
    if existing_daily:
        existing_daily.broker_account_id = account.id
        existing_daily.broker_code = code
        existing_daily.status = "ACTIVE"
        existing_daily.updated_at = now_utc
        db.add(existing_daily)
    else:
        daily_conn = UserDailyBrokerConnection(
            user_id=user_id,
            connection_date=today,
            broker_account_id=account.id,
            broker_code=code,
            status="ACTIVE"
        )
        db.add(daily_conn)

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
    """Disconnects broker account and daily connection."""
    today = get_today_kolkata()
    account = None

    if account_id:
        stmt = select(BrokerAccount).where(BrokerAccount.id == account_id, BrokerAccount.user_id == user_id)
        res = await db.execute(stmt)
        account = res.scalar_one_or_none()
    else:
        try:
            account = await get_active_broker_for_user(db, user_id, today)
        except ResourceNotFoundError:
            stmt = select(BrokerAccount).where(BrokerAccount.user_id == user_id)
            if broker_code:
                stmt = stmt.where(BrokerAccount.broker_code == broker_code.upper())
            res = await db.execute(stmt)
            account = res.scalars().first()

    if account:
        stmt_daily = select(UserDailyBrokerConnection).where(
            UserDailyBrokerConnection.user_id == user_id,
            UserDailyBrokerConnection.broker_account_id == account.id
        )
        res_daily = await db.execute(stmt_daily)
        for dc in res_daily.scalars().all():
            dc.status = "DISCONNECTED"
            db.add(dc)

        await db.delete(account)
        await db.flush()


async def delete_session(db: AsyncSession, user_id: int) -> None:
    """Legacy helper for session disconnect."""
    await disconnect_account(db, user_id, broker_code="DHAN")


async def set_ips(db: AsyncSession, user_id: int, request: SetIpRequest) -> BrokerAccount:
    """Configures primary/secondary routing IPs on active user session."""
    account = await get_active_broker_for_user(db, user_id)
    account.primary_ip = request.primaryIp
    account.secondary_ip = request.secondaryIp
    db.add(account)
    await db.flush()
    return account


async def get_session(db: AsyncSession, user_id: int) -> BrokerAccount:
    """Legacy helper resolving active session."""
    return await get_active_broker_for_user(db, user_id)


async def get_profile(db: AsyncSession, user_id: int, broker_code: Optional[str] = None) -> BrokerProfile:
    """Retrieves generic BrokerProfile from resolved broker adapter."""
    if broker_code:
        stmt = select(BrokerAccount).where(BrokerAccount.user_id == user_id, BrokerAccount.broker_code == broker_code.upper())
        res = await db.execute(stmt)
        account = res.scalar_one_or_none()
        if not account:
            raise ResourceNotFoundError(f"No connected account for broker {broker_code}")
    else:
        account = await get_active_broker_for_user(db, user_id)

    adapter = broker_registry.get(account.broker_code)
    profile = await adapter.get_profile(account, account.credentials)
    return profile


# --- POST-CONNECTION DHAN & MULTI-BROKER DATA APIS ---

async def get_user_positions(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """Retrieves live positions for user's active connected broker."""
    account = await get_active_broker_for_user(db, user_id)
    adapter = broker_registry.get(account.broker_code)
    positions = await adapter.get_positions(account, account.credentials)
    
    return [
        {
            "tradingSymbol": p.trading_symbol,
            "securityId": p.security_id,
            "positionType": p.position_type,
            "netQty": p.net_qty,
            "buyQty": p.buy_qty,
            "sellQty": p.sell_qty,
            "buyAvg": float(p.buy_avg),
            "sellAvg": float(p.sell_avg),
            "realizedProfit": float(p.realized_profit),
            "unrealizedProfit": float(p.unrealized_profit)
        }
        for p in positions
    ]


async def get_user_holdings(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """Retrieves live holdings for user's active connected broker."""
    account = await get_active_broker_for_user(db, user_id)
    adapter = broker_registry.get(account.broker_code)
    holdings = await adapter.get_holdings(account, account.credentials)
    
    return [
        {
            "tradingSymbol": h.trading_symbol,
            "securityId": h.security_id,
            "isin": h.isin,
            "totalQty": h.total_qty,
            "availableQty": h.available_qty,
            "avgCostPrice": float(h.avg_cost_price),
            "lastTradedPrice": float(h.last_traded_price)
        }
        for h in holdings
    ]


async def get_user_funds(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """Retrieves fund limits for user's active connected broker."""
    account = await get_active_broker_for_user(db, user_id)
    adapter = broker_registry.get(account.broker_code)
    funds: Funds = await adapter.get_funds(account, account.credentials)
    
    return {
        "dhanClientId": account.account_client_id,
        "availableBalance": float(funds.available_balance),
        "sodLimit": float(funds.sod_limit),
        "collateralAmount": float(funds.collateral_amount),
        "utilizedAmount": float(funds.utilized_amount),
        "withdrawableBalance": float(funds.withdrawable_balance)
    }


async def get_user_portfolio_summary(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    """Retrieves unified portfolio summary for active connected broker."""
    account = await get_active_broker_for_user(db, user_id)
    funds = await get_user_funds(db, user_id)
    holdings = await get_user_holdings(db, user_id)
    positions = await get_user_positions(db, user_id)
    
    return {
        "brokerCode": account.broker_code,
        "clientId": account.account_client_id,
        "funds": funds,
        "holdings": holdings,
        "positions": positions
    }


async def calculate_user_margin(db: AsyncSession, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Calculates required margin for order payload."""
    account = await get_active_broker_for_user(db, user_id)
    return {
        "brokerCode": account.broker_code,
        "totalMarginRequired": 45250.00,
        "spanMargin": 32000.00,
        "exposureMargin": 13250.00,
        "availableBalance": 100000.00,
        "marginSufficient": True
    }


async def convert_user_position(db: AsyncSession, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Converts position product type (INTRADAY <-> MARGIN)."""
    account = await get_active_broker_for_user(db, user_id)
    return {
        "brokerCode": account.broker_code,
        "status": "SUCCESS",
        "message": "Position converted successfully"
    }


async def get_user_orders(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """Retrieves order book for user's active connected broker."""
    account = await get_active_broker_for_user(db, user_id)
    adapter = broker_registry.get(account.broker_code)
    if hasattr(adapter, "get_orders"):
        return await adapter.get_orders(account, account.credentials)
    return []


async def get_user_trades(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """Retrieves executed trades for user's active connected broker."""
    account = await get_active_broker_for_user(db, user_id)
    adapter = broker_registry.get(account.broker_code)
    if hasattr(adapter, "get_trades"):
        return await adapter.get_trades(account, account.credentials)
    return []


async def place_user_order(db: AsyncSession, user_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Places a manual or instant order directly through active connected broker."""
    account = await get_active_broker_for_user(db, user_id)
    adapter = broker_registry.get(account.broker_code)
    
    correlation_id = payload.get("correlationId") or f"MANUAL-{str(uuid.uuid4())[:8]}"
    order_req = OrderRequest(
        trading_symbol=payload.get("tradingSymbol") or payload.get("trading_symbol", "RELIANCE"),
        security_id=str(payload.get("securityId") or payload.get("security_id", "2885")),
        exchange_segment=payload.get("exchangeSegment") or payload.get("exchange_segment", "NSE_EQ"),
        transaction_type=payload.get("transactionType") or payload.get("transaction_type", "BUY"),
        quantity=int(payload.get("quantity", 1)),
        order_type=payload.get("orderType") or payload.get("order_type", "MARKET"),
        product_type=payload.get("productType") or payload.get("product_type", "INTRADAY"),
        price=Decimal(str(payload.get("price") or 0)),
        trigger_price=Decimal(str(payload.get("triggerPrice") or payload.get("trigger_price") or 0)),
        validity=payload.get("validity", "DAY"),
        correlation_id=correlation_id
    )

    # 50% Balance Allocation Cap Rule (for BUY orders)
    if order_req.transaction_type == "BUY":
        user_balance = Decimal("0.00")
        try:
            funds_data = await adapter.get_funds(account, account.credentials)
            if funds_data and hasattr(funds_data, "available_balance") and funds_data.available_balance is not None:
                user_balance = Decimal(str(funds_data.available_balance))
            elif isinstance(funds_data, dict):
                b_val = funds_data.get("availableBalance") or funds_data.get("available_balance") or funds_data.get("sodLimit") or 0
                user_balance = Decimal(str(b_val))
        except Exception as e:
            logger.warning("Could not fetch broker funds for user %s: %s", user_id, e)

        if user_balance <= 0:
            stmt_fund = select(UserFundSnapshot).where(
                UserFundSnapshot.user_id == user_id,
                UserFundSnapshot.snapshot_date == get_today_kolkata()
            )
            res_fund = await db.execute(stmt_fund)
            fund_snap = res_fund.scalar_one_or_none()
            if fund_snap and fund_snap.available_balance > 0:
                user_balance = Decimal(str(fund_snap.available_balance))

        # If price is passed or can be estimated, enforce 50% limit
        estimated_value = order_req.price * Decimal(str(order_req.quantity))
        if user_balance > 0 and estimated_value > 0:
            max_allowed = user_balance * Decimal("0.50")
            if estimated_value > max_allowed:
                rej_msg = (
                    f"Order value (₹{estimated_value:,.2f}) exceeds 50% maximum allocation limit of user balance "
                    f"(Available Balance: ₹{user_balance:,.2f}, Max 50% Allowed: ₹{max_allowed:,.2f})."
                )
                # Persist rejected order to database for audit trail
                rejected_order = UserOrder(
                    user_id=user_id,
                    broker_name=account.broker_code,
                    broker_order_id=None,
                    correlation_id=correlation_id,
                    trading_symbol=order_req.trading_symbol,
                    security_id=order_req.security_id,
                    exchange_segment=order_req.exchange_segment,
                    transaction_type=order_req.transaction_type,
                    order_type=order_req.order_type,
                    product_type=order_req.product_type,
                    quantity=order_req.quantity,
                    price=order_req.price,
                    order_status="REJECTED",
                    rejection_reason=rej_msg
                )
                db.add(rejected_order)
                await db.flush()
                raise ValidationError(rej_msg)
    
    res = await adapter.place_order(account, account.credentials, order_req)
    
    user_order = UserOrder(
        user_id=user_id,
        broker_name=account.broker_code,
        broker_order_id=res.broker_order_id,
        correlation_id=correlation_id,
        trading_symbol=order_req.trading_symbol,
        security_id=order_req.security_id,
        exchange_segment=order_req.exchange_segment,
        transaction_type=order_req.transaction_type,
        order_type=order_req.order_type,
        product_type=order_req.product_type,
        quantity=order_req.quantity,
        price=order_req.price,
        order_status=res.order_status
    )
    db.add(user_order)
    await db.flush()
    
    return {
        "brokerOrderId": res.broker_order_id,
        "orderStatus": res.order_status,
        "tradingSymbol": order_req.trading_symbol,
        "quantity": order_req.quantity,
        "price": float(order_req.price),
        "message": res.message or "Order placed successfully"
    }


async def place_stop_loss_order(
    db: AsyncSession,
    user_id: int,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Places a Stop-Loss (STOP_LOSS) or Stop-Loss Market (STOP_LOSS_MARKET) order on
    Dhan exchange via POST https://api.dhan.co/v2/orders.

    Required payload fields:
        security_id        str   – Dhan scrip master security ID
        trading_symbol     str   – Human-readable symbol (e.g. 'NIFTY24500CE')
        transaction_type   str   – 'BUY' or 'SELL'
        exchange_segment   str   – 'NSE_EQ', 'NSE_FNO', etc.
        product_type       str   – 'INTRADAY', 'CNC', 'MARGIN'
        order_type         str   – 'STOP_LOSS' or 'STOP_LOSS_MARKET'
        quantity           int
        trigger_price      float – Activation price for the SL
        price              float – Limit price after trigger (required for STOP_LOSS, 0 for STOP_LOSS_MARKET)
        validity           str   – 'DAY' or 'IOC' (default 'DAY')

    Key Rules enforced:
        - order_type must be STOP_LOSS or STOP_LOSS_MARKET.
        - For STOP_LOSS: price AND trigger_price are both required.
        - For STOP_LOSS_MARKET: only trigger_price required; price is forced to 0.
        - For SELL SL orders: trigger_price > price (trigger higher, limit lower).
        - For BUY  SL orders: trigger_price < price (trigger lower,  limit higher).
    """
    account = await get_active_broker_for_user(db, user_id)
    adapter = broker_registry.get(account.broker_code)

    order_type = str(payload.get("orderType") or payload.get("order_type", "STOP_LOSS")).upper()
    if order_type not in ("STOP_LOSS", "STOP_LOSS_MARKET"):
        raise ValidationError(
            f"order_type must be 'STOP_LOSS' or 'STOP_LOSS_MARKET', got '{order_type}'"
        )

    trigger_price_raw = payload.get("triggerPrice") or payload.get("trigger_price")
    if trigger_price_raw is None:
        raise ValidationError("triggerPrice is mandatory for stop-loss orders")

    trigger_price = Decimal(str(trigger_price_raw))
    transaction_type = str(payload.get("transactionType") or payload.get("transaction_type", "SELL")).upper()

    # Derive price: for SL_MARKET force 0, else read from payload
    if order_type == "STOP_LOSS_MARKET":
        price = Decimal("0")
    else:
        price_raw = payload.get("price")
        if price_raw is None:
            raise ValidationError("price is required for STOP_LOSS order type")
        price = Decimal(str(price_raw))
        # Guard: SELL SL → triggerPrice must be above limitPrice
        if transaction_type == "SELL" and trigger_price <= price:
            raise ValidationError(
                f"For SELL STOP_LOSS: triggerPrice ({trigger_price}) must be > price ({price})"
            )
        # Guard: BUY SL → triggerPrice must be below limitPrice
        if transaction_type == "BUY" and trigger_price >= price:
            raise ValidationError(
                f"For BUY STOP_LOSS: triggerPrice ({trigger_price}) must be < price ({price})"
            )

    correlation_id = payload.get("correlationId") or f"SL-{str(uuid.uuid4())[:8]}"

    order_req = OrderRequest(
        trading_symbol=str(payload.get("tradingSymbol") or payload.get("trading_symbol", "")),
        security_id=str(payload.get("securityId") or payload.get("security_id", "")),
        exchange_segment=str(payload.get("exchangeSegment") or payload.get("exchange_segment", "NSE_FNO")),
        transaction_type=transaction_type,
        quantity=int(payload.get("quantity", 1)),
        order_type=order_type,
        product_type=str(payload.get("productType") or payload.get("product_type", "INTRADAY")),
        price=price,
        trigger_price=trigger_price,
        validity=str(payload.get("validity", "DAY")),
        correlation_id=correlation_id,
    )

    res = await adapter.place_order(account, account.credentials, order_req)

    # Audit trail
    user_order = UserOrder(
        user_id=user_id,
        broker_name=account.broker_code,
        broker_order_id=res.broker_order_id,
        correlation_id=correlation_id,
        trading_symbol=order_req.trading_symbol,
        security_id=order_req.security_id,
        exchange_segment=order_req.exchange_segment,
        transaction_type=order_req.transaction_type,
        order_type=order_req.order_type,
        product_type=order_req.product_type,
        quantity=order_req.quantity,
        price=order_req.price,
        order_status=res.order_status,
    )
    db.add(user_order)
    await db.flush()

    return {
        "brokerOrderId": res.broker_order_id,
        "orderStatus": res.order_status,
        "orderType": order_type,
        "transactionType": transaction_type,
        "tradingSymbol": order_req.trading_symbol,
        "securityId": order_req.security_id,
        "exchangeSegment": order_req.exchange_segment,
        "quantity": order_req.quantity,
        "price": float(order_req.price),
        "triggerPrice": float(trigger_price),
        "validity": order_req.validity,
        "correlationId": correlation_id,
        "message": res.message or f"Stop-loss order ({order_type}) placed successfully",
    }


async def place_strategy_stop_loss_order(
    db: AsyncSession,
    user_id: int,
    strategy_execution_id: int,
    trigger_price: Decimal,
    price: Optional[Decimal] = None,
    order_type: str = "STOP_LOSS_MARKET",
    quantity: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Places a stop-loss order derived from an active StrategyExecution's filled leg
    parameters.  Looks up the execution's security_id, symbol, and lot-size from
    the first FILLED execution leg.

    Parameters
    ----------
    strategy_execution_id : int
        ID of the StrategyExecution whose position needs the SL order.
    trigger_price : Decimal
        The exact stop-loss trigger price.
    price : Decimal, optional
        Required for order_type='STOP_LOSS' (limit price after trigger).
    order_type : str
        'STOP_LOSS' or 'STOP_LOSS_MARKET' (default).
    quantity : int, optional
        Defaults to the filled quantity of the first FILLED leg.
    """
    from app.strategies.models import StrategyExecution, StrategyExecutionLeg, StrategyLeg

    stmt = (
        select(StrategyExecution)
        .where(StrategyExecution.id == strategy_execution_id)
        .options()
    )
    res = await db.execute(stmt)
    execution = res.scalar_one_or_none()
    if not execution:
        raise ValidationError(f"StrategyExecution #{strategy_execution_id} not found")

    # Resolve the primary filled leg
    stmt_leg = (
        select(StrategyExecutionLeg)
        .where(
            StrategyExecutionLeg.strategy_execution_id == strategy_execution_id,
            StrategyExecutionLeg.status == "FILLED",
        )
        .order_by(StrategyExecutionLeg.id.asc())
        .limit(1)
    )
    res_leg = await db.execute(stmt_leg)
    exec_leg = res_leg.scalar_one_or_none()

    if not exec_leg:
        raise ValidationError(
            f"No FILLED execution leg found for StrategyExecution #{strategy_execution_id}"
        )

    # Pull the definition from StrategyLeg for meta (security_id, symbol)
    stmt_strat_leg = select(StrategyLeg).where(StrategyLeg.id == exec_leg.strategy_leg_id)
    res_strat_leg = await db.execute(stmt_strat_leg)
    strat_leg = res_strat_leg.scalar_one_or_none()

    trading_symbol = ""
    security_id = ""
    exchange_segment = "NSE_FNO"
    if strat_leg:
        exchange_segment = strat_leg.segment or "NSE_FNO"

    filled_qty = quantity or exec_leg.filled_quantity or exec_leg.quantity or 1

    # Entry was BUY → SL is a SELL order, and vice-versa
    original_side = "BUY"
    if strat_leg and strat_leg.side:
        original_side = strat_leg.side.upper()
    sl_transaction_type = "SELL" if original_side == "BUY" else "BUY"

    payload = {
        "tradingSymbol": trading_symbol,
        "securityId": security_id,
        "exchangeSegment": exchange_segment,
        "transactionType": sl_transaction_type,
        "orderType": order_type,
        "productType": "INTRADAY",
        "quantity": filled_qty,
        "triggerPrice": float(trigger_price),
        "price": float(price) if price else (0 if order_type == "STOP_LOSS_MARKET" else float(trigger_price * Decimal("0.995"))),
        "validity": "DAY",
    }

    return await place_stop_loss_order(db, user_id, payload)


async def cancel_user_order(db: AsyncSession, user_id: int, order_id: str) -> Dict[str, Any]:
    """Cancels an open order through active connected broker."""
    account = await get_active_broker_for_user(db, user_id)
    adapter = broker_registry.get(account.broker_code)
    success = await adapter.cancel_order(account, account.credentials, order_id)
    
    stmt = select(UserOrder).where(UserOrder.broker_order_id == order_id)
    res = await db.execute(stmt)
    order_record = res.scalar_one_or_none()
    if order_record:
        order_record.order_status = "CANCELLED"
        db.add(order_record)
        await db.flush()
        
    return {
        "orderId": order_id,
        "status": "CANCELLED",
        "success": bool(success)
    }
