import pytest
from httpx import AsyncClient
from sqlalchemy import select
from decimal import Decimal

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.strategies.models import Strategy, StrategyVersion, StrategyRuntimeState
from app.strategies.enums import StrategyLifecycleState
from app.strategies.schemas import StrategyRequest
from app.strategies.service import StrategyService
from app.strategies.state_manager import StrategyStateManager

@pytest.fixture
async def active_admin(db_session):
    """Creates a seeded active admin user for strategies testing."""
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("adminpass123"),
        role=UserRole.ADMIN,
        is_active=True,
        referral_code="REF-ADM999"
    )
    db_session.add(admin)
    await db_session.flush()
    return admin

@pytest.mark.asyncio
async def test_strategy_validation_rules(client: AsyncClient, active_admin):
    # Authenticate admin
    login_res = await client.post("/api/v1/auth/admin/login", json={
        "email": "admin@example.com",
        "password": "adminpass123"
    })
    token = login_res.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Invalid underlying asset validation
    invalid_payload = {
        "name": "Nifty Bull Spread",
        "description": "Bullish call option legs",
        "underlying": "INVALID_ASSET", # not supported
        "capital": 100000,
        "tradingType": "INTRADAY",
        "mode": "PAPER",
        "legs": [
            {
                "sequence": 1,
                "segment": "OPT",
                "side": "BUY",
                "strikeSelection": "ATM",
                "expiry": "WEEKLY",
                "lots": 1
            }
        ],
        "entrySetting": {"entryTime": "09:20"},
        "entryDays": ["MONDAY", "TUESDAY"],
        "exitSetting": {"exitTime": "15:15"}
    }
    
    response = await client.post("/api/v1/admin/strategies", json=invalid_payload, headers=headers)
    assert response.status_code == 400
    assert "validation failed" in response.json()["message"].lower()

@pytest.mark.asyncio
async def test_strategy_inplace_versus_new_version(client: AsyncClient, active_admin, db_session):
    login_res = await client.post("/api/v1/auth/admin/login", json={
        "email": "admin@example.com",
        "password": "adminpass123"
    })
    token = login_res.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    strategy_payload = {
        "name": "Nifty Intraday Buy",
        "description": "ATM Buy Leg",
        "underlying": "NIFTY",
        "capital": 50000.00,
        "tradingType": "INTRADAY",
        "mode": "PAPER",
        "legs": [
            {
                "sequence": 1,
                "segment": "OPT",
                "side": "BUY",
                "strikeSelection": "ATM",
                "expiry": "WEEKLY",
                "lots": 1
            }
        ],
        "entrySetting": {"entryTime": "09:30"},
        "entryDays": ["MONDAY"],
        "exitSetting": {"exitTime": "15:00"}
    }

    # Create Strategy
    res_create = await client.post("/api/v1/admin/strategies", json=strategy_payload, headers=headers)
    assert res_create.status_code == 201
    strategy_id = res_create.json()["data"]["id"]

    # 1. Without executions, updates should be in-place (keeps Version 1)
    strategy_payload["description"] = "Updated Description Inplace"
    res_update_inplace = await client.put(f"/api/v1/admin/strategies/{strategy_id}", json=strategy_payload, headers=headers)
    assert res_update_inplace.status_code == 200
    assert res_update_inplace.json()["data"]["versionNumber"] == 1
    assert res_update_inplace.json()["data"]["description"] == "Updated Description Inplace"

    # 2. Simulate executions exist by adding an execution record to strategy_versions (id = 1)
    stmt_v = select(StrategyVersion).where(StrategyVersion.strategy_id == strategy_id)
    res_v = await db_session.execute(stmt_v)
    version = res_v.scalars().first()

    from app.strategies.models import StrategyExecution
    execution = StrategyExecution(
        strategy_id=strategy_id,
        strategy_version_id=version.id,
        user_id=active_admin.id,
        status="SUCCESS",
        entry_time=version.created_at
    )
    db_session.add(execution)
    await db_session.commit()

    # Update again. Because executions exist, version number must increment to 2!
    strategy_payload["name"] = "Nifty Intraday Buy V2"
    res_update_v2 = await client.put(f"/api/v1/admin/strategies/{strategy_id}", json=strategy_payload, headers=headers)
    assert res_update_v2.status_code == 200
    assert res_update_v2.json()["data"]["versionNumber"] == 2
    assert res_update_v2.json()["data"]["name"] == "Nifty Intraday Buy V2"

