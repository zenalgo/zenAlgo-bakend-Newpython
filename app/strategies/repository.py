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
    async def get_strategy_by_id_and_user(db: AsyncSession, strategy_id: int, user_id: Optional[int] = None, is_admin: bool = False) -> Optional[Strategy]:
        if is_admin or user_id is None:
            stmt = select(Strategy).where(Strategy.id == strategy_id)
        else:
            stmt = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user_id)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_strategies_by_user(
        db: AsyncSession,
        user_id: Optional[int] = None,
        page: int = 0,
        size: int = 20,
        search: Optional[str] = None,
        mode: Optional[str] = None,
        status: Optional[str] = None,
        is_admin: bool = False
    ) -> List[Strategy]:
        stmt = select(Strategy)
        if not is_admin and user_id is not None:
            stmt = stmt.where(Strategy.user_id == user_id)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(Strategy.name.ilike(term) | Strategy.description.ilike(term))
        if mode:
            stmt = stmt.where(Strategy.mode == mode.upper())
        if status:
            stmt = stmt.where(Strategy.status == status.upper())

        stmt = stmt.order_by(Strategy.id.desc()).offset(page * size).limit(size)
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
