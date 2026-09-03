import pytest
from decimal import Decimal
from datetime import datetime, date, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.strategies.risk.evaluators import evaluate_capital_and_margin
from app.strategies.risk.enums import RiskFailureCode, RiskCheckType
from app.brokers.models import UserOrder, UserFundSnapshot
from app.brokers.service import place_user_order
from app.core.exceptions import ValidationError

@pytest.mark.asyncio
async def test_evaluate_capital_and_margin_within_50_pct():
    """Order value (40,000) <= 50% of 100,000 balance -> MUST PASS."""
    available_cap = Decimal("100000.00")
    required_cap = Decimal("40000.00")  # 40% of balance

    res = evaluate_capital_and_margin(
        available_capital=available_cap,
        required_capital=required_cap,
        user_id=1
    )
    assert res.passed is True
    assert "within 50%" in res.reason
    assert res.check_type == RiskCheckType.CAPITAL_AND_MARGIN

@pytest.mark.asyncio
async def test_evaluate_capital_and_margin_exceeds_50_pct():
    """Order value (60,000) > 50% of 100,000 balance -> MUST FAIL with ORDER_EXCEEDS_50_PCT_BALANCE."""
    available_cap = Decimal("100000.00")
    required_cap = Decimal("60000.00")  # 60% of balance

    res = evaluate_capital_and_margin(
        available_capital=available_cap,
        required_capital=required_cap,
        user_id=1
    )
    assert res.passed is False
    assert res.failure_code == RiskFailureCode.ORDER_EXCEEDS_50_PCT_BALANCE
    assert "exceeds 50% maximum allocation limit" in res.reason
    assert "₹60,000.00" in res.reason
    assert "₹50,000.00" in res.reason

