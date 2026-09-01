import logging
from typing import Optional, Dict, Any, Tuple
from datetime import time, date, datetime, timezone
from decimal import Decimal

from app.strategies.exits.enums import ExitType, ExitDecision, PositionDirection
from app.strategies.exits.schemas import ExitEvaluationResult, TrailingStopState

logger = logging.getLogger(__name__)

def evaluate_stop_loss(
    entry_price: Optional[Decimal],
    current_price: Optional[Decimal],
    stop_loss_price: Optional[Decimal],
    direction: PositionDirection = PositionDirection.BUY
) -> ExitEvaluationResult:
    """
    Evaluates fixed or candle-based Stop Loss.
    Triggered when market price crosses the protective stop loss boundary.
    """
    if entry_price is None or current_price is None or stop_loss_price is None:
        return ExitEvaluationResult(
            decision=ExitDecision.DATA_UNAVAILABLE,
            reason="Missing required price data for Stop Loss evaluation",
            metrics={"entry_price": str(entry_price), "current_price": str(current_price), "stop_loss_price": str(stop_loss_price)}
        )

    metrics = {
        "entry_price": float(entry_price),
        "current_price": float(current_price),
        "stop_loss_price": float(stop_loss_price),
        "direction": direction.value
    }

    if direction == PositionDirection.BUY:
        if current_price <= stop_loss_price:
            return ExitEvaluationResult(
                decision=ExitDecision.TRIGGERED,
                exit_type=ExitType.STOP_LOSS,
                trigger_price=current_price,
                reason=f"Stop loss triggered for LONG position: current price {current_price} <= SL {stop_loss_price}",
                metrics=metrics
            )
    elif direction == PositionDirection.SELL:
        if current_price >= stop_loss_price:
            return ExitEvaluationResult(
                decision=ExitDecision.TRIGGERED,
                exit_type=ExitType.STOP_LOSS,
                trigger_price=current_price,
                reason=f"Stop loss triggered for SHORT position: current price {current_price} >= SL {stop_loss_price}",
                metrics=metrics
            )

    return ExitEvaluationResult(
        decision=ExitDecision.NOT_TRIGGERED,
        reason=f"Stop loss not breached (Current: {current_price}, SL: {stop_loss_price})",
        metrics=metrics
    )


def evaluate_target(
    entry_price: Optional[Decimal],
    current_price: Optional[Decimal],
    target_price: Optional[Decimal],
    direction: PositionDirection = PositionDirection.BUY,
    exit_quantity_pct: Decimal = Decimal("100.0")
) -> ExitEvaluationResult:
    """
    Evaluates fixed price or percentage Target.
    Triggered when market price reaches or surpasses profit target.
    """
    if entry_price is None or current_price is None or target_price is None:
        return ExitEvaluationResult(
            decision=ExitDecision.DATA_UNAVAILABLE,
            reason="Missing required price data for Target evaluation",
            metrics={"entry_price": str(entry_price), "current_price": str(current_price), "target_price": str(target_price)}
        )

    metrics = {
        "entry_price": float(entry_price),
        "current_price": float(current_price),
        "target_price": float(target_price),
        "direction": direction.value,
        "exit_quantity_pct": float(exit_quantity_pct)
    }

    if direction == PositionDirection.BUY:
        if current_price >= target_price:
            return ExitEvaluationResult(
                decision=ExitDecision.TRIGGERED,
                exit_type=ExitType.TARGET if exit_quantity_pct >= Decimal("100.0") else ExitType.PARTIAL_EXIT,
                trigger_price=current_price,
                exit_quantity_pct=exit_quantity_pct,
                reason=f"Profit target reached for LONG position: current price {current_price} >= Target {target_price}",
                metrics=metrics
            )
    elif direction == PositionDirection.SELL:
        if current_price <= target_price:
            return ExitEvaluationResult(
                decision=ExitDecision.TRIGGERED,
                exit_type=ExitType.TARGET if exit_quantity_pct >= Decimal("100.0") else ExitType.PARTIAL_EXIT,
                trigger_price=current_price,
                exit_quantity_pct=exit_quantity_pct,
                reason=f"Profit target reached for SHORT position: current price {current_price} <= Target {target_price}",
                metrics=metrics
            )

    return ExitEvaluationResult(
        decision=ExitDecision.NOT_TRIGGERED,
        reason=f"Target not reached (Current: {current_price}, Target: {target_price})",
        metrics=metrics
    )


