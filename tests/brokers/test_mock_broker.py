import pytest
from httpx import AsyncClient
from app.users.models import User, UserRole
from app.auth.service import hash_password

@pytest.fixture
async def setup_trader_user(db_session):
    trader = User(
        email="mock_trader@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.TRADER,
        is_active=True,
        referral_code="REF-MOCK999"
    )
    db_session.add(trader)
    await db_session.flush()
    return trader

@pytest.mark.asyncio
async def test_generic_broker_apis(client: AsyncClient, setup_trader_user):
    # Authenticate trader
    login_res = await client.post("/api/v1/auth/login", json={
        "email": "mock_trader@example.com",
        "password": "password123"
    })
    token = login_res.json()["data"]["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. List supported brokers
    res_brokers = await client.get("/api/v1/brokers")
    assert res_brokers.status_code == 200
    brokers_data = res_brokers.json()["data"]
    codes = [b["code"] for b in brokers_data]
    assert "DHAN" in codes
    assert "MOCK" in codes

    # 2. Retrieve dynamic connection config for MOCK broker
    res_cfg = await client.get("/api/v1/brokers/MOCK/config")
    assert res_cfg.status_code == 200
    cfg_data = res_cfg.json()["data"]
    assert cfg_data["brokerCode"] == "MOCK"
    assert len(cfg_data["fields"]) >= 2

    # 3. Connect MOCK broker account
    conn_payload = {
        "credentials": {
            "clientId": "MOCK_CLIENT_123",
            "accessToken": "mock_access_token_xyz"
        }
    }
    res_conn = await client.post("/api/v1/brokers/MOCK/connect", json=conn_payload, headers=headers)
    assert res_conn.status_code == 200
    conn_data = res_conn.json()["data"]
    assert conn_data["brokerCode"] == "MOCK"
    assert conn_data["accountClientId"] == "MOCK_CLIENT_123"
    assert conn_data["status"] == "ACTIVE"

    # 4. List connected user accounts
    res_accs = await client.get("/api/v1/brokers/accounts", headers=headers)
    assert res_accs.status_code == 200
    accs_data = res_accs.json()["data"]
    assert len(accs_data) == 1
    assert accs_data[0]["brokerCode"] == "MOCK"
    assert accs_data[0]["accountClientId"] == "MOCK_CLIENT_123"

    # 5. Disconnect broker account
    account_id = accs_data[0]["id"]
    res_del = await client.delete(f"/api/v1/brokers/accounts/{account_id}", headers=headers)
    assert res_del.status_code == 200

    # Verify accounts empty
    res_accs_empty = await client.get("/api/v1/brokers/accounts", headers=headers)
    assert len(res_accs_empty.json()["data"]) == 0
