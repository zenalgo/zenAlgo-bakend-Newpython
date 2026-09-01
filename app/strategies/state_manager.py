from datetime import datetime, timezone
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.strategies.models import StrategyRuntimeState, Strategy
from app.strategies.enums import StrategyLifecycleState
from app.core.exceptions import ResourceNotFoundError, ValidationError

logger = logging.getLogger(__name__)

# State transitions mapping: Key is the 'From State', value is a set of valid 'To States'
VALID_TRANSITIONS = {
    StrategyLifecycleState.WAITING: {
        StrategyLifecycleState.ELIGIBLE,
        StrategyLifecycleState.PAUSED,
        StrategyLifecycleState.ERROR,
        StrategyLifecycleState.RECONCILIATION_REQUIRED
    },
    StrategyLifecycleState.ELIGIBLE: {
        StrategyLifecycleState.MONITORING_ENTRY,
        StrategyLifecycleState.PAUSED,
        StrategyLifecycleState.ERROR,
        StrategyLifecycleState.RECONCILIATION_REQUIRED
    },
    StrategyLifecycleState.MONITORING_ENTRY: {
        StrategyLifecycleState.ENTRY_SIGNAL,
        StrategyLifecycleState.PAUSED,
        StrategyLifecycleState.ERROR,
        StrategyLifecycleState.RECONCILIATION_REQUIRED
    },
    StrategyLifecycleState.ENTRY_SIGNAL: {
        StrategyLifecycleState.ORDER_PENDING,
        StrategyLifecycleState.MONITORING_ENTRY, # Revert if signal cancelled/rejected
        StrategyLifecycleState.PAUSED,
        StrategyLifecycleState.ERROR,
        StrategyLifecycleState.RECONCILIATION_REQUIRED
    },
    StrategyLifecycleState.ORDER_PENDING: {
        StrategyLifecycleState.POSITION_OPEN,
        StrategyLifecycleState.MONITORING_EXIT,
        StrategyLifecycleState.MONITORING_ENTRY, # Revert if broker rejects the order completely
        StrategyLifecycleState.PAUSED,
        StrategyLifecycleState.ERROR,
        StrategyLifecycleState.RECONCILIATION_REQUIRED
    },
    StrategyLifecycleState.POSITION_OPEN: {
        StrategyLifecycleState.MONITORING_EXIT,
        StrategyLifecycleState.PAUSED,
        StrategyLifecycleState.ERROR,
        StrategyLifecycleState.RECONCILIATION_REQUIRED
    },
    StrategyLifecycleState.MONITORING_EXIT: {
        StrategyLifecycleState.EXIT_SIGNAL,
        StrategyLifecycleState.PAUSED,
        StrategyLifecycleState.ERROR,
        StrategyLifecycleState.RECONCILIATION_REQUIRED
    },
    StrategyLifecycleState.EXIT_SIGNAL: {
        StrategyLifecycleState.EXIT_ORDER_PENDING,
        StrategyLifecycleState.PAUSED,
        StrategyLifecycleState.ERROR,
        StrategyLifecycleState.RECONCILIATION_REQUIRED
    },
    StrategyLifecycleState.EXIT_ORDER_PENDING: {
        StrategyLifecycleState.POSITION_CLOSED,
        StrategyLifecycleState.PAUSED,
        StrategyLifecycleState.ERROR,
        StrategyLifecycleState.RECONCILIATION_REQUIRED
    },
    StrategyLifecycleState.POSITION_CLOSED: {
        StrategyLifecycleState.WAITING,
        StrategyLifecycleState.PAUSED,
        StrategyLifecycleState.ERROR,
        StrategyLifecycleState.RECONCILIATION_REQUIRED
    },
    StrategyLifecycleState.PAUSED: {
        StrategyLifecycleState.ERROR,
        StrategyLifecycleState.RECONCILIATION_REQUIRED,
        StrategyLifecycleState.WAITING
    },
    StrategyLifecycleState.ERROR: {
        StrategyLifecycleState.WAITING,
        StrategyLifecycleState.MONITORING_ENTRY,
        StrategyLifecycleState.MONITORING_EXIT,
        StrategyLifecycleState.RECONCILIATION_REQUIRED
    },
    StrategyLifecycleState.RECONCILIATION_REQUIRED: {
        StrategyLifecycleState.WAITING,
        StrategyLifecycleState.MONITORING_ENTRY,
        StrategyLifecycleState.MONITORING_EXIT,
        StrategyLifecycleState.POSITION_CLOSED
    }
}