def evaluate_r_multiple(
    entry_price: Optional[Decimal],
    stop_loss_price: Optional[Decimal],
    current_price: Optional[Decimal],
    r_multiple: Decimal,
    direction: PositionDirection = PositionDirection.BUY,
    exit_quantity_pct: Decimal = Decimal("100.0")
) -> ExitEvaluationResult:
    """
    Evaluates R-Multiple (e.g. 1R partial, 2R full) Target based on initial risk (entry - SL).
    """
    if entry_price is None or stop_loss_price is None or current_price is None:
        return ExitEvaluationResult(
            decision=ExitDecision.DATA_UNAVAILABLE,
            reason="Missing required price data for R-multiple evaluation",
            metrics={"entry_price": str(entry_price), "stop_loss_price": str(stop_loss_price), "current_price": str(current_price)}
        )

    risk = abs(entry_price - stop_loss_price)
    if risk <= Decimal("0.0"):
        return ExitEvaluationResult(
            decision=ExitDecision.DATA_UNAVAILABLE,
            reason="Zero or negative initial risk distance between entry and SL",
            metrics={"entry_price": float(entry_price), "stop_loss_price": float(stop_loss_price)}
        )

    target_distance = risk * r_multiple
    target_price = (entry_price + target_distance) if direction == PositionDirection.BUY else (entry_price - target_distance)

    metrics = {
        "entry_price": float(entry_price),
        "stop_loss_price": float(stop_loss_price),
        "current_price": float(current_price),
        "initial_risk_1R": float(risk),
        "r_multiple": float(r_multiple),
        "calculated_target_price": float(target_price),
        "direction": direction.value
    }

    if direction == PositionDirection.BUY:
        if current_price >= target_price:
            return ExitEvaluationResult(
                decision=ExitDecision.TRIGGERED,
                exit_type=ExitType.R_MULTIPLE_TARGET if exit_quantity_pct >= Decimal("100.0") else ExitType.PARTIAL_EXIT,
                trigger_price=current_price,
                exit_quantity_pct=exit_quantity_pct,
                reason=f"Reached {r_multiple}R target at price {current_price} (Target: {target_price}, 1R Risk: {risk})",
                metrics=metrics
            )
    elif direction == PositionDirection.SELL:
        if current_price <= target_price:
            return ExitEvaluationResult(
                decision=ExitDecision.TRIGGERED,
                exit_type=ExitType.R_MULTIPLE_TARGET if exit_quantity_pct >= Decimal("100.0") else ExitType.PARTIAL_EXIT,
                trigger_price=current_price,
                exit_quantity_pct=exit_quantity_pct,
                reason=f"Reached {r_multiple}R target at price {current_price} (Target: {target_price}, 1R Risk: {risk})",
                metrics=metrics
            )

    return ExitEvaluationResult(
        decision=ExitDecision.NOT_TRIGGERED,
        reason=f"{r_multiple}R target not reached (Current: {current_price}, Target: {target_price})",
        metrics=metrics
    )


