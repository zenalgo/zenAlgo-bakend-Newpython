import asyncio
from app.core.database import AsyncSessionLocal
import app.users.models
import app.wallets.models
import app.subscriptions.models
import app.strategies.models
import app.execution.models
import app.brokers.models

from app.users.models import User, UserRole
from app.core.security import hash_password
from sqlalchemy.future import select

from decimal import Decimal
from app.wallets.models import Wallet
from app.subscriptions.models import Plan

async def seed_initial_users():
    async with AsyncSessionLocal() as db:
        users_to_seed = [
            {
                "email": "superadmin@trading.com",
                "password": "superadmin123",
                "role": UserRole.SUPER_ADMIN,
                "referral": "REF-ADMIN001"
            },
            {
                "email": "superadmin@example.com",
                "password": "superadmin123",
                "role": UserRole.SUPER_ADMIN,
                "referral": "REF-SUPERADM"
            },
            {
                "email": "trader@example.com",
                "password": "password123",
                "role": UserRole.TRADER,
                "referral": "REF-TRADER01"
            },
            {
                "email": "partner@trading.com",
                "password": "partner123",
                "role": UserRole.PARTNER,
                "referral": "REF-PARTNER77"
            },
            {
                "email": "user@trading.com",
                "password": "user123",
                "role": UserRole.USER,
                "referral": "REF-CLIENT01"
            }
        ]

        for u in users_to_seed:
            stmt = select(User).where(User.email == u["email"])
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                user = User(
                    email=u["email"],
                    password_hash=hash_password(u["password"]),
                    role=u["role"],
                    is_active=True,
                    referral_code=u["referral"]
                )
                db.add(user)
                await db.flush()
            else:
                user.password_hash = hash_password(u["password"])
                user.is_active = True
                db.add(user)
                await db.flush()

            # Ensure wallet exists for user
            wallet_stmt = select(Wallet).where(Wallet.user_id == user.id)
            wallet_res = await db.execute(wallet_stmt)
            if not wallet_res.scalar_one_or_none():
                wallet = Wallet(user_id=user.id, balance=Decimal("100000.00"), currency="INR")
                db.add(wallet)

        # Seed default plans
        plans_to_seed = [
            {
                "code": "FREE",
                "name": "Free Trial Plan",
                "monthly_price": Decimal("0.00"),
                "gst_percentage": Decimal("18.00"),
                "min_wallet_balance": Decimal("0.00"),
                "max_active_strategies": 1,
                "max_strategy_executions_per_day": 1,
                "subscription_type": "MONTHLY",
                "is_active": True
            },
            {
                "code": "PREMIUM",
                "name": "Premium Trading Plan",
                "monthly_price": Decimal("999.00"),
                "gst_percentage": Decimal("18.00"),
                "min_wallet_balance": Decimal("500.00"),
                "max_active_strategies": 10,
                "max_strategy_executions_per_day": 3,
                "subscription_type": "MONTHLY",
                "is_active": True
            }
        ]
        for p in plans_to_seed:
            p_stmt = select(Plan).where(Plan.code == p["code"])
            p_res = await db.execute(p_stmt)
            existing_p = p_res.scalar_one_or_none()
            if not existing_p:
                plan = Plan(**p)
                db.add(plan)

        await db.commit()
        print("Successfully seeded/updated users, wallets, and plans in PostgreSQL!")

if __name__ == "__main__":
    asyncio.run(seed_initial_users())
