import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.users.models import User, UserRole
from app.wallets.models import Wallet

@pytest.mark.asyncio
async def test_user_registration_and_wallet_setup(client: AsyncClient, db_session):
    # Register new user
    payload = {
        "email": "trader@example.com",
        "password": "securepassword123",
        "firstName": "John",
        "lastName": "Doe"
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert data["success"] is True
    assert data["data"]["email"] == "trader@example.com"
    assert data["data"]["isActive"] is False  # Self-registered is inactive by default

    # Verify user exists in DB
    stmt = select(User).where(User.email == "trader@example.com")
    res = await db_session.execute(stmt)
    user = res.scalar_one_or_none()
    assert user is not None
    assert user.first_name == "John"

    # Verify wallet exists and has 0.00 balance
    stmt_wallet = select(Wallet).where(Wallet.user_id == user.id)
    res_wallet = await db_session.execute(stmt_wallet)
    wallet = res_wallet.scalar_one_or_none()
    assert wallet is not None
    assert wallet.balance == 0.00

@pytest.mark.asyncio
async def test_duplicate_registration_failure(client: AsyncClient):
    payload = {
        "email": "dup@example.com",
        "password": "password123"
    }
    # Register once
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Register again
    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    assert res2.json()["success"] is False
    assert res2.json()["code"] == "DUPLICATE_REQUEST"

@pytest.mark.asyncio
async def test_login_deactivated_rejection(client: AsyncClient):
    # Register (which is inactive)
    register_payload = {
        "email": "inactive@example.com",
        "password": "password123"
    }
    await client.post("/api/v1/auth/register", json=register_payload)

    # Attempt Login
    login_payload = {
        "email": "inactive@example.com",
        "password": "password123"
    }
    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.json()["code"] == "DEACTIVATED"
