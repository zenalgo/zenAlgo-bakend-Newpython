import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.strategies.models import StrategyEventProcessing

logger = logging.getLogger(__name__)

async def claim_strategy_event_processing(db: AsyncSession, strategy_id: int, market_event_key: str) -> bool:
    """
    Atomically attempts to record processing claim in strategy_event_processing.
    Returns True if this is the first worker to claim the event.
    Returns False if already processed or claimed by a concurrent worker.
    """
    try:
        async with db.begin_nested():
            rec = StrategyEventProcessing(
                strategy_id=strategy_id,
                market_event_key=market_event_key
            )
            db.add(rec)
            await db.flush()

        logger.debug(
            f"Strategy event claimed: strategy_id={strategy_id}, event_key={market_event_key}",
            extra={
                "event": "strategy_event_claimed",
                "strategy_id": strategy_id,
                "market_event_key": market_event_key
            }
        )
        return True
    except IntegrityError:
        # Duplicate key in strategy_event_processing
        logger.debug(
            f"Duplicate strategy event skipped: strategy_id={strategy_id}, event_key={market_event_key}",
            extra={
                "event": "strategy_event_duplicate",
                "strategy_id": strategy_id,
                "market_event_key": market_event_key
            }
        )
        return False
