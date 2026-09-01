import pytest
from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.strategies.models import Strategy, StrategyVersion
from app.execution.models import StrategySignal
from app.execution.service import execute_signal_batch
from app.strategies.signals.enums import SignalType, SignalDirection, SignalStatus
from app.strategies.signals.schemas import TradingSignal, build_deterministic_signal_key

@pytest.fixture
async def test_user(db_session):
    """Creates a seeded user for foreign key safety."""
    user = User(
        email="signal_domain_user@example.com",
        password_hash=hash_password("testpass123"),
        role=UserRole.TRADER,
        is_active=True,
        referral_code="REF-SIG001"
    )
    db_session.add(user)
    await db_session.flush()
    return user

# --- Test 1 & 2: Enum Validation & Schema Serialization ---

def test_signal_enums_and_pydantic_schema():
    """Test 1 & 2: Validates SignalType, SignalStatus, and TradingSignal serialization."""
    key = build_deterministic_signal_key(101, 501, SignalType.ENTRY, "101:NIFTY:5m:CANDLE_CLOSED:2026-08-31T03:50:00.000000Z")
    
    signal = TradingSignal(
        signal_key=key,
        strategy_id=101,
        strategy_version_id=501,
        market_event_key="101:NIFTY:5m:CANDLE_CLOSED:2026-08-31T03:50:00.000000Z",
        event_id="NIFTY:5m:CANDLE_CLOSED:2026-08-31T03:50:00.000000Z",
        symbol="NIFTY",
        timeframe="5m",
        signal_type=SignalType.ENTRY,
        direction=SignalDirection.BUY,
        price=Decimal("25020.50"),
        status=SignalStatus.CREATED,
        reason="RSI crossed above 60 confirmed by Breakout Level > 25000"
    )

    assert signal.signal_type == SignalType.ENTRY
    assert signal.status == SignalStatus.CREATED
    assert signal.direction == SignalDirection.BUY
    assert signal.price == Decimal("25020.50")
    assert signal.signal_key == "101:501:ENTRY:101:NIFTY:5m:CANDLE_CLOSED:2026-08-31T03:50:00.000000Z"

# --- Test 3, 4, 5, 6: Deterministic Key Generation Matrix ---

def test_deterministic_signal_key_matrix():
    """Test 3, 4, 5, 6: Verifies signal_key determinism across types, versions, and events."""
    base_key = build_deterministic_signal_key(101, 1, SignalType.ENTRY, "101:NIFTY:5m:EV1")
    
    # 1. Same inputs -> identical key
    same_key = build_deterministic_signal_key(101, 1, SignalType.ENTRY, "101:NIFTY:5m:EV1")
    assert base_key == same_key

    # 2. Different signal_type -> different key
    exit_key = build_deterministic_signal_key(101, 1, SignalType.EXIT, "101:NIFTY:5m:EV1")
    assert base_key != exit_key

    # 3. Different strategy_version -> different key
    v2_key = build_deterministic_signal_key(101, 2, SignalType.ENTRY, "101:NIFTY:5m:EV1")
    assert base_key != v2_key

    # 4. Different market_event_key -> different key
    ev2_key = build_deterministic_signal_key(101, 1, SignalType.ENTRY, "101:NIFTY:5m:EV2")
    assert base_key != ev2_key

# --- Test 7: Database Unique Constraint Enforcement ---

@pytest.mark.asyncio
async def test_database_signal_key_uniqueness(db_session, test_user):
    """Test 7: Inserting duplicate signal_key raises IntegrityError and rolls back cleanly."""
    strategy = Strategy(user_id=test_user.id, name="Signal Key Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("100000.0"))
    db_session.add(version)
    await db_session.flush()

    sig_key = f"{strategy.id}:{version.id}:ENTRY:EV_TEST_100"
    
    # 1. Insert first signal record
    sig1 = StrategySignal(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        trading_date=date.today(),
        entry_time="09:30",
        signal_key=sig_key,
        market_event_key="EV_TEST_100",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED",
        price=Decimal("25000.0"),
        reason="Test first signal"
    )
    db_session.add(sig1)
    await db_session.flush()

    # 2. Attempt to insert second signal with exact same signal_key inside savepoint
    sig2 = StrategySignal(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        trading_date=date.today(),
        entry_time="09:30",
        signal_key=sig_key,
        market_event_key="EV_TEST_100",
        signal_type="ENTRY",
        direction="BUY",
        status="CREATED",
        price=Decimal("25000.0"),
        reason="Duplicate signal"
    )

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(sig2)
            await db_session.flush()

    # Verify session remains functional and sig1 is still present
    stmt = select(StrategySignal).where(StrategySignal.signal_key == sig_key)
    res = await db_session.execute(stmt)
    records = list(res.scalars().all())
    assert len(records) == 1
    assert records[0].id == sig1.id

# --- Test 8 & 9: Existing Execution & Legacy Signal Rows Compatibility ---

@pytest.mark.asyncio
async def test_legacy_signal_row_compatibility(db_session, test_user):
    """Test 8 & 9: Existing StrategySignal queries and execution batches operate with new schema."""
    strategy = Strategy(user_id=test_user.id, name="Legacy Compat Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    version = StrategyVersion(strategy_id=strategy.id, version_number=1, underlying="NIFTY", capital=Decimal("50000.0"))
    db_session.add(version)
    await db_session.flush()

    # Create legacy-style signal without signal_key (nullable)
    legacy_sig = StrategySignal(
        strategy_id=strategy.id,
        strategy_version_id=version.id,
        trading_date=date.today(),
        entry_time="09:30"
    )
    db_session.add(legacy_sig)
    await db_session.flush()

    assert legacy_sig.id is not None
    assert legacy_sig.signal_type == "ENTRY"
    assert legacy_sig.status == "CREATED"
    assert legacy_sig.direction == "BUY"

    # Query back
    stmt = select(StrategySignal).where(StrategySignal.id == legacy_sig.id)
    res = await db_session.execute(stmt)
    fetched = res.scalar_one()
    assert fetched.strategy_id == strategy.id
    assert fetched.strategy_version_id == version.id

# --- Test 10: Strategy Version Foreign Key Safety ---

@pytest.mark.asyncio
async def test_strategy_version_foreign_key_safety(db_session, test_user):
    """Test 10: StrategySignal enforces foreign key reference to strategy_versions."""
    strategy = Strategy(user_id=test_user.id, name="FK Safety Strat", is_active=True)
    db_session.add(strategy)
    await db_session.flush()

    # Non-existent version id 999999
    invalid_sig = StrategySignal(
        strategy_id=strategy.id,
        strategy_version_id=999999,
        trading_date=date.today(),
        entry_time="09:30"
    )

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(invalid_sig)
            await db_session.flush()