@pytest.mark.asyncio
async def test_golden_rule_api_validation(client: AsyncClient):
    # 1. Valid Golden Rule parsing request
    res = await client.post("/api/strategy/rules/parse", json={
        "strategyId": "STRAT-R60B",
        "ruleType": "GOLDEN_RULE",
        "text": "Wait for candle closure above breakout level",
        "defaultTimeframe": "15m"
    })
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True
    assert res_data["data"]["validationStatus"] == "VALID"
    assert res_data["data"]["rule"]["type"] == "GOLDEN_RULE"
    assert res_data["data"]["rule"]["confirmation"] == "CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL"
    assert res_data["data"]["rule"]["mandatory"] is True

    # 2. Type mismatch negative test case (rejects EXIT type for Golden Rule text)
    res_mismatch = await client.post("/api/strategy/rules/parse", json={
        "strategyId": "STRAT-R60B",
        "ruleType": "EXIT",
        "text": "Wait for candle closure above breakout level",
        "defaultTimeframe": "15m"
    })
    assert res_mismatch.status_code == 200  # API returns successful payload with error indicator code
    res_mismatch_data = res_mismatch.json()
    assert res_mismatch_data["success"] is False
    assert res_mismatch_data["code"] == "RULE_TYPE_MISMATCH"
    assert "classified as a GOLDEN_RULE" in res_mismatch_data["message"]

