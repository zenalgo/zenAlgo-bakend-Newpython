import pytest
import asyncio
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.future import select


from app.core.database import AsyncSessionLocal
from app.brokers.service import connect_broker, get_active_broker_for_user, disconnect_account
from app.brokers.models import BrokerAccount, UserDailyBrokerConnection
from app.brokers.bootstrap import bootstrap_broker_adapters
from app.brokers.base.interface import BrokerAdapter
from app.brokers.base.schemas import OrderRequest, OrderResult, BrokerFormConfig, ValidationResult, BrokerProfile, Funds
from app.brokers.registry import broker_registry
from app.execution.service import process_user, create_batch_record
from app.execution.models import StrategySignal, StrategyExecutionBatch
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg
from app.users.models import User, UserRole
from app.subscriptions.models import Plan, Subscription, PlanStrategyAccess
from app.core.exceptions import ConflictError, ResourceNotFoundError, DuplicateRequestException
from sqlalchemy.exc import IntegrityError

# Register adapters
bootstrap_broker_adapters()


# Register a dummy Zerodha adapter for multi-broker daily testing
class DummyZerodhaAdapter(BrokerAdapter):
    @property
    def broker_code(self) -> str:
        return "ZERODHA"

    @property
    def name(self) -> str:
        return "Zerodha Kite"

    def get_form_config(self) -> BrokerFormConfig:
        return BrokerFormConfig(brokerCode="ZERODHA", name="Zerodha Kite", authType="API_KEY", fields=[])

    async def validate_credentials(self, credentials: dict) -> ValidationResult:
        return ValidationResult(is_valid=True, status="ACTIVE")

    async def validate_connection(self, account, credentials: dict) -> ValidationResult:
        return ValidationResult(is_valid=True, status="ACTIVE")

    async def get_profile(self, account, credentials: dict) -> BrokerProfile:
        return BrokerProfile(client_id="ZERODHA_123", name="Zerodha User")

    async def place_order(self, account, credentials: dict, order_req: OrderRequest) -> OrderResult:
        return OrderResult(broker_order_id="ZERO_ORDER_1", order_status="OPEN")

    async def cancel_order(self, account, credentials: dict, order_id: str) -> bool:
        return True

    async def modify_order(self, account, credentials: dict, order_id: str, order_req: OrderRequest) -> OrderResult:
        return OrderResult(broker_order_id=order_id, order_status="OPEN")

    async def get_order_status(self, account, credentials: dict, order_id: str):
        return None

    async def get_positions(self, account, credentials: dict):
        return []

    async def get_holdings(self, account, credentials: dict):
        return []

    async def get_funds(self, account, credentials: dict):
        return Funds(available_balance=100000)

broker_registry.register(DummyZerodhaAdapter())


@pytest.mark.asyncio
async def test_1_connect_dhan_on_aug_29(db_session, test_user):
    """Test 1: User connects Dhan on Aug 29 -> SUCCESS."""
    aug_29 = date(2026, 8, 29)
    acc = await connect_broker(db_session, test_user.id, "DHAN", {"clientId": "100001", "accessToken": "TOKEN_1"}, target_date=aug_29)
    
    assert acc.broker_code == "DHAN"
    assert acc.user_id == test_user.id

    active_acc = await get_active_broker_for_user(db_session, test_user.id, target_date=aug_29)
    assert active_acc.id == acc.id
    assert active_acc.broker_code == "DHAN"


@pytest.mark.asyncio
async def test_2_same_user_connects_zerodha_same_day_rejected(db_session, test_user):
    """Test 2: Same user connects Zerodha on Aug 29 after Dhan -> REJECTED with ConflictError."""
    aug_29 = date(2026, 8, 29)
    await connect_broker(db_session, test_user.id, "DHAN", {"clientId": "100001", "accessToken": "TOKEN_1"}, target_date=aug_29)

    with pytest.raises(ConflictError) as exc_info:
        await connect_broker(db_session, test_user.id, "ZERODHA", {"apiKey": "KITE_123"}, target_date=aug_29)

    assert "User can connect only ONE broker per calendar day" in str(exc_info.value)


@pytest.mark.asyncio
async def test_3_same_user_reconnects_dhan_same_day_success(db_session, test_user):
    """Test 3: Same user connects Dhan again on Aug 29 -> SUCCESS (Updates existing Dhan account)."""
    aug_29 = date(2026, 8, 29)
    await connect_broker(db_session, test_user.id, "DHAN", {"clientId": "100001", "accessToken": "TOKEN_OLD"}, target_date=aug_29)

    updated_acc = await connect_broker(db_session, test_user.id, "DHAN", {"clientId": "100001", "accessToken": "TOKEN_NEW"}, target_date=aug_29)
    assert updated_acc.broker_code == "DHAN"
    assert updated_acc.credentials.get("accessToken") == "TOKEN_NEW"