def evaluate_trailing_stop(
    current_price: Optional[Decimal],
    state: TrailingStopState
) -> Tuple[ExitEvaluationResult, TrailingStopState]:
    """
    Evaluates dynamic Trailing Stop Loss and updates highest/lowest favorable excursion.
    """
    if current_price is None or current_price <= Decimal("0.0"):
        return (
            ExitEvaluationResult(
                decision=ExitDecision.DATA_UNAVAILABLE,
                reason="Invalid or missing current market price for Trailing Stop evaluation"
            ),
            state
        )

    risk = abs(state.entry_price - state.initial_stop_loss)
    if risk <= Decimal("0.0"):
        risk = state.entry_price * Decimal("0.01") # 1% fallback risk

    # Clone state for updates
    updated_state = state.model_copy()
    updated_state.last_updated_at = datetime.now(timezone.utc)

    if state.direction == PositionDirection.BUY:
        # Update peak price for LONG
        if current_price > updated_state.highest_favorable_price:
            updated_state.highest_favorable_price = current_price

        # Step 1: Breakeven activation when price crosses +1R
        if not updated_state.is_breakeven_activated and updated_state.highest_favorable_price >= updated_state.entry_price + risk:
            updated_state.is_breakeven_activated = True
            updated_state.current_trailing_stop = max(updated_state.current_trailing_stop, updated_state.entry_price)

        # Step 2: Step-based trailing once above 1R
        if updated_state.highest_favorable_price > updated_state.entry_price + (risk * updated_state.step_r):
            trail_candidate = updated_state.highest_favorable_price - risk
            updated_state.current_trailing_stop = max(updated_state.current_trailing_stop, trail_candidate)

        # Step 3: Trigger check
        if current_price <= updated_state.current_trailing_stop:
            return (
                ExitEvaluationResult(
                    decision=ExitDecision.TRIGGERED,
                    exit_type=ExitType.TRAILING_STOP,
                    trigger_price=current_price,
                    reason=f"Trailing stop triggered for LONG: current price {current_price} <= trailing stop {updated_state.current_trailing_stop} (Peak: {updated_state.highest_favorable_price})",
                    metrics={
                        "entry_price": float(state.entry_price),
                        "peak_price": float(updated_state.highest_favorable_price),
                        "current_trailing_stop": float(updated_state.current_trailing_stop),
                        "current_price": float(current_price)
                    }
                ),
                updated_state
            )

    elif state.direction == PositionDirection.SELL:
        # Update trough price for SHORT
        if current_price < updated_state.lowest_favorable_price or updated_state.lowest_favorable_price == Decimal("0.0"):
            updated_state.lowest_favorable_price = current_price

        # Step 1: Breakeven activation when price drops by 1R
        if not updated_state.is_breakeven_activated and updated_state.lowest_favorable_price <= updated_state.entry_price - risk:
            updated_state.is_breakeven_activated = True
            updated_state.current_trailing_stop = min(updated_state.current_trailing_stop, updated_state.entry_price)

        # Step 2: Step-based trailing once below 1R
        if updated_state.lowest_favorable_price < updated_state.entry_price - (risk * updated_state.step_r):
            trail_candidate = updated_state.lowest_favorable_price + risk
            updated_state.current_trailing_stop = min(updated_state.current_trailing_stop, trail_candidate)

        # Step 3: Trigger check
        if current_price >= updated_state.current_trailing_stop:
            return (
                ExitEvaluationResult(
                    decision=ExitDecision.TRIGGERED,
                    exit_type=ExitType.TRAILING_STOP,
                    trigger_price=current_price,
                    reason=f"Trailing stop triggered for SHORT: current price {current_price} >= trailing stop {updated_state.current_trailing_stop} (Trough: {updated_state.lowest_favorable_price})",
                    metrics={
                        "entry_price": float(state.entry_price),
                        "trough_price": float(updated_state.lowest_favorable_price),
                        "current_trailing_stop": float(updated_state.current_trailing_stop),
                        "current_price": float(current_price)
                    }
                ),
                updated_state
            )

    return (
        ExitEvaluationResult(
            decision=ExitDecision.NOT_TRIGGERED,
            reason=f"Trailing stop holding (Current: {current_price}, Trailing Stop: {updated_state.current_trailing_stop})",
            metrics={
                "entry_price": float(state.entry_price),
                "peak_favorable": float(updated_state.highest_favorable_price if state.direction == PositionDirection.BUY else updated_state.lowest_favorable_price),
                "current_trailing_stop": float(updated_state.current_trailing_stop),
                "current_price": float(current_price)
            }
        ),
        updated_state
    )


