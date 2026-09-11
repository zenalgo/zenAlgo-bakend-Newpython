from decimal import Decimal
from datetime import datetime, timezone
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.settings_model import SystemSetting
from app.core.redis import redis_manager

logger = logging.getLogger(__name__)

ORDER_CAP_KEY = "MAX_ORDER_VALUE_SAFETY_CAP"
DEFAULT_ORDER_CAP = Decimal("5000.00")

class SystemSettingsService:
    @staticmethod
    async def get_max_order_value_cap(db: Optional[AsyncSession] = None) -> Decimal:
        """
        Retrieves the configured max order value safety cap.
        Checks Redis cache first, falling back to DB, then default 5000.00.
        """
        try:
            cached = await redis_manager.get(f"setting:{ORDER_CAP_KEY}")
            if cached:
                return Decimal(str(cached))
        except Exception as e:
            logger.debug(f"Redis get setting error: {e}")

        # Check DB
        if db is not None:
            stmt = select(SystemSetting).where(SystemSetting.key == ORDER_CAP_KEY)
            res = await db.execute(stmt)
            setting = res.scalar_one_or_none()
            if setting and setting.value:
                try:
                    val = Decimal(str(setting.value))
                    try:
                        await redis_manager.set(f"setting:{ORDER_CAP_KEY}", str(val), ex=300)
                    except Exception:
                        pass
                    return val
                except Exception:
                    pass
        else:
            async with AsyncSessionLocal() as session:
                stmt = select(SystemSetting).where(SystemSetting.key == ORDER_CAP_KEY)
                res = await session.execute(stmt)
                setting = res.scalar_one_or_none()
                if setting and setting.value:
                    try:
                        val = Decimal(str(setting.value))
                        try:
                            await redis_manager.set(f"setting:{ORDER_CAP_KEY}", str(val), ex=300)
                        except Exception:
                            pass
                        return val
                    except Exception:
                        pass

        return DEFAULT_ORDER_CAP

    @staticmethod
    async def set_max_order_value_cap(db: AsyncSession, new_cap: Decimal, updated_by: str = "ADMIN") -> Decimal:
        """
        Updates the max order value safety cap in DB and Redis.
        """
        if new_cap <= 0:
            raise ValueError("Safety cap must be greater than zero")

        stmt = select(SystemSetting).where(SystemSetting.key == ORDER_CAP_KEY)
        res = await db.execute(stmt)
        setting = res.scalar_one_or_none()

        cap_str = str(round(new_cap, 2))
        now = datetime.now(timezone.utc)

        if not setting:
            setting = SystemSetting(
                key=ORDER_CAP_KEY,
                value=cap_str,
                description="Platform-wide max order value safety cap in INR (per order batch execution)",
                updated_at=now,
                updated_by=updated_by
            )
            db.add(setting)
        else:
            setting.value = cap_str
            setting.updated_at = now
            setting.updated_by = updated_by
            db.add(setting)

        await db.commit()

        try:
            await redis_manager.set(f"setting:{ORDER_CAP_KEY}", cap_str, ex=3600)
        except Exception as e:
            logger.debug(f"Redis set setting error: {e}")

        logger.info(f"Updated Max Order Value Safety Cap to ₹{cap_str} by {updated_by}")
        return Decimal(cap_str)
