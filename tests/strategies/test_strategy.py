import pytest
from httpx import AsyncClient
from sqlalchemy import select
from decimal import Decimal

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.strategies.models import Strategy, StrategyVersion
from app.strategies.schemas import StrategyRequest

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
