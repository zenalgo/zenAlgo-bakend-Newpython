"""
Trailing Profit Stop-Loss Engine
=================================
Rule:  Every time unrealized profit crosses a 1% increment beyond the previous
       high-water-mark, the protective stop-loss is ratcheted forward by 1%
       of the entry price.

Key guarantees:
  - Stop-loss NEVER moves backward (monotonically tightening / moving in profit direction).
  - Step size is configurable (default 1.0 %).
  - Works for both LONG (BUY) and SHORT (SELL) positions.
  - Fully deterministic – idempotent on the same input price.
  - All state is captured in TrailingProfitState (Redis-backed + DB checkpoint).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from datetime import datetime, timezone
from typing import Tuple, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# State Schema
# ──────────────────────────────────────────────

class TrailingProfitState(BaseModel):
    """Persisted runtime state for the 1%-profit trailing stop-loss feature."""

    execution_id: int
    direction: str = "BUY"                       # "BUY" or "SELL"
    entry_price: Decimal                          # Actual fill / entry price
    initial_stop_loss: Decimal                    # The original SL price set by strategy
    current_stop_loss: Decimal                    # The live (ratcheted) SL price
    peak_profit_pct: Decimal = Decimal("0.0")    # Highest profit % ever reached (HWM)
    step_pct: Decimal = Decimal("1.0")           # Step size in % (default 1 %)
    steps_advanced: int = 0                      # How many times SL has been ratcheted
    last_updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # ── Convenience helpers ────────────────────
    @property
    def profit_pct(self) -> Decimal:
        return self.peak_profit_pct

    def summary(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "direction": self.direction,
            "entry_price": float(self.entry_price),
            "initial_stop_loss": float(self.initial_stop_loss),
            "current_stop_loss": float(self.current_stop_loss),
            "peak_profit_pct": float(self.peak_profit_pct),
            "steps_advanced": self.steps_advanced,
            "step_pct": float(self.step_pct),
        }


# ──────────────────────────────────────────────
# Core evaluation logic
# ──────────────────────────────────────────────

def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def advance_trailing_stop(
    current_price: Decimal,
    state: TrailingProfitState,
) -> Tuple[TrailingProfitState, bool]:
    """
    Evaluate the current market price against the trailing-profit state and
    advance the stop-loss if a new profit threshold has been crossed.

    Returns
    -------
    (updated_state, was_advanced)
        updated_state : the new state (may be unchanged if SL did not move)
        was_advanced  : True if the SL was moved at least once
    """
    entry = state.entry_price
    if entry <= Decimal("0"):
        return state, False

    # --- Compute current unrealised profit % ---
    if state.direction.upper() == "BUY":
        current_profit_pct = ((current_price - entry) / entry) * Decimal("100")
    else:  # SELL / SHORT
        current_profit_pct = ((entry - current_price) / entry) * Decimal("100")

    # Profit must be positive to advance SL
    if current_profit_pct <= Decimal("0"):
        return state, False

    # --- How many full `step_pct` bands has price crossed? ---
    step = state.step_pct
    new_peak = max(state.peak_profit_pct, current_profit_pct)
    completed_steps = int(new_peak / step)          # e.g. 2.4% / 1% = 2 full steps

    if completed_steps <= state.steps_advanced:
        # No new band crossed – update HWM if price improved, but SL stays
        if new_peak > state.peak_profit_pct:
            updated = state.model_copy(
                update={
                    "peak_profit_pct": _round2(new_peak),
                    "last_updated_at": datetime.now(timezone.utc),
                }
            )
            return updated, False
        return state, False

    # --- Advance SL by the number of NEW steps crossed ---
    new_steps_advanced = completed_steps
    steps_gained = new_steps_advanced - state.steps_advanced
    sl_advance_pct = step * Decimal(str(steps_gained))   # e.g. 1 step × 1 % = 1 %

    if state.direction.upper() == "BUY":
        # For LONG: move SL UP  (closer to / above entry)
        candidate_sl = _round2(state.current_stop_loss + (entry * sl_advance_pct / Decimal("100")))
        # Monotonic constraint: never retreat
        new_sl = max(state.current_stop_loss, candidate_sl)
    else:
        # For SHORT: move SL DOWN (closer to / below entry)
        candidate_sl = _round2(state.current_stop_loss - (entry * sl_advance_pct / Decimal("100")))
        # Monotonic constraint: never retreat (never move SL up for a SHORT)
        new_sl = min(state.current_stop_loss, candidate_sl)

    updated = state.model_copy(
        update={
            "current_stop_loss": new_sl,
            "peak_profit_pct": _round2(new_peak),
            "steps_advanced": new_steps_advanced,
            "last_updated_at": datetime.now(timezone.utc),
        }
    )

    logger.info(
        "trailing_profit_sl_advanced: execution_id=%s direction=%s "
        "entry=%.2f profit_pct=%.2f steps=%d old_sl=%.2f new_sl=%.2f",
        state.execution_id,
        state.direction,
        float(entry),
        float(new_peak),
        new_steps_advanced,
        float(state.current_stop_loss),
        float(new_sl),
    )

    return updated, True


def is_sl_triggered(current_price: Decimal, state: TrailingProfitState) -> bool:
    """
    Returns True if the current market price has breached the live trailing SL.
    LONG  → triggered when price drops to or below current_stop_loss
    SHORT → triggered when price rises to or above current_stop_loss
    """
    if state.direction.upper() == "BUY":
        return current_price <= state.current_stop_loss
    else:
        return current_price >= state.current_stop_loss


# ──────────────────────────────────────────────
# Redis-backed state persistence
# ──────────────────────────────────────────────

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.strategies.models import StrategyExecution


class TrailingProfitStateManager:
    """
    Dual-tier state manager:
      1. Redis  – sub-millisecond hot path reads/writes.
      2. PostgreSQL (execution_logs JSON column) – crash-safe checkpoints.
    """

    _REDIS_KEY_PREFIX = "state:trailing_profit:"
    _REDIS_TTL = 604_800   # 7 days in seconds

    @classmethod
    def _key(cls, execution_id: int) -> str:
        return f"{cls._REDIS_KEY_PREFIX}{execution_id}"

    @classmethod
    async def get_state(
        cls,
        db: AsyncSession,
        execution_id: int,
        default: Optional[TrailingProfitState] = None,
    ) -> Optional[TrailingProfitState]:
        """Load state: Redis → DB fallback → default."""
        from app.core.redis import redis_manager  # local import to avoid circular deps

        key = cls._key(execution_id)

        # 1. Redis hot path
        try:
            raw = await redis_manager.client.get(key)
            if raw:
                return TrailingProfitState.model_validate(json.loads(raw))
        except Exception as exc:
            logger.debug("Redis trailing_profit read error exec=%s: %s", execution_id, exc)

        # 2. PostgreSQL fallback
        try:
            stmt = select(StrategyExecution).where(StrategyExecution.id == execution_id)
            res = await db.execute(stmt)
            execution = res.scalar_one_or_none()
            if execution and execution.execution_logs:
                logs: dict = {}
                if isinstance(execution.execution_logs, str):
                    try:
                        logs = json.loads(execution.execution_logs)
                    except Exception:
                        pass
                elif isinstance(execution.execution_logs, dict):
                    logs = execution.execution_logs

                if "trailing_profit_state" in logs:
                    recovered = TrailingProfitState.model_validate(logs["trailing_profit_state"])
                    await cls.save_state(db, recovered, persist_db=False)
                    return recovered
        except Exception as exc:
            logger.warning("DB trailing_profit recovery error exec=%s: %s", execution_id, exc)

        # 3. Seed default
        if default:
            await cls.save_state(db, default, persist_db=True)
            return default

        return None

    @classmethod
    async def save_state(
        cls,
        db: AsyncSession,
        state: TrailingProfitState,
        persist_db: bool = True,
    ) -> None:
        """Write state to Redis and optionally checkpoint to PostgreSQL."""
        from app.core.redis import redis_manager

        key = cls._key(state.execution_id)
        payload = json.loads(state.model_dump_json())

        # 1. Redis
        try:
            await redis_manager.client.setex(key, cls._REDIS_TTL, json.dumps(payload))
        except Exception as exc:
            logger.debug("Redis trailing_profit write error exec=%s: %s", state.execution_id, exc)

        # 2. PostgreSQL checkpoint
        if persist_db:
            try:
                stmt = select(StrategyExecution).where(StrategyExecution.id == state.execution_id)
                res = await db.execute(stmt)
                execution = res.scalar_one_or_none()
                if execution:
                    logs: dict = {}
                    if execution.execution_logs:
                        if isinstance(execution.execution_logs, str):
                            try:
                                logs = json.loads(execution.execution_logs)
                            except Exception:
                                logs = {}
                        elif isinstance(execution.execution_logs, dict):
                            logs = dict(execution.execution_logs)
                    logs["trailing_profit_state"] = payload
                    execution.execution_logs = json.dumps(logs)
                    db.add(execution)
                    await db.flush()
            except Exception as exc:
                logger.warning("DB trailing_profit checkpoint error exec=%s: %s", state.execution_id, exc)


trailing_profit_state_manager = TrailingProfitStateManager()