@pytest.mark.asyncio
async def test_manual_order_blocks_exceeding_50_pct(db_session: AsyncSession):
    """Direct manual order exceeding 50% balance must be blocked and saved in DB as REJECTED."""
    import uuid
    from app.users.models import User, UserRole
    from app.brokers.models import BrokerAccount
    from app.core.security import hash_password

    u_id = uuid.uuid4().hex[:8]
    # 1. Create test user
    user = User(
        email=f"test_risk_50_{u_id}@trading.com",
        password_hash=hash_password("pass123"),
        role=UserRole.TRADER,
        referral_code=f"REF-{u_id}",
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()

    from datetime import datetime, timezone, timedelta
    from app.brokers.models import UserDailyBrokerConnection

    # 2. Setup connected Mock broker account
    account = BrokerAccount(
        user_id=user.id,
        broker_code="MOCK",
        account_client_id="MOCK_RISK_01",
        status="ACTIVE",
        expiry_time=datetime.now(timezone.utc) + timedelta(days=1)
    )
    account.set_credentials({"clientId": "MOCK_RISK_01", "accessToken": "MOCK_TOKEN"})
    db_session.add(account)
    await db_session.flush()

    today = date.today()
    conn = UserDailyBrokerConnection(
        user_id=user.id,
        connection_date=today,
        broker_account_id=account.id,
        broker_code="MOCK",
        status="ACTIVE"
    )
    db_session.add(conn)

    # 3. Setup user fund snapshot: ₹1,00,000 available balance
    fund_snap = UserFundSnapshot(
        user_id=user.id,
        broker_name="MOCK",
        snapshot_date=today,
        available_balance=Decimal("100000.00")
    )
    db_session.add(fund_snap)
    await db_session.commit()

    # 4. Attempt to place BUY order of ₹65,000 (65% of balance -> Exceeds 50% limit of ₹50,000)
    order_payload = {
        "tradingSymbol": "RELIANCE",
        "securityId": "2885",
        "exchangeSegment": "NSE_EQ",
        "transactionType": "BUY",
        "quantity": 1,
        "price": 65000.0,
        "orderType": "LIMIT",
        "productType": "CNC"
    }

    with pytest.raises(ValidationError) as excinfo:
        await place_user_order(db_session, user.id, order_payload)

    assert "exceeds 50% maximum allocation limit" in str(excinfo.value)
    assert "₹65,000.00" in str(excinfo.value)

    # 5. Verify order was recorded in PostgreSQL database with status REJECTED
    stmt_order = select(UserOrder).where(UserOrder.user_id == user.id)
    res_order = await db_session.execute(stmt_order)
    saved_order = res_order.scalar_one_or_none()

    assert saved_order is not None
    assert saved_order.order_status == "REJECTED"
    assert "exceeds 50% maximum allocation limit" in saved_order.rejection_reason
    assert saved_order.trading_symbol == "RELIANCE"


@pytest.mark.asyncio
async def test_process_user_blocks_execution_exceeding_50_pct(db_session: AsyncSession):
    """Strategy signal copy-trading execution exceeding 50% balance must be REJECTED and logged in DB."""
    import uuid
    from app.users.models import User, UserRole
    from app.brokers.models import BrokerAccount, UserDailyBrokerConnection
    from app.core.security import hash_password
    from app.subscriptions.models import Subscription, Plan, PlanStrategyAccess
    from app.strategies.models import Strategy, StrategyVersion, StrategyLeg
    from app.execution.models import StrategySignal, StrategyUserExecutionTrace, StrategyExecutionTraceEvent
    from app.execution.service import process_user, create_batch_record

    u_id = uuid.uuid4().hex[:8]
    test_user = User(
        email=f"strat_risk50_{u_id}@trading.com",
        password_hash=hash_password("pass123"),
        role=UserRole.TRADER,
        referral_code=f"REF-S{u_id}",
        is_active=True
    )
    db_session.add(test_user)
    await db_session.flush()

    today = date.today()

    # Setup Broker Account & Daily Connection
    account = BrokerAccount(
        user_id=test_user.id,
        broker_code="MOCK",
        account_client_id=f"MOCK_{u_id}",
        status="ACTIVE",
        expiry_time=datetime.now(timezone.utc) + timedelta(days=1)
    )
    account.set_credentials({"clientId": f"MOCK_{u_id}", "accessToken": "MOCK_TOKEN", "mockAvailableBalance": "10000.00"})
    db_session.add(account)
    await db_session.flush()

    conn = UserDailyBrokerConnection(
        user_id=test_user.id,
        connection_date=today,
        broker_account_id=account.id,
        broker_code="MOCK",
        status="ACTIVE"
    )
    db_session.add(conn)

    # Setup Fund Snapshot: ₹10,000 balance -> 50% Max Allowed is ₹5,000
    fund_snap = UserFundSnapshot(
        user_id=test_user.id,
        broker_name="MOCK",
        snapshot_date=today,
        available_balance=Decimal("10000.00")
    )
    db_session.add(fund_snap)

    # Setup Plan & Subscription
    plan = Plan(
        code=f"PRO_{u_id}",
        name="Pro Plan",
        monthly_price=Decimal("999.00"),
        max_strategy_executions_per_day=10,
        is_active=True
    )
    db_session.add(plan)
    await db_session.flush()

    now_utc = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=test_user.id,
        plan_id=plan.id,
        status="ACTIVE",
        start_at=now_utc,
        current_period_start=now_utc,
        current_period_end=now_utc + timedelta(days=30)
    )
    db_session.add(sub)

    # Setup Strategy with order value = ₹200 strike * 50 lot_size = ₹10,000 (exceeds 50% cap of ₹5,000)
    strategy = Strategy(user_id=test_user.id, name=f"Risk Test Strategy {u_id}", mode="LIVE", status="ACTIVE_LIVE")
    db_session.add(strategy)
    await db_session.flush()

    plan_access = PlanStrategyAccess(plan_id=plan.id, strategy_id=strategy.id, is_enabled=True)
    db_session.add(plan_access)

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("10000.00"))
    db_session.add(version)
    await db_session.flush()

    leg = StrategyLeg(
        strategy_version_id=version.id,
        sequence=1,
        side="BUY",
        segment="OPTIDX",
        strike_selection="ATM",
        strike_value=Decimal("200.00"),  # Order value = 200 * 50 = ₹10,000 (100% of balance)
        expiry="WEEKLY",
        lots=1
    )
    db_session.add(leg)

    signal = StrategySignal(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        trading_date=today,
        entry_time="09:30"
    )
    db_session.add(signal)
    await db_session.flush()

    batch = await create_batch_record(db_session, signal.id, total_users=1)

    # Execute copy trading process for user
    exec_result = await process_user(db_session, batch, test_user.id)

    # Assert execution was BLOCKED by the 50% rule
    assert exec_result.executed is False
    assert exec_result.status == "REJECTED"
    assert exec_result.failureCode == "ORDER_EXCEEDS_50_PCT_BALANCE"
    assert "exceeds 50% maximum allocation limit" in exec_result.failureReason

    # Assert trace record in database has status REJECTED
    stmt_trace = select(StrategyUserExecutionTrace).where(
        StrategyUserExecutionTrace.user_id == test_user.id,
        StrategyUserExecutionTrace.signal_id == signal.id
    )
    res_trace = await db_session.execute(stmt_trace)
    saved_trace = res_trace.scalar_one_or_none()

    assert saved_trace is not None
    assert saved_trace.status == "REJECTED"
    assert saved_trace.current_step == "BALANCE_CHECK"
    assert saved_trace.failure_code == "ORDER_EXCEEDS_50_PCT_BALANCE"
    assert "exceeds 50% maximum allocation limit" in saved_trace.failure_reason

    # Assert trace event in database
    stmt_events = select(StrategyExecutionTraceEvent).where(
        StrategyExecutionTraceEvent.execution_trace_id == saved_trace.id,
        StrategyExecutionTraceEvent.step == "BALANCE_CHECK"
    )
    res_events = await db_session.execute(stmt_events)
    events = res_events.scalars().all()

    assert len(events) >= 1
    failed_event = next(e for e in events if e.status == "FAILED")
    assert failed_event.error_code == "ORDER_EXCEEDS_50_PCT_BALANCE"
    assert "exceeds 50% maximum allocation limit" in failed_event.message