def evaluate_forced_time_exit(
    current_time_ist: time,
    forced_exit_time: time = time(15, 15),
    is_intraday: bool = True
) -> ExitEvaluationResult:
    """
    Evaluates intraday hard cutoff time (15:15 IST).
    """
    if not is_intraday:
        return ExitEvaluationResult(decision=ExitDecision.SKIPPED, reason="Positional/Delivery strategy exempt from intraday forced exit cutoff")

    if current_time_ist >= forced_exit_time:
        return ExitEvaluationResult(
            decision=ExitDecision.TRIGGERED,
            exit_type=ExitType.FORCED_TIME_EXIT,
            reason=f"Forced intraday cutoff triggered: current IST time {current_time_ist.strftime('%H:%M')} >= {forced_exit_time.strftime('%H:%M')}",
            metrics={"current_time_ist": current_time_ist.strftime('%H:%M:%S'), "forced_exit_time": forced_exit_time.strftime('%H:%M:%S')}
        )

    return ExitEvaluationResult(
        decision=ExitDecision.NOT_TRIGGERED,
        reason=f"Before forced cutoff window (Current: {current_time_ist.strftime('%H:%M')}, Cutoff: {forced_exit_time.strftime('%H:%M')})",
        metrics={"current_time_ist": current_time_ist.strftime('%H:%M:%S'), "forced_exit_time": forced_exit_time.strftime('%H:%M:%S')}
    )


def evaluate_expiry_exit(
    current_date_ist: date,
    expiry_date_ist: date,
    current_time_ist: time,
    forced_exit_time: time = time(15, 15)
) -> ExitEvaluationResult:
    """
    Evaluates contract expiry cutoff (15:15 IST on expiry date).
    """
    if current_date_ist == expiry_date_ist and current_time_ist >= forced_exit_time:
        return ExitEvaluationResult(
            decision=ExitDecision.TRIGGERED,
            exit_type=ExitType.EXPIRY_EXIT,
            reason=f"Contract expiry exit triggered on {current_date_ist} at {current_time_ist.strftime('%H:%M')} (Expiry Cutoff: {forced_exit_time.strftime('%H:%M')})",
            metrics={"current_date": str(current_date_ist), "expiry_date": str(expiry_date_ist), "current_time": current_time_ist.strftime('%H:%M:%S')}
        )

    return ExitEvaluationResult(
        decision=ExitDecision.NOT_TRIGGERED,
        reason=f"Not yet at expiry cutoff (Date: {current_date_ist}, Expiry: {expiry_date_ist}, Time: {current_time_ist.strftime('%H:%M')})",
        metrics={"current_date": str(current_date_ist), "expiry_date": str(expiry_date_ist), "current_time": current_time_ist.strftime('%H:%M:%S')}
    )


def evaluate_strategy_invalidation(
    current_price: Optional[Decimal],
    invalidation_level: Optional[Decimal],
    direction: PositionDirection = PositionDirection.SELL
) -> ExitEvaluationResult:
    """
    Evaluates structural strategy invalidation (e.g. Strategy 3 Camarilla R3 breach for CE short setup).
    """
    if current_price is None or invalidation_level is None:
        return ExitEvaluationResult(
            decision=ExitDecision.DATA_UNAVAILABLE,
            reason="Missing price data for strategy invalidation evaluation",
            metrics={"current_price": str(current_price), "invalidation_level": str(invalidation_level)}
        )

    metrics = {
        "current_price": float(current_price),
        "invalidation_level": float(invalidation_level),
        "direction": direction.value
    }

    # For Option Selling setups (e.g. Short CE breached above R3 level)
    if direction == PositionDirection.SELL:
        if current_price >= invalidation_level:
            return ExitEvaluationResult(
                decision=ExitDecision.TRIGGERED,
                exit_type=ExitType.STRATEGY_INVALIDATION,
                trigger_price=current_price,
                reason=f"Strategy structure invalidated: current price {current_price} breached invalidation level {invalidation_level}",
                metrics=metrics
            )
    elif direction == PositionDirection.BUY:
        if current_price <= invalidation_level:
            return ExitEvaluationResult(
                decision=ExitDecision.TRIGGERED,
                exit_type=ExitType.STRATEGY_INVALIDATION,
                trigger_price=current_price,
                reason=f"Strategy structure invalidated: current price {current_price} breached invalidation level {invalidation_level}",
                metrics=metrics
            )

    return ExitEvaluationResult(
        decision=ExitDecision.NOT_TRIGGERED,
        reason=f"Strategy structure intact (Current: {current_price}, Invalidation Level: {invalidation_level})",
        metrics=metrics
    )
