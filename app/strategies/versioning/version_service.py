from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import exists
from app.strategies.models import StrategyExecution

class VersionService:
    @staticmethod
    async def is_version_immutable(db: AsyncSession, version_id: int) -> bool:
        """Determines if a StrategyVersion has any executing orders or runs (immutability check)."""
        if not version_id:
            return False
        stmt = select(exists().where(StrategyExecution.strategy_version_id == version_id))
        res = await db.execute(stmt)
        return res.scalar()
