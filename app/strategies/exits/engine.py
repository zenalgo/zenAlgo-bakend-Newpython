import logging
import uuid
import pytz
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, date, time
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.market_data.schemas import MarketEvent
from app.strategies.models import Strategy, StrategyVersion, StrategyExecution, StrategyExecutionLeg, StrategyRuntimeState
from app.execution.models import StrategySignal
from app.strategies.enums import StrategyLifecycleState
from app.strategies.state_manager import strategy_state_manager
from app.strategies.signals.enums import SignalType, SignalDirection, SignalStatus
from app.strategies.signals.schemas import TradingSignal, build_deterministic_signal_key
from app.strategies.exits.enums import ExitType, ExitDecision, PositionDirection
from app.strategies.exits.schemas import ExitEvaluationResult, TrailingStopState
from app.strategies.exits.evaluators import (
    evaluate_stop_loss,
    evaluate_target,
    evaluate_r_multiple,
    evaluate_trailing_stop,
    evaluate_forced_time_exit,
    evaluate_expiry_exit,
    evaluate_strategy_invalidation
)
from app.strategies.exits.trailing import trailing_state_manager

logger = logging.getLogger(__name__)
ZONE_KOLKATA = pytz.timezone("Asia/Kolkata")

class ExitEngine:
    """
    Authoritative Exit Engine for active strategy positions.
    Evaluates whether an active StrategyExecution in MONITORING_EXIT state has met exit criteria.
    Emits EXIT StrategySignals downstream to RiskEngine and ExecutionEngine without placing broker orders.
    """

    @classmethod
    async def evaluate_strategy_exits(
        cls,
        db: AsyncSession,
        strategy_id: int,
        strategy_version_id: int,
        event: MarketEvent,
        forced_time_ist: Optional[time] = None,
        custom_stop_loss: Optional[Decimal] = None,
        custom_target: Optional[Decimal] = None,
        custom_r_multiple: Optional[Decimal] = None,
        enable_trailing: bool = False,
        enable_partial_1r: bool = False,
        invalidation_level: Optional[Decimal] = None,
        expiry_date_ist: Optional[date] = None
    ) -> List[TradingSignal]:
        """
        Main entry point for evaluating exits across all active user executions for a strategy.
        """
        market_event_key = f"{strategy_id}:{strategy_version_id}:EV-{event.event_id}"
        current_price = Decimal(str(event.price if event.price is not None else event.close))

        log_meta = {
            "event": "exit_evaluation_started",
            "strategy_id": strategy_id,
            "strategy_version_id": strategy_version_id,
            "event_id": event.event_id,
            "current_price": float(current_price),
            "market_event_key": market_event_key
        }
        logger.info(
            "exit_evaluation_started: strategy_id=%s version_id=%s current_price=%s",
            strategy_id, strategy_version_id, current_price,
            extra=log_meta
        )

        # 1. Query all active RUNNING executions for this strategy
        stmt_exec = select(StrategyExecution).where(
            StrategyExecution.strategy_id == strategy_id,
            StrategyExecution.strategy_version_id == strategy_version_id,
            StrategyExecution.status == "RUNNING"
        ).options(selectinload(StrategyExecution.legs))
        res_exec = await db.execute(stmt_exec)
        active_executions = list(res_exec.scalars().all())

        if not active_executions:
            logger.debug(
                "No active RUNNING executions for strategy %s", strategy_id,
                extra={**log_meta, "event": "exit_evaluation_skipped", "reason": "NO_ACTIVE_EXECUTIONS"}
            )
            return []

        # Current time in Asia/Kolkata
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc.astimezone(ZONE_KOLKATA)
        eval_time_ist = forced_time_ist or now_ist.time()
        eval_date_ist = now_ist.date()

        generated_signals: List[TradingSignal] = []

        # 2. Evaluate Exit Conditions Independently Per User Execution (Copy-Trading Safety)
        for execution in active_executions:
            exec_log_meta = {
                **log_meta,
                "execution_id": execution.id,
                "user_id": execution.user_id
            }

            # Find primary leg for entry price and direction
            primary_leg = next((l for l in execution.legs if l.status == "FILLED"), None)
            if not primary_leg:
                continue

            entry_price = primary_leg.average_fill_price or primary_leg.price or Decimal("100.00")
            direction = PositionDirection.BUY # Default long option

            # Determine effective Stop Loss
            sl_price = custom_stop_loss if custom_stop_loss is not None else (entry_price * Decimal("0.95")) # 5% fallback SL
            
            exit_result: Optional[ExitEvaluationResult] = None

            # --- Check A: Forced Time Exit (15:15 IST) ---
            forced_res = evaluate_forced_time_exit(eval_time_ist, time(15, 15), is_intraday=True)
            if forced_res.decision == ExitDecision.TRIGGERED:
                exit_result = forced_res
                logger.info("forced_exit_triggered: execution_id=%s reason=%s", execution.id, forced_res.reason, extra={**exec_log_meta, "event": "forced_exit_triggered"})

            # --- Check B: Contract Expiry Exit (15:15 IST on Expiry Date) ---
            if not exit_result and expiry_date_ist:
                exp_res = evaluate_expiry_exit(eval_date_ist, expiry_date_ist, eval_time_ist, time(15, 15))
                if exp_res.decision == ExitDecision.TRIGGERED:
                    exit_result = exp_res
                    logger.info("expiry_exit_triggered: execution_id=%s reason=%s", execution.id, exp_res.reason, extra={**exec_log_meta, "event": "expiry_exit_triggered"})

            # --- Check C: Strategy Invalidation (e.g. Strategy 3 Camarilla R3 breach) ---
            if not exit_result and invalidation_level is not None:
                inv_res = evaluate_strategy_invalidation(current_price, invalidation_level, direction=PositionDirection.SELL)
                if inv_res.decision == ExitDecision.TRIGGERED:
                    exit_result = inv_res
                    logger.info("strategy_invalidation_triggered: execution_id=%s reason=%s", execution.id, inv_res.reason, extra={**exec_log_meta, "event": "exit_condition_triggered", "condition": "STRATEGY_INVALIDATION"})

            # --- Check D: Hard Stop Loss Breach ---
            if not exit_result:
                sl_res = evaluate_stop_loss(entry_price, current_price, sl_price, direction)
                if sl_res.decision == ExitDecision.TRIGGERED:
                    exit_result = sl_res
                    logger.info("stop_loss_triggered: execution_id=%s sl=%s current=%s", execution.id, sl_price, current_price, extra={**exec_log_meta, "event": "exit_condition_triggered", "condition": "STOP_LOSS"})

            # --- Check E: Trailing Stop Loss ---
            if not exit_result and enable_trailing:
                initial_trailing_state = TrailingStopState(
                    execution_id=execution.id,
                    direction=direction,
                    entry_price=entry_price,
                    initial_stop_loss=sl_price,
                    current_trailing_stop=sl_price,
                    highest_favorable_price=entry_price,
                    lowest_favorable_price=entry_price,
                    step_r=Decimal("1.0"),
                    is_breakeven_activated=False
                )
                t_state = await trailing_state_manager.get_state(db, execution.id, initial_trailing_state)
                t_res, updated_t_state = evaluate_trailing_stop(current_price, t_state)
                
                # Checkpoint trailing state if changed
                if updated_t_state.current_trailing_stop != t_state.current_trailing_stop or updated_t_state.highest_favorable_price != t_state.highest_favorable_price:
                    await trailing_state_manager.save_state(db, updated_t_state, persist_db=True)
                    logger.info("trailing_stop_updated: execution_id=%s new_sl=%s peak=%s", execution.id, updated_t_state.current_trailing_stop, updated_t_state.highest_favorable_price, extra={**exec_log_meta, "event": "trailing_stop_updated"})

                if t_res.decision == ExitDecision.TRIGGERED:
                    exit_result = t_res
                    logger.info("trailing_stop_triggered: execution_id=%s current=%s", execution.id, current_price, extra={**exec_log_meta, "event": "exit_condition_triggered", "condition": "TRAILING_STOP"})

            # --- Check F: R-Multiple Target (e.g. 1R Partial or 2R Full) ---
            if not exit_result and (custom_r_multiple is not None or enable_partial_1r):
                r_mult = custom_r_multiple if custom_r_multiple is not None else (Decimal("1.0") if enable_partial_1r else Decimal("2.0"))
                exit_pct = Decimal("50.0") if (enable_partial_1r and custom_r_multiple is None) else Decimal("100.0")
                
                r_res = evaluate_r_multiple(entry_price, sl_price, current_price, r_mult, direction, exit_quantity_pct=exit_pct)
                if r_res.decision == ExitDecision.TRIGGERED:
                    exit_result = r_res
                    logger.info("r_multiple_target_triggered: execution_id=%s r=%s pct=%s", execution.id, r_mult, exit_pct, extra={**exec_log_meta, "event": "exit_condition_triggered", "condition": "R_MULTIPLE_TARGET"})

            # --- Check G: Fixed Target Price / Range ---
            if not exit_result and custom_target is not None:
                tgt_res = evaluate_target(entry_price, current_price, custom_target, direction)
                if tgt_res.decision == ExitDecision.TRIGGERED:
                    exit_result = tgt_res
                    logger.info("target_triggered: execution_id=%s target=%s current=%s", execution.id, custom_target, current_price, extra={**exec_log_meta, "event": "exit_condition_triggered", "condition": "TARGET"})

            # Log evaluation result for observability
            if not exit_result:
                logger.debug(
                    "exit_condition_not_triggered: execution_id=%s current_price=%s entry_price=%s sl=%s",
                    execution.id, current_price, entry_price, sl_price,
                    extra={**exec_log_meta, "event": "exit_condition_not_triggered", "decision": "NOT_TRIGGERED"}
                )
                continue

            # 3. An Exit Condition has Triggered -> Generate Deterministic EXIT Signal
            signal_key = f"{strategy_id}:{strategy_version_id}:EXIT:{exit_result.exit_type.value}:{market_event_key}:{execution.id}"
            
            # Check for existing duplicate signal key to guarantee idempotency
            stmt_sig_check = select(StrategySignal).where(StrategySignal.signal_key == signal_key)
            res_sig_check = await db.execute(stmt_sig_check)
            if res_sig_check.scalar_one_or_none():
                logger.warning(
                    "Duplicate exit signal prevented: key=%s execution_id=%s", signal_key, execution.id,
                    extra={**exec_log_meta, "event": "duplicate_exit_signal_prevented", "signal_key": signal_key}
                )
                continue

            signal_record = StrategySignal(
                strategy_id=strategy_id,
                strategy_version_id=strategy_version_id,
                trading_date=eval_date_ist,
                entry_time=eval_time_ist.strftime("%H:%M"),
                signal_key=signal_key,
                market_event_key=market_event_key,
                signal_type="EXIT",
                direction="SELL" if direction == PositionDirection.BUY else "BUY",
                status="CREATED",
                price=current_price,
                reason=f"[{exit_result.exit_type.value}] {exit_result.reason}"
            )
            db.add(signal_record)
            await db.flush()

            logger.info(
                "exit_signal_generated: signal_id=%s execution_id=%s type=%s reason=%s",
                signal_record.id, execution.id, exit_result.exit_type.value, exit_result.reason,
                extra={
                    **exec_log_meta,
                    "event": "exit_signal_generated",
                    "signal_id": signal_record.id,
                    "exit_type": exit_result.exit_type.value,
                    "reason": exit_result.reason
                }
            )

            # 4. Advance StrategyRuntimeState if full exit
            if exit_result.exit_quantity_pct >= Decimal("100.0"):
                try:
                    await strategy_state_manager.transition_state(
                        db=db,
                        strategy_id=strategy_id,
                        strategy_version_id=strategy_version_id,
                        new_state=StrategyLifecycleState.EXIT_SIGNAL,
                        reason=f"Exit triggered: {exit_result.reason}"
                    )
                    await strategy_state_manager.transition_state(
                        db=db,
                        strategy_id=strategy_id,
                        strategy_version_id=strategy_version_id,
                        new_state=StrategyLifecycleState.EXIT_ORDER_PENDING,
                        reason="Exit order pending execution"
                    )
                except Exception as ex:
                    logger.debug("Runtime state transition notice during exit: %s", str(ex))

            generated_signals.append(TradingSignal(
                signal_id=signal_record.id,
                signal_key=signal_key,
                strategy_id=strategy_id,
                strategy_version_id=strategy_version_id,
                market_event_key=market_event_key,
                event_id=event.event_id,
                symbol=event.symbol,
                timeframe=event.timeframe,
                signal_type=SignalType.EXIT,
                direction=SignalDirection.SELL if direction == PositionDirection.BUY else SignalDirection.BUY,
                status=SignalStatus.CREATED,
                price=current_price,
                reason=exit_result.reason,
                created_at=datetime.now(timezone.utc)
            ))

        return generated_signals

exit_engine = ExitEngine()