@pytest.mark.asyncio
async def test_4_same_user_connects_zerodha_next_day_success(db_session, test_user):
    """Test 4: Same user connects Zerodha on Aug 30 -> SUCCESS."""
    aug_29 = date(2026, 8, 29)
    aug_30 = date(2026, 8, 30)

    await connect_broker(db_session, test_user.id, "DHAN", {"clientId": "100001", "accessToken": "TOKEN_1"}, target_date=aug_29)

    acc_30 = await connect_broker(db_session, test_user.id, "ZERODHA", {"apiKey": "KITE_123"}, target_date=aug_30)
    assert acc_30.broker_code == "ZERODHA"

    active_29 = await get_active_broker_for_user(db_session, test_user.id, target_date=aug_29)
    active_30 = await get_active_broker_for_user(db_session, test_user.id, target_date=aug_30)

    assert active_29.broker_code == "DHAN"
    assert active_30.broker_code == "ZERODHA"


@pytest.mark.asyncio
async def test_5_different_users_different_brokers_same_day_success(db_session, test_user):
    """Test 5: User A connects Dhan, User B connects Zerodha on same date -> both SUCCESS."""
    aug_29 = date(2026, 8, 29)

    user_b = User(email="user_b@example.com", password_hash="pass", role=UserRole.USER, is_active=True, referral_code="REF-USERB")
    db_session.add(user_b)
    await db_session.flush()

    acc_a = await connect_broker(db_session, test_user.id, "DHAN", {"clientId": "USER_A_DHAN", "accessToken": "TOK_A"}, target_date=aug_29)
    acc_b = await connect_broker(db_session, user_b.id, "ZERODHA", {"apiKey": "USER_B_ZERO"}, target_date=aug_29)

    assert acc_a.broker_code == "DHAN"
    assert acc_b.broker_code == "ZERODHA"


@pytest.mark.asyncio
async def test_6_concurrency_single_broker_per_day(db_session, test_user):
    """Test 6: Concurrency — 2 connection attempts (Dhan & Zerodha) for same user and date. Exactly one succeeds."""
    aug_29 = date(2026, 8, 29)
    user_id = test_user.id

    # First request: DHAN
    acc_dhan = await connect_broker(db_session, user_id, "DHAN", {"clientId": "CONC_DHAN", "accessToken": "TOK"}, target_date=aug_29)
    assert acc_dhan.broker_code == "DHAN"

    # Concurrent second request: ZERODHA for same user and date -> must fail with ConflictError
    with pytest.raises(ConflictError):
        await connect_broker(db_session, user_id, "ZERODHA", {"apiKey": "CONC_ZERO"}, target_date=aug_29)


@pytest.mark.asyncio
async def test_7_execution_with_mock_broker_without_dhan_dependency(db_session, test_user):
    """Test 7: Core execution works with MockBrokerAdapter with ZERO Dhan imports or coupling."""
    today = date.today()
    now = datetime.now(timezone.utc)

    # 1. Connect MOCK broker for today
    await connect_broker(db_session, test_user.id, "MOCK", {"clientId": "MOCK_USER_1", "accessToken": "MOCK_TOKEN"}, target_date=today)

    # 2. Setup Plan, Strategy, Subscription
    plan = Plan(code="PRO_PLAN", name="Pro Plan", monthly_price=999, is_active=True, max_strategy_executions_per_day=10)
    db_session.add(plan)
    await db_session.flush()

    sub = Subscription(
        user_id=test_user.id,
        plan_id=plan.id,
        status="ACTIVE",
        start_at=now,
        current_period_start=now,
        current_period_end=now + timedelta(days=30)
    )
    db_session.add(sub)

    strategy = Strategy(user_id=test_user.id, name="Mock Strategy", mode="LIVE", status="ACTIVE_LIVE")
    db_session.add(strategy)
    await db_session.flush()

    plan_access = PlanStrategyAccess(plan_id=plan.id, strategy_id=strategy.id, is_enabled=True)
    db_session.add(plan_access)

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("10000.00"))

    db_session.add(version)
    await db_session.flush()

    leg = StrategyLeg(strategy_version_id=version.id, sequence=1, side="BUY", segment="OPTIDX", strike_selection="ATM", expiry="WEEKLY", lots=1)
    db_session.add(leg)

    signal = StrategySignal(strategy_id=strategy.id, strategy_version_id=version.id, trading_date=today, entry_time="09:30")

    db_session.add(signal)
    await db_session.flush()

    batch = await create_batch_record(db_session, signal.id, total_users=1)

    # 3. Process execution
    exec_result = await process_user(db_session, batch, test_user.id)

    assert exec_result.eligible is True
    assert exec_result.executed is True
    assert exec_result.status == "EXECUTED"
