import pytest
from httpx import AsyncClient
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from app.users.models import User, UserRole
from app.auth.service import hash_password
from app.brokers.models import DhanBrokerSession
from sqlalchemy.future import select

@pytest.fixture
async def setup_trader(db_session):
    """Creates a seeded active trader user for brokers testing."""
    trader = User(
        email="broker_trader@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.TRADER,
        is_active=True,
        referral_code="REF-BRK888"
    )
    db_session.add(trader)
    await db_session.flush()
    return trader

@pytest.mark.asyncio
async def test_session_handling_valid_expired_missing(client: AsyncClient, setup_trader, db_session):
    # Authenticate trader
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "broker_trader@example.com",
        "password": "password123"
    })
    token = login_res.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Initially, no session exists -> expect 404
    res_get = await client.get("/api/v1/dhan/auth/session/me", headers=headers)
    assert res_get.status_code == 404
    assert res_get.json()["code"] == "NOT_FOUND"

    # 2. Add an active session -> expect 200
    session_payload = {
        "clientId": "DHAN_CLIENT_100",
        "accessToken": "dhan_access_token_12345"
    }
    res_set = await client.post("/api/v1/dhan/auth/individual/generate-token", json=session_payload, headers=headers)
    assert res_set.status_code == 200
    assert res_set.json()["data"]["clientId"] == "DHAN_CLIENT_100"
    assert res_set.json()["data"]["status"] == "ACTIVE"

    # Verify session details
    res_check = await client.get("/api/v1/dhan/auth/session/me", headers=headers)
    assert res_check.status_code == 200
    assert res_check.json()["data"]["clientId"] == "DHAN_CLIENT_100"

    # 3. Simulate expired session in DB
    stmt = select(DhanBrokerSession).where(DhanBrokerSession.user_id == setup_trader.id)
    res_stmt = await db_session.execute(stmt)
    session = res_stmt.scalar_one()
    session.expiry_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.add(session)
    await db_session.commit()

    # Get session details - still returns details, but when executing a trade it will validate expiration
    res_check_exp = await client.get("/api/v1/dhan/auth/session/me", headers=headers)
    assert res_check_exp.status_code == 200
    
    # Expiry time check during execution validation
    from app.execution.service import process_user, StrategyExecutionBatch
    from app.execution.models import StrategySignal
    # Create mock batch and trigger check
    # Will be fully covered in integration tests