class StrategyStateManager:
    """Single authority for managing strategy lifecycle state transitions and database row locking."""

    @staticmethod
    async def get_runtime_state(db: AsyncSession, strategy_id: int, lock: bool = False) -> StrategyRuntimeState:
        """Retrieves StrategyRuntimeState record. Uses SELECT FOR UPDATE if lock=True."""
        stmt = select(StrategyRuntimeState).where(StrategyRuntimeState.strategy_id == strategy_id)
        if lock:
            stmt = stmt.with_for_update()
        
        res = await db.execute(stmt)
        state = res.scalar_one_or_none()
        if not state:
            raise ResourceNotFoundError(f"Strategy runtime state not found for strategy_id: {strategy_id}")
        return state

    @staticmethod
    async def initialize_runtime_state(db: AsyncSession, strategy_id: int, strategy_version_id: int) -> StrategyRuntimeState:
        """Initializes a new runtime state row set to WAITING."""
        # Check parent strategy exists
        stmt_strat = select(Strategy).where(Strategy.id == strategy_id)
        res_strat = await db.execute(stmt_strat)
        if not res_strat.scalar_one_or_none():
            raise ResourceNotFoundError(f"Parent Strategy not found for strategy_id: {strategy_id}")

        # Check if runtime state already exists to avoid unique constraint violations
        stmt_exists = select(StrategyRuntimeState).where(StrategyRuntimeState.strategy_id == strategy_id)
        res_exists = await db.execute(stmt_exists)
        existing = res_exists.scalar_one_or_none()
        if existing:
            return existing

        state = StrategyRuntimeState(
            strategy_id=strategy_id,
            strategy_version_id=strategy_version_id,
            lifecycle_state=StrategyLifecycleState.WAITING
        )
        db.add(state)
        await db.flush()

        logger.info(
            f"Strategy runtime state initialized: strategy_id={strategy_id}, version_id={strategy_version_id}, state=WAITING",
            extra={
                "event": "strategy_runtime_state_initialized",
                "strategy_id": strategy_id,
                "strategy_version_id": strategy_version_id,
                "runtime_state_id": state.id,
                "initial_state": "WAITING",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        return state

    @staticmethod
    async def transition_state(
        db: AsyncSession,
        strategy_id: int,
        strategy_version_id: int,
        new_state: StrategyLifecycleState,
        reason: str,
        context: dict = None
    ) -> StrategyRuntimeState:
        """
        Transitions lifecycle state. Validates constraints, applies timestamps, 
        and writes structured audit logs.
        """
        # 1. Row Lock: Retrieve and lock current runtime state
        state = await StrategyStateManager.get_runtime_state(db, strategy_id, lock=True)

        # 2. Version Safety Check
        if state.strategy_version_id != strategy_version_id:
            raise ValidationError(
                f"Strategy version mismatch. State version: {state.strategy_version_id}, "
                f"Requested transition version: {strategy_version_id}"
            )

        prev_state = state.lifecycle_state

        # 3. Idempotent Same-State Transition NO-OP Check
        if prev_state == new_state:
            return state

        # 4. State Transition Matrix Validation
        allowed = VALID_TRANSITIONS.get(prev_state, set())
        if new_state not in allowed:
            raise ValidationError(
                f"Invalid strategy state transition from {prev_state} to {new_state}"
            )

        # 5. Apply State & Timestamps
        state.lifecycle_state = new_state
        state.last_evaluated_at = datetime.now(timezone.utc)

        # Monitoring timers tracking
        if new_state in (StrategyLifecycleState.MONITORING_ENTRY, StrategyLifecycleState.MONITORING_EXIT):
            state.monitoring_started_at = datetime.now(timezone.utc)
            state.monitoring_stopped_at = None
        elif prev_state in (StrategyLifecycleState.MONITORING_ENTRY, StrategyLifecycleState.MONITORING_EXIT):
            state.monitoring_stopped_at = datetime.now(timezone.utc)

        db.add(state)
        await db.flush()

        # 6. Structured Observability Logging
        log_extra = {
            "event": "strategy_state_changed",
            "strategy_id": strategy_id,
            "strategy_version_id": strategy_version_id,
            "runtime_state_id": state.id,
            "previous_state": prev_state.value if isinstance(prev_state, StrategyLifecycleState) else prev_state,
            "new_state": new_state.value if isinstance(new_state, StrategyLifecycleState) else new_state,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if context:
            log_extra.update(context)

        logger.info(f"Strategy state changed: {prev_state} -> {new_state}", extra=log_extra)
        return state

    @staticmethod
    async def pause_strategy(db: AsyncSession, strategy_id: int, strategy_version_id: int, reason: str) -> StrategyRuntimeState:
        """Transitions state to PAUSED, preserving the current state in paused_from_state."""
        state = await StrategyStateManager.get_runtime_state(db, strategy_id, lock=True)
        
        # 1. Version Safety
        if state.strategy_version_id != strategy_version_id:
            raise ValidationError(f"Strategy version mismatch on Pause.")

        prev_state = state.lifecycle_state
        if prev_state == StrategyLifecycleState.PAUSED:
            return state

        # 2. Update state records
        state.paused_from_state = prev_state
        state.lifecycle_state = StrategyLifecycleState.PAUSED
        state.last_evaluated_at = datetime.now(timezone.utc)
        
        if prev_state in (StrategyLifecycleState.MONITORING_ENTRY, StrategyLifecycleState.MONITORING_EXIT):
            state.monitoring_stopped_at = datetime.now(timezone.utc)

        db.add(state)
        await db.flush()

        logger.info(
            f"Strategy paused: {prev_state} -> PAUSED",
            extra={
                "event": "strategy_state_changed",
                "strategy_id": strategy_id,
                "strategy_version_id": strategy_version_id,
                "runtime_state_id": state.id,
                "previous_state": prev_state,
                "new_state": "PAUSED",
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        return state

    @staticmethod
    async def resume_strategy(db: AsyncSession, strategy_id: int, strategy_version_id: int, reason: str) -> StrategyRuntimeState:
        """Resumes strategy from PAUSED back to paused_from_state."""
        state = await StrategyStateManager.get_runtime_state(db, strategy_id, lock=True)

        if state.strategy_version_id != strategy_version_id:
            raise ValidationError(f"Strategy version mismatch on Resume.")

        if state.lifecycle_state != StrategyLifecycleState.PAUSED:
            return state

        target_state = state.paused_from_state or StrategyLifecycleState.WAITING
        # Validate target state representation
        if isinstance(target_state, str):
            target_state = StrategyLifecycleState(target_state)

        state.lifecycle_state = target_state
        state.paused_from_state = None
        state.last_evaluated_at = datetime.now(timezone.utc)

        if target_state in (StrategyLifecycleState.MONITORING_ENTRY, StrategyLifecycleState.MONITORING_EXIT):
            state.monitoring_started_at = datetime.now(timezone.utc)
            state.monitoring_stopped_at = None

        db.add(state)
        await db.flush()

        logger.info(
            f"Strategy resumed: PAUSED -> {target_state}",
            extra={
                "event": "strategy_state_changed",
                "strategy_id": strategy_id,
                "strategy_version_id": strategy_version_id,
                "runtime_state_id": state.id,
                "previous_state": "PAUSED",
                "new_state": target_state.value,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        return state

    @staticmethod
    async def mark_error(db: AsyncSession, strategy_id: int, strategy_version_id: int, reason: str, context: dict = None) -> StrategyRuntimeState:
        """Transitions state to ERROR."""
        return await StrategyStateManager.transition_state(
            db, strategy_id, strategy_version_id, StrategyLifecycleState.ERROR, reason, context
        )

    @staticmethod
    async def mark_reconciliation_required(db: AsyncSession, strategy_id: int, strategy_version_id: int, reason: str, context: dict = None) -> StrategyRuntimeState:
        """Transitions state to RECONCILIATION_REQUIRED."""
        return await StrategyStateManager.transition_state(
            db, strategy_id, strategy_version_id, StrategyLifecycleState.RECONCILIATION_REQUIRED, reason, context
        )

strategy_state_manager = StrategyStateManager
