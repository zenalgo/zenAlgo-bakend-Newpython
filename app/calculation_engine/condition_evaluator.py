"""
Calculation Engine — Strategy Condition Evaluator
Evaluates live IndicatorSnapshots and real-time tick prices against strategy conditions
stored in the database (StrategyCondition.rule_json).
Generates SignalEvents when entry/exit conditions are satisfied.
"""
from datetime import datetime, timezone
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculation_engine.schemas import IndicatorSnapshot, SignalEvent
from app.strategies.models import Strategy, StrategyVersion, StrategyCondition

logger = logging.getLogger(__name__)


def normalize_indicator_name(name: str) -> str:
    """Normalize indicator names for comparison."""
    if not name:
        return ""
    clean = name.strip().upper()
    if clean.startswith("EMA_") or clean.startswith("EMA"):
        return "EMA"
    if clean in ("BOLLINGER", "BOLLINGER_BANDS", "BBANDS", "BB"):
        return "BB"
    if clean in ("STOCH", "STOCHASTIC", "STOCHASTICS"):
        return "STOCHASTIC"
    if clean in ("SUPERTREND", "SUPER_TREND"):
        return "SUPERTREND"
    return clean


def extract_indicator_val(snapshot: IndicatorSnapshot, indicator_name: str) -> Optional[float]:
    """
    Extract current numeric value for an indicator name from snapshot.
    Supports special fields like LTP, VWAP, or individual indicator items.
    """
    norm = normalize_indicator_name(indicator_name)
    if norm in ("LTP", "PRICE", "CLOSE"):
        return snapshot.ltp
    if norm == "VWAP":
        # Check snapshot.vwap or find VWAP in indicators list
        if snapshot.vwap is not None:
            return snapshot.vwap
        for ind in snapshot.indicators:
            if ind.name.upper() == "VWAP" and ind.value is not None:
                return ind.value
        return None

    # Search snapshot indicators list
    for ind in snapshot.indicators:
        if normalize_indicator_name(ind.name) == norm:
            return ind.value

    return None


def evaluate_rule_op(current_val: float, target_val: float, operator: str) -> bool:
    """Evaluate comparison operator."""
    op = operator.strip().upper()
    if op in (">", "GREATER_THAN", "PRICE_ABOVE", "ABOVE"):
        return current_val > target_val
    elif op in ("<", "LESS_THAN", "PRICE_BELOW", "BELOW"):
        return current_val < target_val
    elif op in (">=", "GREATER_THAN_EQUAL", "AT_LEAST"):
        return current_val >= target_val
    elif op in ("<=", "LESS_THAN_EQUAL", "AT_MOST"):
        return current_val <= target_val
    elif op in ("==", "=", "EQUAL", "EQUALS"):
        return abs(current_val - target_val) < 1e-4
    return False


