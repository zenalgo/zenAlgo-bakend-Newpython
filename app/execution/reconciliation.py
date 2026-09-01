import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy.future import select

from app.core.database import AsyncSessionLocal
from app.core.redis import redis_manager
from app.strategies.models import StrategyExecutionLeg
from app.brokers.models import UserOrder, BrokerAccount
from app.brokers.service import get_active_broker_for_user
from app.brokers.registry import broker_registry

logger = logging.getLogger(__name__)

class OrderReconciliationWorker:
    """Distributed Order Reconciliation Worker running under Redis lock.
    Polls active orders in PENDING, OPEN, or UNKNOWN state every 3 seconds.
    """
    def __init__(self, poll_interval: float = 3.0):
        self.poll_interval = poll_interval
        self._is_running = False

    async def start(self):
        """Starts the reconciliation loop."""
        self._is_running = True
        logger.info("OrderReconciliationWorker started with poll_interval=%.1fs", self.poll_interval)
        while self._is_running:
            try:
                await self.reconcile_active_orders()
            except Exception as e:
                logger.error("Error in reconciliation loop: %s", str(e))
            await asyncio.sleep(self.poll_interval)

    def stop(self):
        """Stops the reconciliation loop."""
        self._is_running = False

    async def reconcile_active_orders(self):
        """Acquires Redis lock and reconciles pending/open legs."""
        async with redis_manager.lock("lock:reconciliation:worker", timeout=10.0) as acquired:
            if not acquired:
                return

            async with AsyncSessionLocal() as db:
                stmt_legs = select(StrategyExecutionLeg).where(
                    StrategyExecutionLeg.status.in_(["PENDING", "OPEN", "UNKNOWN"])
                )
                res_legs = await db.execute(stmt_legs)
                active_legs = list(res_legs.scalars().all())

                if not active_legs:
                    return

                for leg in active_legs:
                    try:
                        leg.reconciliation_attempts = (leg.reconciliation_attempts or 0) + 1
                        leg.last_reconciled_at = datetime.now(timezone.utc)

                        if leg.broker_order_id:
                            # Reconcile via broker order status
                            stmt_exec = select(StrategyExecutionLeg).where(StrategyExecutionLeg.id == leg.id)
                            # Find associated broker account
                            stmt_acc = select(BrokerAccount).where(BrokerAccount.user_id == leg.strategy_execution.user_id)
                            res_acc = await db.execute(stmt_acc)
                            account = res_acc.scalars().first()

                            if account:
                                adapter = broker_registry.get(account.broker_code)
                                order_status = await adapter.get_order_status(account, account.credentials, leg.broker_order_id)
                                leg.status = order_status.status
                                leg.filled_quantity = order_status.filled_quantity
                                leg.remaining_quantity = max(0, (leg.quantity or 0) - (order_status.filled_quantity or 0))
                                db.add(leg)
                    except Exception as ex:
                        logger.warning("Reconciliation failed for leg %s: %s", leg.id, str(ex))

                await db.commit()


order_reconciliation_worker = OrderReconciliationWorker()
