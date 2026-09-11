"""
Calculation Engine — Strategy Condition Evaluator
Evaluates live IndicatorSnapshots and real-time tick prices against strategy conditions
stored in the database (StrategyCondition.rule_json).
Generates SignalEvents when entry/exit conditions are satisfied.
"""
import re
from datetime import datetime, timezone
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.calculation_engine.schemas import IndicatorSnapshot, SignalEvent
from app.strategies.models import Strategy, StrategyVersion, StrategyCondition
from app.strategies.parser.deterministic_parser import parse_deterministic_rule

logger = logging.getLogger(__name__)


def normalize_indicator_name(name: str) -> str:
    """Normalize indicator names for comparison, preserving specific periods when present."""
    if not name:
        return ""
    clean = name.strip().upper().replace(" ", "_")
    # Check if period is specified (e.g. EMA_8, 8_EMA, EMA(8), EMA8)
    ema_match = re.search(r"(\d+)_?EMA|EMA_?\(?(\d+)\)?", clean)
    if ema_match:
        period = ema_match.group(1) or ema_match.group(2)
        return f"EMA_{period}"
    if clean.startswith("EMA"):
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
    Supports special fields like LTP, VWAP, specific EMA periods (EMA_8, EMA_33), or individual indicator items.
    """
    if not indicator_name:
        return None

    norm = normalize_indicator_name(indicator_name)
    if norm in ("LTP", "PRICE", "CLOSE", "SPOT"):
        return snapshot.ltp
    if norm == "VWAP":
        if snapshot.vwap is not None:
            return snapshot.vwap
        for ind in snapshot.indicators:
            if ind.name.upper() == "VWAP" and ind.value is not None:
                return ind.value
        return None

    # Check for specific EMA period (e.g. EMA_8, EMA_33)
    if norm.startswith("EMA_"):
        period_str = norm.split("_")[1]
        # 1. Look for direct indicator item in snapshot (e.g. EMA_8)
        for ind in snapshot.indicators:
            if ind.name.upper() == norm and ind.value is not None:
                return ind.value

        # 2. Look in EMA secondary dict
        for ind in snapshot.indicators:
            if ind.name.upper() == "EMA" and isinstance(ind.secondary, dict):
                sec_val = ind.secondary.get(f"ema{period_str}") or ind.secondary.get(f"EMA{period_str}")
                if sec_val is not None:
                    return float(sec_val)

        # Fallback to general EMA value
        for ind in snapshot.indicators:
            if ind.name.upper() == "EMA" and ind.value is not None:
                return ind.value

    # General search across snapshot indicators
    for ind in snapshot.indicators:
        if normalize_indicator_name(ind.name) == norm and ind.value is not None:
            return ind.value

    return None


def evaluate_rule_op(current_val: float, target_val: float, operator: str) -> bool:
    """Evaluate comparison operator."""
    if current_val is None or target_val is None:
        return False
    op = (operator or "").strip().upper()
    if op in (">", "GREATER_THAN", "PRICE_ABOVE", "ABOVE", "CROSS_ABOVE"):
        return current_val > target_val
    elif op in ("<", "LESS_THAN", "PRICE_BELOW", "BELOW", "CROSS_BELOW"):
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

    # If rule_json is missing or was parsed as generic CONFIRMATION_RULE, try parsing raw_text
    if (not rule_dict or rule_dict.get("type") == "CONFIRMATION_RULE" or not rule_dict.get("indicator")) and condition.raw_text:
        parsed_res = parse_deterministic_rule(condition.raw_text)
        if parsed_res.status == "SUPPORTED" and parsed_res.parsed_rule:
            rule_dict = parsed_res.parsed_rule.model_dump(mode="json")

    indicator_name = rule_dict.get("indicator")
    operator = rule_dict.get("operator")
    target_val = rule_dict.get("value")
    rule_signal = rule_dict.get("signal") or condition.rule_type or "ENTRY"
    rule_type = rule_dict.get("type")

    # Handle Indicator-to-Indicator comparison (left vs right)
    matched = False
    curr_val = None

    if rule_dict.get("left") and rule_dict.get("right"):
        left_op = rule_dict["left"]
        right_op = rule_dict["right"]
        left_ind = f"{left_op.get('indicator')}_{left_op.get('period')}" if left_op.get("period") else left_op.get("indicator")
        right_ind = f"{right_op.get('indicator')}_{right_op.get('period')}" if right_op.get("period") else right_op.get("indicator")

        left_val = extract_indicator_val(snapshot, left_ind)
        right_val = extract_indicator_val(snapshot, right_ind)
        curr_val = left_val

        if left_val is not None and right_val is not None:
            matched = evaluate_rule_op(left_val, right_val, operator or ">")
    elif rule_type == "PRICE_COMPARISON" or rule_type == "PRICE_CROSSOVER" or rule_dict.get("price") in ("PRICE", "SPOT"):
        # Price vs Indicator (e.g. Price > EMA 33)
        curr_val = snapshot.ltp
        ind_key = f"{indicator_name}_{rule_dict.get('period')}" if rule_dict.get("period") else indicator_name
        target_val = extract_indicator_val(snapshot, ind_key)
        if curr_val is not None and target_val is not None:
            matched = evaluate_rule_op(curr_val, target_val, operator or ">")
    else:
        # Fallback to single indicator vs target / another indicator
        if not indicator_name and condition.raw_text:
            raw_upper = condition.raw_text.upper()
            for cand in ["VWAP", "RSI", "MACD", "SUPERTREND", "STOCHASTIC", "ADX", "CCI", "MFI", "EMA", "BB"]:
                if cand in raw_upper:
                    indicator_name = cand
                    break

        if not indicator_name:
            return None

        # Period resolution from rule_dict
        if rule_dict.get("period"):
            indicator_name = f"{indicator_name}_{rule_dict.get('period')}"

        curr_val = extract_indicator_val(snapshot, indicator_name)
        if curr_val is None:
            return None

        if target_val is not None:
            try:
                target_num = float(target_val)
                matched = evaluate_rule_op(curr_val, target_num, operator or ">=")
            except (ValueError, TypeError):
                pass
        elif rule_dict.get("compareToIndicator"):
            other_ind = rule_dict.get("compareToIndicator")
            other_val = extract_indicator_val(snapshot, other_ind)
            if other_val is not None:
                matched = evaluate_rule_op(curr_val, other_val, operator or ">=")

    if matched and curr_val is not None:
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
            indicator_name=indicator_name or "CONDITION",
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
                Strategy.is_active == True,
                Strategy.status.in_(["ACTIVE", "ACTIVE_LIVE", "ACTIVE_PAPER", "DEPLOYED", "TESTING", "DRAFT", "LIVE", "PAPER"]),
                StrategyVersion.underlying.ilike(f"%{symbol}%")
            )
        )
        res = await db.execute(stmt)
        for row in res.all():
            cond, s_id, s_name = row[0], row[1], row[2]
            results.append((cond, int(s_id), str(s_name)))
    except Exception as e:
        logger.warning(f"Error fetching active conditions for {symbol}: {e}")

    return results
