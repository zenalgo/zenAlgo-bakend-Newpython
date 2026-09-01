import json
import logging
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.redis import redis_manager
from app.strategies.models import StrategyExecution
from app.strategies.exits.schemas import TrailingStopState

logger = logging.getLogger(__name__)

class TrailingStateManager:
    """
    Manages dual-tier trailing stop loss state:
    1. Redis: Microsecond in-memory evaluation state.
    2. PostgreSQL / execution_logs: Durable checkpoints that survive application restart.
    """

    @classmethod
    def _redis_key(cls, execution_id: int) -> str:
        return f"state:trailing:{execution_id}"

    @classmethod
    async def get_state(
        cls,
        db: AsyncSession,
        execution_id: int,
        default_state: Optional[TrailingStopState] = None
    ) -> Optional[TrailingStopState]:
        """
        Retrieves trailing state from Redis cache, falling back to PostgreSQL execution_logs on restart.
        """
        key = cls._redis_key(execution_id)

        # 1. Try Redis cache first
        try:
            raw_cached = await redis_manager.client.get(key)
            if raw_cached:
                cached_dict = json.loads(raw_cached)
                return TrailingStopState.model_validate(cached_dict)
        except Exception as e:
            logger.debug("Redis trailing state cache read exception for execution %s: %s", execution_id, str(e))

        # 2. Fallback to PostgreSQL execution_logs
        try:
            stmt = select(StrategyExecution).where(StrategyExecution.id == execution_id)
            res = await db.execute(stmt)
            execution = res.scalar_one_or_none()
            if execution and execution.execution_logs:
                logs_data = execution.execution_logs if isinstance(execution.execution_logs, dict) else {}
                if isinstance(execution.execution_logs, str):
                    try:
                        logs_data = json.loads(execution.execution_logs)
                    except Exception:
                        logs_data = {}
                
                if "trailing_state" in logs_data:
                    state_dict = logs_data["trailing_state"]
                    recovered_state = TrailingStopState.model_validate(state_dict)
                    # Warm Redis cache
                    await cls.save_state(db, recovered_state, persist_db=False)
                    return recovered_state
        except Exception as e:
            logger.warning("Database trailing state recovery exception for execution %s: %s", execution_id, str(e))

        # 3. Default fallback
        if default_state:
            await cls.save_state(db, default_state, persist_db=True)
            return default_state

        return None

    @classmethod
    async def save_state(
        cls,
        db: AsyncSession,
        state: TrailingStopState,
        persist_db: bool = True
    ) -> None:
        """
        Saves trailing state to Redis and optionally checkpoints to PostgreSQL execution_logs.
        """
        key = cls._redis_key(state.execution_id)
        state_dict = json.loads(state.model_dump_json())

        # 1. Save to Redis with 7-day TTL
        try:
            await redis_manager.client.setex(key, 604800, json.dumps(state_dict))
        except Exception as e:
            logger.debug("Redis trailing state write exception for execution %s: %s", state.execution_id, str(e))

        # 2. Durable checkpoint to PostgreSQL
        if persist_db:
            try:
                stmt = select(StrategyExecution).where(StrategyExecution.id == state.execution_id)
                res = await db.execute(stmt)
                execution = res.scalar_one_or_none()
                if execution:
                    current_logs = {}
                    if execution.execution_logs:
                        if isinstance(execution.execution_logs, dict):
                            current_logs = execution.execution_logs
                        elif isinstance(execution.execution_logs, str):
                            try:
                                current_logs = json.loads(execution.execution_logs)
                            except Exception:
                                current_logs = {"legacy_log": execution.execution_logs}
                    
                    current_logs["trailing_state"] = state_dict
                    execution.execution_logs = json.dumps(current_logs)
                    db.add(execution)
                    await db.flush()
            except Exception as e:
                logger.warning("Database trailing state checkpoint exception for execution %s: %s", state.execution_id, str(e))

trailing_state_manager = TrailingStateManager()