@pytest.mark.asyncio
async def test_custom_strategies_admin_flow(client: AsyncClient, active_admin):
    # Authenticate admin
    login_res = await client.post("/api/v1/auth/admin/login", json={
        "email": "admin@example.com",
        "password": "adminpass123"
    })
    token = login_res.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # Post custom strategy payload
    payload = {
        "id": "STRAT-6B2PCB",
        "name": "My Custom Strategy",
        "author": "Trader Analyst",
        "description": "Custom strategy description",
        "category": "Option Buying - Index",
        "marketBias": "BULLISH",
        "underlying": "NIFTY 50",
        "indicesArray": ["NIFTY 50"],
        "entryTimeframe": "15m",
        "expiryType": "Weekly",
        "status": "ACTIVE_LIVE",
        "config": {
            "meta": {
                "strategyId": "STRAT-6B2PCB",
                "strategyName": "My Custom Strategy",
                "authorName": "Trader Analyst",
                "status": "ACTIVE_LIVE"
            },
            "description": "Custom strategy description",
            "category": "Option Buying - Index",
            "marketBias": "BULLISH",
            "instrument": {
                "underlying": "NIFTY 50",
                "indicesArray": ["NIFTY 50"],
                "expiryType": "Weekly"
            },
            "timing": {
                "entryFrom": "09:20",
                "entryTo": "14:30",
                "forcedExitTime": "15:15",
                "applicableDays": ["Mon","Tue","Wed","Thu","Fri"]
            },
            "entryTimeframe": "15m",
            "entryConditions": [],
            "exitConditions": [],
            "riskManagement": {
                "capitalAllocationPerTrade": 100000.0
            },
            "scriptExecutionPayload": {
                "runInPython": True,
                "runInNode": True,
                "cliCommand": "python run_strategy.py --id STRAT-6B2PCB --bias BULLISH"
            }
        }
    }
    
    res = await client.post("/api/v1/admin/custom-strategies", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["name"] == "My Custom Strategy"
    assert data["timeframe"] == "15m"
    assert data["status"] == "ACTIVE_LIVE"
    assert data["scriptExecutionPayload"]["cliCommand"] == "python run_strategy.py --id STRAT-6B2PCB --bias BULLISH"

@pytest.mark.asyncio
async def test_custom_strategies_new_format(client: AsyncClient, active_admin):
    # Authenticate admin
    login_res = await client.post("/api/v1/auth/admin/login", json={
        "email": "admin@example.com",
        "password": "adminpass123"
    })
    token = login_res.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
      "schemaVersion": "2.0.0",
      "executionEngine": "ZENALGO_QUANT_ENGINE",
      "meta": {
        "strategyId": "STRAT-SSNZHB",
        "strategyName": "dfdsf",
        "authorName": "zdds",
        "createdAt": "2026-08-29T12:06:07.356Z",
        "status": "ACTIVE_LIVE"
      },
      "description": "fsdfs",
      "youtubeUrl": "sdfs",
      "coreIdea": "fsf",
      "category": "Option Buying - Index",
      "marketBias": "BULLISH",
      "timeframe": "15m",
      "instrument": {
        "underlying": "NIFTY 50",
        "indicesArray": ["NIFTY 50"],
        "expiryType": "Weekly"
      },
      "schedule": {
        "entryFrom": "09:20",
        "forcedExitTime": "15:15",
        "entryDay": "Mon",
        "exitDay": "Tue",
        "weeklyCycleScope": "SAME_WEEK",
        "entryDays": ["Mon"],
        "exitDays": ["Tue"],
        "avoidEvents": ""
      },
      "entryConditions": ["ssd"],
      "exitConditions": ["sds"],
      "keyRememberPoints": ["dsd"],
      "riskManagement": {
        "riskRewardRatio": "3",
        "stopLoss": "2232",
        "maxLossPerTrade": "222",
        "maxLossPerDay": "32",
        "capitalAllocationPerTrade": "dsd"
      },
      "target": {
        "value": "232",
        "scaleOutPlan": ""
      },
      "scriptExecutionPayload": {
        "runInPython": True,
        "runInNode": True,
        "cliCommand": "python run_strategy.py --id STRAT-SSNZHB --bias BULLISH"
      }
    }
    
    # Send request directly to strategies router through the payload mapper
    res = await client.post("/api/v1/admin/custom-strategies", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["name"] == "dfdsf"
    assert data["timeframe"] == "15m"
    assert data["status"] == "ACTIVE_LIVE"
    assert data["entryDays"] == ["MONDAY"]
    assert data["capital"] == "100000.00"  # Fallback due to string 'dsd' capital Allocation

@pytest.mark.asyncio
async def test_create_strategy_auto_initializes_runtime_state_waiting(db_session, active_admin):
    """Test 2D-01: Verifies strategy creation automatically provisions runtime state in WAITING."""
    req = StrategyRequest(
        name="Auto State Strategy",
        description="Testing runtime state auto initialization",
        underlying="NIFTY",
        capital=Decimal("150000.00"),
        tradingType="INTRADAY",
        mode="PAPER",
        legs=[{
            "sequence": 1,
            "segment": "OPT",
            "side": "BUY",
            "strikeSelection": "ATM",
            "expiry": "WEEKLY",
            "lots": 2
        }],
        entrySetting={"entryTime": "09:20"},
        entryDays=["MONDAY", "WEDNESDAY"],
        exitSetting={"exitTime": "15:15"}
    )
    resp = await StrategyService.create_strategy(db_session, req, active_admin.id)
    assert resp.id is not None
    assert resp.name == "Auto State Strategy"

    # Query StrategyRuntimeState from DB
    res = await db_session.execute(
        select(StrategyRuntimeState).where(StrategyRuntimeState.strategy_id == resp.id)
    )
    runtime_state = res.scalar_one_or_none()
    assert runtime_state is not None
    assert runtime_state.lifecycle_state == StrategyLifecycleState.WAITING
    assert runtime_state.strategy_id == resp.id
    assert runtime_state.created_at is not None

@pytest.mark.asyncio
async def test_create_strategy_runtime_state_strategy_and_version_mapping(db_session, active_admin):
    """Test 2D-02: Verifies exact strategy_id and strategy_version_id mapping."""
    req = StrategyRequest(
        name="Mapping Test Strategy",
        underlying="BANKNIFTY",
        capital=Decimal("200000.00"),
        tradingType="INTRADAY",
        mode="PAPER",
        legs=[{
            "sequence": 1,
            "segment": "OPT",
            "side": "BUY",
            "strikeSelection": "ATM",
            "expiry": "WEEKLY",
            "lots": 1
        }],
        entrySetting={"entryTime": "09:30"},
        entryDays=["TUESDAY"],
        exitSetting={"exitTime": "15:00"}
    )
    resp = await StrategyService.create_strategy(db_session, req, active_admin.id)
    
    # Retrieve strategy and its active version from DB
    res_strat = await db_session.execute(select(Strategy).where(Strategy.id == resp.id))
    strategy = res_strat.scalar_one()

    res_state = await db_session.execute(
        select(StrategyRuntimeState).where(StrategyRuntimeState.strategy_id == strategy.id)
    )
    runtime_state = res_state.scalar_one()

    assert runtime_state.strategy_id == strategy.id
    assert runtime_state.strategy_version_id == strategy.current_version_id

@pytest.mark.asyncio
async def test_create_strategy_exactly_one_runtime_state(db_session, active_admin):
    """Test 2D-03: Verifies exactly one runtime state row is created per strategy."""
    req = StrategyRequest(
        name="Single State Count Strategy",
        underlying="NIFTY",
        capital=Decimal("100000.00"),
        tradingType="INTRADAY",
        mode="PAPER",
        legs=[{
            "sequence": 1,
            "segment": "OPT",
            "side": "BUY",
            "strikeSelection": "ATM",
            "expiry": "WEEKLY",
            "lots": 1
        }],
        entrySetting={"entryTime": "09:20"},
        entryDays=["MONDAY"],
        exitSetting={"exitTime": "15:15"}
    )
    resp = await StrategyService.create_strategy(db_session, req, active_admin.id)

    res = await db_session.execute(
        select(StrategyRuntimeState).where(StrategyRuntimeState.strategy_id == resp.id)
    )
    rows = res.scalars().all()
    assert len(rows) == 1

@pytest.mark.asyncio
async def test_create_strategy_transaction_rollback_safety(db_session, active_admin, monkeypatch):
    """Test 2D-04: Verifies that failure during runtime state initialization rolls back Strategy and Version."""
    async def failing_initialize(db, strategy_id, strategy_version_id):
        raise RuntimeError("Simulated Database Crash during RuntimeState insert")

    monkeypatch.setattr(StrategyStateManager, "initialize_runtime_state", failing_initialize)

    req = StrategyRequest(
        name="Rollback Test Strategy",
        underlying="NIFTY",
        capital=Decimal("100000.00"),
        tradingType="INTRADAY",
        mode="PAPER",
        legs=[{
            "sequence": 1,
            "segment": "OPT",
            "side": "BUY",
            "strikeSelection": "ATM",
            "expiry": "WEEKLY",
            "lots": 1
        }],
        entrySetting={"entryTime": "09:20"},
        entryDays=["MONDAY"],
        exitSetting={"exitTime": "15:15"}
    )

    with pytest.raises(RuntimeError, match="Simulated Database Crash"):
        async with db_session.begin_nested():
            await StrategyService.create_strategy(db_session, req, active_admin.id)

    # Verify no strategy or version exists with this name in DB
    res_strat = await db_session.execute(
        select(Strategy).where(Strategy.name == "Rollback Test Strategy")
    )
    assert res_strat.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_create_strategy_api_endpoint_initializes_runtime_state(client: AsyncClient, active_admin, db_session):
    """Test 2D-05: Verifies the HTTP API endpoint creates Strategy, Version and RuntimeState."""
    login_res = await client.post("/api/v1/auth/admin/login", json={
        "email": "admin@example.com",
        "password": "adminpass123"
    })
    token = login_res.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "name": "API Created Strategy",
        "description": "Created via API endpoint",
        "underlying": "NIFTY",
        "capital": 100000.00,
        "tradingType": "INTRADAY",
        "mode": "PAPER",
        "legs": [
            {
                "sequence": 1,
                "segment": "OPT",
                "side": "BUY",
                "strikeSelection": "ATM",
                "expiry": "WEEKLY",
                "lots": 1
            }
        ],
        "entrySetting": {"entryTime": "09:30"},
        "entryDays": ["MONDAY"],
        "exitSetting": {"exitTime": "15:00"}
    }

    res_create = await client.post("/api/v1/admin/strategies", json=payload, headers=headers)
    assert res_create.status_code == 201
    strategy_id = res_create.json()["data"]["id"]

    # Verify DB has StrategyRuntimeState in WAITING
    res_state = await db_session.execute(
        select(StrategyRuntimeState).where(StrategyRuntimeState.strategy_id == strategy_id)
    )
    runtime_state = res_state.scalar_one_or_none()
    assert runtime_state is not None
    assert runtime_state.lifecycle_state == StrategyLifecycleState.WAITING






