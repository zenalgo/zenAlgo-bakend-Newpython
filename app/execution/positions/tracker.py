import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.strategies.models import StrategyExecution, StrategyExecutionLeg, StrategyRuntimeState
from app.brokers.models import UserPosition
from app.execution.enums import ExecutionStatus, LegRole
from app.execution.contracts import ExecutionRequest, ExecutionResult, ExecutionLegResult
from app.strategies.enums import StrategyLifecycleState
from app.strategies.state_manager import strategy_state_manager

logger = logging.getLogger(__name__)

class PositionTracker:
    """
    Authoritative position lifecycle coordinator.
    Consumes confirmed ExecutionResult(status=FILLED) to establish and track strategy positions.
    Synchronizes broker account level UserPosition ledgers and transitions StrategyRuntimeState
    from ORDER_PENDING -> POSITION_OPEN -> MONITORING_EXIT.
    """

    @classmethod
    async def open_position_from_execution(
        cls,
        db: AsyncSession,
        execution_result: ExecutionResult,
        request: ExecutionRequest
    ) -> Optional[StrategyExecution]:
        """
        Processes a confirmed ExecutionResult and opens the canonical strategy position.
        Guarantees that unconfirmed, rejected, or incomplete executions NEVER open a position.
        """
        correlation_id = execution_result.correlation_id or request.correlation_id
        log_meta = {
            "event": "position_opening_started",
            "strategy_id": request.strategy_id,
            "strategy_version_id": request.strategy_version_id,
            "signal_id": request.signal_id,
            "user_id": request.user_id,
            "execution_id": execution_result.execution_id,
            "correlation_id": correlation_id
        }
        logger.info(
            "position_opening_started: strategy_id=%s version_id=%s signal_id=%s user_id=%s execution_id=%s",
            request.strategy_id, request.strategy_version_id, request.signal_id, request.user_id, execution_result.execution_id,
            extra=log_meta
        )

        # 1. CRITICAL SAFETY GUARD: Only ExecutionStatus.FILLED can proceed
        if execution_result.status != ExecutionStatus.FILLED or not execution_result.execution_id:
            logger.warning(
                "position_opening_failed: execution not filled (status=%s)",
                execution_result.status.value if hasattr(execution_result.status, "value") else execution_result.status,
                extra={**log_meta, "event": "position_opening_failed", "status": str(execution_result.status)}
            )
            return None

        # 2. Package Completeness Check for Multi-Leg (Strategy 3)
        if len(request.legs) > 1:
            if len(execution_result.leg_results) < len(request.legs):
                logger.error(
                    "position_opening_failed: incomplete multi-leg package (expected %s legs, got %s)",
                    len(request.legs), len(execution_result.leg_results),
                    extra={**log_meta, "event": "position_opening_failed", "reason": "INCOMPLETE_MULTI_LEG_PACKAGE"}
                )
                return None

            # All legs must be confirmed FILLED
            for leg_res in execution_result.leg_results:
                if leg_res.status != ExecutionStatus.FILLED or leg_res.filled_quantity <= 0:
                    logger.error(
                        "position_opening_failed: leg %s not filled (status=%s)",
                        leg_res.leg_id, leg_res.status,
                        extra={**log_meta, "event": "position_opening_failed", "leg_id": leg_res.leg_id}
                    )
                    return None

        # 3. Retrieve and Validate StrategyExecution
        stmt_exec = select(StrategyExecution).where(StrategyExecution.id == execution_result.execution_id)
        res_exec = await db.execute(stmt_exec)
        execution = res_exec.scalar_one_or_none()

        if not execution:
            logger.error(
                "position_opening_failed: StrategyExecution ID %s not found",
                execution_result.execution_id,
                extra={**log_meta, "event": "position_opening_failed", "reason": "EXECUTION_NOT_FOUND"}
            )
            return None

        # 4. Synchronize UserPosition (Broker Account Ledger) for each leg
        broker_name = "MOCK" if request.execution_mode.value in ["MOCK", "PAPER"] else "DHAN"
        
        for leg_res in execution_result.leg_results:
            # Find matching logical leg request
            matched_leg_req = next((l for l in request.legs if l.leg_id == leg_res.leg_id), None)
            if not matched_leg_req:
                continue

            trading_symbol = f"{request.underlying}_{matched_leg_req.option_type or 'OPT'}_{matched_leg_req.strike_policy.value}"
            security_id = f"SEC_{trading_symbol}"

            await cls._sync_user_position(
                db=db,
                user_id=request.user_id,
                broker_name=broker_name,
                trading_symbol=trading_symbol,
                security_id=security_id,
                side=matched_leg_req.side.upper(),
                filled_qty=leg_res.filled_quantity,
                avg_price=leg_res.average_fill_price
            )

        # 5. Advance StrategyRuntimeState: ORDER_PENDING -> POSITION_OPEN -> MONITORING_EXIT
        await cls._transition_runtime_state(db, request.strategy_id, request.strategy_version_id, execution.id, log_meta)

        logger.info(
            "position_opened: execution_id=%s strategy_id=%s user_id=%s filled_qty=%s",
            execution.id, request.strategy_id, request.user_id, execution_result.total_filled_quantity,
            extra={
                **log_meta,
                "event": "position_opened",
                "filled_quantity": execution_result.total_filled_quantity,
                "status": "RUNNING"
            }
        )

        return execution

    @classmethod
    async def _sync_user_position(
        cls,
        db: AsyncSession,
        user_id: int,
        broker_name: str,
        trading_symbol: str,
        security_id: str,
        side: str,
        filled_qty: int,
        avg_price: Decimal
    ) -> UserPosition:
        """
        Synchronizes or updates the broker-level UserPosition record without corrupting existing positions.
        """
        stmt = select(UserPosition).where(
            UserPosition.user_id == user_id,
            UserPosition.broker_name == broker_name,
            UserPosition.security_id == security_id,
            UserPosition.position_type == "INTRADAY"
        )
        res = await db.execute(stmt)
        user_pos = res.scalar_one_or_none()

        if user_pos:
            # Update existing broker position
            if side == "BUY":
                new_buy_qty = (user_pos.buy_qty or 0) + filled_qty
                current_total_cost = (user_pos.buy_avg or Decimal("0.00")) * Decimal(user_pos.buy_qty or 0)
                new_leg_cost = avg_price * Decimal(filled_qty)
                user_pos.buy_avg = (current_total_cost + new_leg_cost) / Decimal(new_buy_qty) if new_buy_qty > 0 else avg_price
                user_pos.buy_qty = new_buy_qty
                user_pos.net_qty = (user_pos.net_qty or 0) + filled_qty
            elif side == "SELL":
                new_sell_qty = (user_pos.sell_qty or 0) + filled_qty
                current_total_cost = (user_pos.sell_avg or Decimal("0.00")) * Decimal(user_pos.sell_qty or 0)
                new_leg_cost = avg_price * Decimal(filled_qty)
                user_pos.sell_avg = (current_total_cost + new_leg_cost) / Decimal(new_sell_qty) if new_sell_qty > 0 else avg_price
                user_pos.sell_qty = new_sell_qty
                user_pos.net_qty = (user_pos.net_qty or 0) - filled_qty
            
            user_pos.synced_at = datetime.now(timezone.utc)
            db.add(user_pos)
        else:
            # Create new broker position row
            buy_qty = filled_qty if side == "BUY" else 0
            sell_qty = filled_qty if side == "SELL" else 0
            buy_avg = avg_price if side == "BUY" else Decimal("0.00")
            sell_avg = avg_price if side == "SELL" else Decimal("0.00")
            net_qty = filled_qty if side == "BUY" else -filled_qty

            user_pos = UserPosition(
                user_id=user_id,
                broker_name=broker_name,
                trading_symbol=trading_symbol,
                security_id=security_id,
                position_type="INTRADAY",
                exchange_segment="NSE_FNO",
                product_type="MIS",
                net_qty=net_qty,
                buy_qty=buy_qty,
                sell_qty=sell_qty,
                buy_avg=buy_avg,
                sell_avg=sell_avg,
                realized_profit=Decimal("0.00"),
                unrealized_profit=Decimal("0.00"),
                synced_at=datetime.now(timezone.utc)
            )
            db.add(user_pos)

        await db.flush()
        return user_pos

    @classmethod
    async def _transition_runtime_state(
        cls,
        db: AsyncSession,
        strategy_id: int,
        strategy_version_id: int,
        execution_id: int,
        log_meta: dict
    ) -> None:
        """
        Advances the StrategyRuntimeState through the valid state machine path:
        ORDER_PENDING -> POSITION_OPEN -> MONITORING_EXIT.
        """
        try:
            runtime_state = await strategy_state_manager.get_runtime_state(db, strategy_id)
            if not runtime_state:
                return

            current = runtime_state.lifecycle_state

            # If waiting / monitoring entry / entry signal, transition to ORDER_PENDING first if needed
            if current == StrategyLifecycleState.MONITORING_ENTRY:
                await strategy_state_manager.transition_state(
                    db=db,
                    strategy_id=strategy_id,
                    strategy_version_id=strategy_version_id,
                    new_state=StrategyLifecycleState.ENTRY_SIGNAL,
                    reason=f"Entry signal triggered for Execution {execution_id}"
                )
                current = StrategyLifecycleState.ENTRY_SIGNAL

            if current == StrategyLifecycleState.ENTRY_SIGNAL:
                await strategy_state_manager.transition_state(
                    db=db,
                    strategy_id=strategy_id,
                    strategy_version_id=strategy_version_id,
                    new_state=StrategyLifecycleState.ORDER_PENDING,
                    reason=f"Order submitted for Execution {execution_id}"
                )
                current = StrategyLifecycleState.ORDER_PENDING

            if current == StrategyLifecycleState.ORDER_PENDING:
                # Transition ORDER_PENDING -> POSITION_OPEN
                await strategy_state_manager.transition_state(
                    db=db,
                    strategy_id=strategy_id,
                    strategy_version_id=strategy_version_id,
                    new_state=StrategyLifecycleState.POSITION_OPEN,
                    reason=f"Position confirmed filled via Execution {execution_id}"
                )
                current = StrategyLifecycleState.POSITION_OPEN

            if current == StrategyLifecycleState.POSITION_OPEN:
                # Transition POSITION_OPEN -> MONITORING_EXIT
                await strategy_state_manager.transition_state(
                    db=db,
                    strategy_id=strategy_id,
                    strategy_version_id=strategy_version_id,
                    new_state=StrategyLifecycleState.MONITORING_EXIT,
                    reason=f"Started monitoring position for exits (Execution {execution_id})"
                )
                logger.info(
                    "position_monitoring_started: strategy_id=%s version_id=%s execution_id=%s state=MONITORING_EXIT",
                    strategy_id, strategy_version_id, execution_id,
                    extra={**log_meta, "event": "position_monitoring_started", "state": "MONITORING_EXIT"}
                )
        except Exception as e:
            logger.warning("Runtime state transition warning during position opening: %s", str(e))

position_tracker = PositionTracker()
