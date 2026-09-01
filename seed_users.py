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

async def seed_initial_users():
    async with AsyncSessionLocal() as db:
        users_to_seed = [
            {
                "email": "superadmin@trading.com",
                "password": "SuperAdminPass123!",
                "role": UserRole.SUPER_ADMIN,
                "referral": "REF-ADMIN001"
            },
            {
                "email": "superadmin@example.com",
                "password": "Z3nAlG0_Sup3rAdm1n_2026!",
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
            existing = res.scalar_one_or_none()

            if not existing:
                user = User(
                    email=u["email"],
                    password_hash=hash_password(u["password"]),
                    role=u["role"],
                    is_active=True,
                    referral_code=u["referral"]
                )
                db.add(user)
            else:
                existing.password_hash = hash_password(u["password"])
                existing.is_active = True
                db.add(existing)

        await db.commit()
        print("Successfully seeded/updated users in PostgreSQL!")

if __name__ == "__main__":
    asyncio.run(seed_initial_users())
