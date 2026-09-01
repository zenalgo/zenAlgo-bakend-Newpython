from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List, Optional
from app.strategies.models import Strategy, StrategyVersion
from app.users.models import User

class StrategyRepository:
    @staticmethod
    async def get_strategy_by_id(db: AsyncSession, strategy_id: int) -> Optional[Strategy]:
        stmt = select(Strategy).where(Strategy.id == strategy_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_strategy_by_id_and_user(db: AsyncSession, strategy_id: int, user_id: int) -> Optional[Strategy]:
        stmt = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_strategies_by_user(db: AsyncSession, user_id: int, page: int, size: int) -> List[Strategy]:
        stmt = (
            select(Strategy)
            .where(Strategy.user_id == user_id)
            .order_by(Strategy.id.desc())
            .offset(page * size)
            .limit(size)
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def count_strategies_by_user(db: AsyncSession, user_id: int) -> int:
        stmt = select(func.count(Strategy.id)).where(Strategy.user_id == user_id)
        res = await db.execute(stmt)
        return res.scalar() or 0

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()