def evaluate_single_condition(
    condition: StrategyCondition,
    snapshot: IndicatorSnapshot,
    strategy_id: int,
    strategy_name: str,
    trigger_type: str = "CANDLE_CLOSE",
) -> Optional[SignalEvent]:
    """
    Evaluate a single StrategyCondition model against an IndicatorSnapshot.
    Returns a SignalEvent if condition is met, else None.
    """
    rule_dict: Dict[str, Any] = {}
    if condition.rule_json:
        try:
            rule_dict = json.loads(condition.rule_json)
        except Exception:
            pass

    # Extract indicator, operator, target value
    # Handle both simplified JSON: {"indicator": "VWAP", "operator": ">=", "value": 24500}
    # and ParsedRule format: {"type": "...", "indicator": "...", "operator": "...", "value": ...}
    indicator_name = rule_dict.get("indicator")
    operator = rule_dict.get("operator")
    target_val = rule_dict.get("value")
    rule_signal = rule_dict.get("signal") or condition.rule_type or "ENTRY"

    # Fallback to parsing raw_text if rule_dict is empty or missing fields
    if not indicator_name and condition.raw_text:
        raw_upper = condition.raw_text.upper()
        for cand in ["VWAP", "RSI", "MACD", "SUPERTREND", "STOCHASTIC", "ADX", "CCI", "MFI", "EMA", "BB"]:
            if cand in raw_upper:
                indicator_name = cand
                break

    if not indicator_name:
        return None

    # If target_val is missing from rule_dict, check if raw_text has a number
    if target_val is None and condition.raw_text:
        import re
        numbers = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", condition.raw_text)
        if numbers:
            try:
                target_val = float(numbers[-1])
            except ValueError:
                pass

    # Default operator if missing
    if not operator:
        raw_upper = (condition.raw_text or "").upper()
        if ">=" in raw_upper or "AT LEAST" in raw_upper:
            operator = ">="
        elif "<=" in raw_upper or "AT MOST" in raw_upper:
            operator = "<="
        elif ">" in raw_upper or "ABOVE" in raw_upper or "CROSSES ABOVE" in raw_upper:
            operator = ">"
        elif "<" in raw_upper or "BELOW" in raw_upper or "CROSSES BELOW" in raw_upper:
            operator = "<"
        elif "==" in raw_upper or "=" in raw_upper or "EQUALS" in raw_upper:
            operator = "=="
        else:
            operator = ">="

    curr_val = extract_indicator_val(snapshot, indicator_name)
    if curr_val is None:
        return None

    # Compare with another indicator or scalar value
    matched = False
    if target_val is not None:
        try:
            target_num = float(target_val)
            matched = evaluate_rule_op(curr_val, target_num, operator)
        except (ValueError, TypeError):
            pass
    elif rule_dict.get("compareToIndicator"):
        # e.g., LTP vs VWAP
        other_ind = rule_dict.get("compareToIndicator")
        other_val = extract_indicator_val(snapshot, other_ind)
        if other_val is not None:
            matched = evaluate_rule_op(curr_val, other_val, operator)

    if matched:
        cond_text = condition.raw_text or f"{indicator_name} {operator} {target_val}"
        return SignalEvent(
            event_id=f"sig_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now(timezone.utc),
            symbol=snapshot.symbol,
            timeframe=snapshot.timeframe,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            condition_id=condition.id,
            condition_text=cond_text,
            rule_json=rule_dict,
            indicator_name=indicator_name,
            indicator_value=round(curr_val, 2),
            signal=rule_signal.upper(),
            trigger_type=trigger_type,
        )

    return None


async def evaluate_conditions_against_snapshot(
    snapshot: IndicatorSnapshot,
    conditions_with_strategy: List[Tuple[StrategyCondition, int, str]],
    trigger_type: str = "CANDLE_CLOSE",
) -> List[SignalEvent]:
    """
    Evaluates a list of (StrategyCondition, strategy_id, strategy_name) tuples against snapshot.
    Returns list of triggered SignalEvents.
    """
    signals: List[SignalEvent] = []
    for cond, strat_id, strat_name in conditions_with_strategy:
        # If trigger is TICK, only evaluate fast indicators like VWAP and LTP
        rule_text = (cond.raw_text or "").upper()
        rule_json_str = (cond.rule_json or "").upper()
        is_vwap_or_price = (
            "VWAP" in rule_text or "VWAP" in rule_json_str or
            "PRICE" in rule_text or "LTP" in rule_text
        )

        if trigger_type == "TICK" and not is_vwap_or_price:
            continue

        sig = evaluate_single_condition(
            condition=cond,
            snapshot=snapshot,
            strategy_id=strat_id,
            strategy_name=strat_name,
            trigger_type=trigger_type,
        )
        if sig:
            signals.append(sig)

    return signals


async def fetch_active_conditions_for_symbol(
    db: AsyncSession,
    symbol: str,
) -> List[Tuple[StrategyCondition, int, str]]:
    """
    Fetch active strategy conditions for the given asset symbol from DB.
    Returns: List of (StrategyCondition, strategy_id, strategy_name)
    """
    results: List[Tuple[StrategyCondition, int, str]] = []
    try:
        stmt = (
            select(StrategyCondition, Strategy.id, Strategy.name)
            .join(StrategyVersion, StrategyCondition.strategy_version_id == StrategyVersion.id)
            .join(Strategy, StrategyVersion.strategy_id == Strategy.id)
            .where(
                Strategy.status.in_(["ACTIVE", "DEPLOYED", "TESTING", "DRAFT"]),
                Strategy.underlying.ilike(f"%{symbol}%")
            )
        )
        res = await db.execute(stmt)
        for row in res.all():
            cond, s_id, s_name = row[0], row[1], row[2]
            results.append((cond, int(s_id), str(s_name)))
    except Exception as e:
        logger.warning(f"Error fetching active conditions for {symbol}: {e}")

    return results
