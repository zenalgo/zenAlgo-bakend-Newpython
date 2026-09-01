import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.brokers.registry import broker_registry
from app.brokers.base.schemas import OrderRequest, OrderResult
from app.brokers.models import UserOrder
from app.brokers.service import get_active_broker_for_user
from app.strategies.models import Strategy, StrategyVersion, StrategyLeg, StrategyExecution, StrategyExecutionLeg
from app.execution.models import StrategySignal, StrategyUserExecutionTrace
from app.execution.enums import ExecutionStatus, ExecutionMode, LegRole
from app.execution.contracts import (
    LogicalLeg,
    ExecutionRequest,
    ExecutionLegResult,
    ExecutionResult
)
from app.execution.validator import ExecutionValidator, ExecutionValidationResult
from app.execution.positions.tracker import PositionTracker

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """
    Core trade execution service for MOCK and PAPER modes.
    Enforces that NO broker order can be placed without prior ExecutionValidator approval.
    Provides complete multi-leg package execution, idempotency, and audit persistence.
    """

    @classmethod
    async def execute(
        cls,
        db: AsyncSession,
        request: ExecutionRequest
    ) -> ExecutionResult:
        """
        Main entry point for executing an approved ExecutionRequest.
        """
        correlation_id = request.correlation_id or f"EXEC-{uuid.uuid4().hex[:8]}"
        log_meta = {
            "event": "execution_started",
            "strategy_id": request.strategy_id,
            "strategy_version_id": request.strategy_version_id,
            "signal_id": request.signal_id,
            "user_id": request.user_id,
            "correlation_id": correlation_id,
            "execution_mode": request.execution_mode.value
        }
        logger.info(
            "execution_started: strategy_id=%s version_id=%s signal_id=%s user_id=%s",
            request.strategy_id, request.strategy_version_id, request.signal_id, request.user_id,
            extra=log_meta
        )

        # 1. MANDATORY SAFETY GATE: ExecutionValidator Check
        val_res: ExecutionValidationResult = await ExecutionValidator.validate_execution_request(db, request)
        if not val_res.is_valid:
            logger.warning(
                "execution_validation_failed: failure_code=%s reason=%s",
                val_res.failure_code, val_res.reason,
                extra={**log_meta, "event": "execution_validation_failed", "failure_code": val_res.failure_code, "reason": val_res.reason}
            )
            # ZERO BROKER CALLS ON VALIDATION FAILURE
            return ExecutionResult(
                user_id=request.user_id,
                strategy_id=request.strategy_id,
                strategy_version_id=request.strategy_version_id,
                signal_id=request.signal_id,
                correlation_id=correlation_id,
                status=ExecutionStatus.REJECTED,
                rejection_reason=f"[{val_res.failure_code}] {val_res.reason}"
            )

        signal: StrategySignal = val_res.signal
        trace: StrategyUserExecutionTrace = val_res.trace

        # 2. Resolve Broker Adapter & Account
        broker_code = "MOCK"
        broker_account = None
        broker_credentials = {"clientId": f"MOCK_USER_{request.user_id}", "accessToken": "MOCK_TOKEN"}

        try:
            # Check if user has an active registered broker account
            broker_account = await get_active_broker_for_user(db, request.user_id)
            if broker_account and request.execution_mode == ExecutionMode.LIVE:
                broker_code = broker_account.broker_code.upper()
                broker_credentials = broker_account.get_credentials()
            elif broker_account:
                # In PAPER / MOCK mode, route safely to MOCK adapter
                broker_code = "MOCK"
        except Exception:
            # Fallback to Mock adapter in Mock/Paper mode
            broker_code = "MOCK"

        broker_adapter = broker_registry.get(broker_code)

        # 3. Create StrategyExecution Record
        execution = StrategyExecution(
            strategy_id=request.strategy_id,
            strategy_version_id=request.strategy_version_id,
            user_id=request.user_id,
            execution_trace_id=trace.id if trace else None,
            status="RUNNING",
            entry_time=datetime.now(timezone.utc),
            realized_pnl=Decimal("0.00"),
            unrealized_pnl=Decimal("0.00")
        )
        db.add(execution)
        await db.flush()

        log_meta["execution_id"] = execution.id

        # 4. Resolve / Prepare Strategy Legs
        stmt_strat_legs = select(StrategyLeg).where(StrategyLeg.strategy_version_id == request.strategy_version_id).order_by(StrategyLeg.sequence.asc())
        res_strat_legs = await db.execute(stmt_strat_legs)
        existing_strat_legs = {sl.sequence: sl for sl in res_strat_legs.scalars().all()}

        leg_results: List[ExecutionLegResult] = []
        all_legs_successful = True
        package_rejection_reason: Optional[str] = None

        # Sort legs by sequence (Hedge legs execute first in sequence 1)
        sorted_legs = sorted(request.legs, key=lambda l: l.sequence)

        # 5. Execute Each Leg in Sequence
        for leg in sorted_legs:
            leg_corr_id = f"{correlation_id}-LEG-{leg.leg_id}"
            
            # Map/Ensure database StrategyLeg exists for foreign key constraint
            db_strat_leg = existing_strat_legs.get(leg.sequence)
            if not db_strat_leg:
                db_strat_leg = StrategyLeg(
                    strategy_version_id=request.strategy_version_id,
                    sequence=leg.sequence,
                    segment=leg.segment,
                    side=leg.side.upper(),
                    strike_selection=leg.strike_policy.value,
                    expiry=leg.expiry_policy.value,
                    lots=leg.lots
                )
                db.add(db_strat_leg)
                await db.flush()
                existing_strat_legs[leg.sequence] = db_strat_leg

            # Sizing multiplier: 50 for NIFTY, 250 for RELIANCE
            lot_multiplier = 250 if request.underlying.upper() == "RELIANCE" else 50
            quantity = leg.lots * lot_multiplier

            trading_symbol = f"{request.underlying}_{leg.option_type or 'OPT'}_{leg.strike_policy.value}"
            security_id = f"SEC_{trading_symbol}"

            # Create StrategyExecutionLeg in PENDING state
            exec_leg = StrategyExecutionLeg(
                strategy_execution_id=execution.id,
                strategy_leg_id=db_strat_leg.id,
                correlation_id=leg_corr_id,
                status="PENDING",
                quantity=quantity,
                requested_quantity=quantity,
                filled_quantity=0,
                remaining_quantity=quantity,
                price=Decimal("0.00"),
                requested_price=Decimal("0.00"),
                average_fill_price=Decimal("0.00")
            )
            db.add(exec_leg)
            await db.flush()

            leg_log_meta = {
                **log_meta,
                "leg_id": leg.leg_id,
                "sequence": leg.sequence,
                "role": leg.role.value,
                "side": leg.side,
                "quantity": quantity,
                "trading_symbol": trading_symbol
            }

            # Build Normalized OrderRequest
            order_req = OrderRequest(
                trading_symbol=trading_symbol,
                security_id=security_id,
                transaction_type=leg.side.upper(),
                order_type=leg.order_type.value,
                product_type="MIS" if request.signal_type == "ENTRY" else "NRML",
                quantity=quantity,
                price=Decimal("0.0"),
                validity="DAY"
            )

            # Broker Order Submission
            logger.info(
                "broker_call_started: broker=%s symbol=%s side=%s qty=%s",
                broker_code, trading_symbol, leg.side, quantity,
                extra={**leg_log_meta, "event": "broker_call_started", "broker": broker_code}
            )

            try:
                order_res: OrderResult = await broker_adapter.place_order(
                    account=broker_account,
                    credentials=broker_credentials,
                    order_req=order_req
                )

                if order_res.order_status in ["SUCCESS", "OPEN", "FILLED"]:
                    exec_leg.broker_order_id = order_res.broker_order_id
                    exec_leg.status = "FILLED"
                    exec_leg.filled_quantity = quantity
                    exec_leg.remaining_quantity = 0
                    exec_leg.average_fill_price = Decimal("100.00") # Simulated fill price
                    
                    db.add(exec_leg)

                    # Persist UserOrder audit record
                    user_order = UserOrder(
                        user_id=request.user_id,
                        broker_name=broker_code,
                        broker_order_id=order_res.broker_order_id,
                        correlation_id=leg_corr_id,
                        trading_symbol=trading_symbol,
                        security_id=security_id,
                        exchange_segment="NSE_FNO",
                        transaction_type=leg.side.upper(),
                        order_type=leg.order_type.value,
                        product_type="MIS" if request.signal_type == "ENTRY" else "NRML",
                        quantity=quantity,
                        requested_quantity=quantity,
                        filled_quantity=quantity,
                        remaining_quantity=0,
                        price=Decimal("100.00"),
                        requested_price=Decimal("0.00"),
                        average_fill_price=Decimal("100.00"),
                        order_status="FILLED"
                    )
                    db.add(user_order)
                    await db.flush()

                    logger.info(
                        "order_filled: broker_order_id=%s symbol=%s qty=%s fill_price=%s",
                        order_res.broker_order_id, trading_symbol, quantity, exec_leg.average_fill_price,
                        extra={**leg_log_meta, "event": "order_filled", "order_id": order_res.broker_order_id}
                    )

                    leg_results.append(ExecutionLegResult(
                        leg_id=leg.leg_id,
                        broker_order_id=order_res.broker_order_id,
                        correlation_id=leg_corr_id,
                        status=ExecutionStatus.FILLED,
                        filled_quantity=quantity,
                        remaining_quantity=0,
                        average_fill_price=exec_leg.average_fill_price,
                        submitted_at=datetime.now(timezone.utc),
                        filled_at=datetime.now(timezone.utc)
                    ))
                else:
                    # Broker Rejected Order
                    exec_leg.status = "REJECTED"
                    exec_leg.rejection_reason = order_res.message or "Broker order rejected"
                    db.add(exec_leg)
                    all_legs_successful = False
                    package_rejection_reason = exec_leg.rejection_reason

                    logger.warning(
                        "broker_call_failed: reason=%s",
                        exec_leg.rejection_reason,
                        extra={**leg_log_meta, "event": "broker_call_failed", "reason": exec_leg.rejection_reason}
                    )

                    leg_results.append(ExecutionLegResult(
                        leg_id=leg.leg_id,
                        broker_order_id=order_res.broker_order_id,
                        correlation_id=leg_corr_id,
                        status=ExecutionStatus.REJECTED,
                        rejection_reason=exec_leg.rejection_reason
                    ))
                    break # Stop multi-leg sequencing on failure

            except Exception as e:
                exec_leg.status = "FAILED"
                exec_leg.rejection_reason = str(e)
                db.add(exec_leg)
                all_legs_successful = False
                package_rejection_reason = str(e)

                logger.error(
                    "broker_call_failed: exception=%s",
                    str(e),
                    extra={**leg_log_meta, "event": "broker_call_failed", "error": str(e)}
                )

                leg_results.append(ExecutionLegResult(
                    leg_id=leg.leg_id,
                    correlation_id=leg_corr_id,
                    status=ExecutionStatus.FAILED,
                    rejection_reason=str(e)
                ))
                break

        # 6. Finalize Package Status
        if all_legs_successful:
            execution.status = "RUNNING"
            if trace:
                trace.status = "EXECUTED"
                trace.execution_id = execution.id
                trace.completed_at = datetime.now(timezone.utc)
                db.add(trace)

            db.add(execution)
            await db.flush()

            logger.info(
                "execution_completed: execution_id=%s status=FILLED legs_count=%s",
                execution.id, len(leg_results),
                extra={**log_meta, "event": "execution_completed", "status": "FILLED"}
            )

            final_result = ExecutionResult(
                user_id=request.user_id,
                strategy_id=request.strategy_id,
                strategy_version_id=request.strategy_version_id,
                signal_id=request.signal_id,
                execution_id=execution.id,
                correlation_id=correlation_id,
                status=ExecutionStatus.FILLED,
                leg_results=leg_results,
                total_filled_quantity=sum(lr.filled_quantity for lr in leg_results),
                completed_at=datetime.now(timezone.utc)
            )

            # Establish and synchronize Position Lifecycle
            await PositionTracker.open_position_from_execution(db, final_result, request)

            return final_result
        else:
            execution.status = "FAILED"
            if trace:
                trace.status = "FAILED"
                trace.failure_code = "BROKER_REJECTION"
                trace.failure_reason = package_rejection_reason
                trace.completed_at = datetime.now(timezone.utc)
                db.add(trace)

            db.add(execution)
            await db.flush()

            logger.warning(
                "execution_failed: execution_id=%s reason=%s",
                execution.id, package_rejection_reason,
                extra={**log_meta, "event": "execution_failed", "reason": package_rejection_reason}
            )

            return ExecutionResult(
                user_id=request.user_id,
                strategy_id=request.strategy_id,
                strategy_version_id=request.strategy_version_id,
                signal_id=request.signal_id,
                execution_id=execution.id,
                correlation_id=correlation_id,
                status=ExecutionStatus.FAILED,
                leg_results=leg_results,
                rejection_reason=package_rejection_reason,
                completed_at=datetime.now(timezone.utc)
            )

execution_engine = ExecutionEngine()
