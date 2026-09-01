from typing import Optional, Dict, Any, List
import logging
from decimal import Decimal

from app.strategies.rules.rule_schema import ParsedRule
from app.strategies.engine.enums import EvaluationStatus
from app.strategies.engine.schemas import ConditionEvaluationResult
from app.strategies.engine.context import MarketContext

logger = logging.getLogger(__name__)

def evaluate_comparison_operator(left: float, right: float, operator: str) -> bool:
    """Evaluates standard comparison operators."""
    op = operator.strip().upper()
    if op in (">", "GREATER_THAN", "PRICE_ABOVE", "ABOVE"):
        return left > right
    elif op in ("<", "LESS_THAN", "PRICE_BELOW", "BELOW"):
        return left < right
    elif op in (">=", "GREATER_THAN_EQUAL", "AT_LEAST"):
        return left >= right
    elif op in ("<=", "LESS_THAN_EQUAL", "AT_MOST"):
        return left <= right
    elif op in ("==", "=", "EQUAL", "EQUALS"):
        return left == right
    return left > right

def evaluate_condition(rule: ParsedRule, context: MarketContext) -> ConditionEvaluationResult:
    """
    Pure, deterministic evaluation of a ParsedRule AST against a MarketContext.
    """
    rule_type = str(rule.type).strip().upper() if rule.type else "CONDITION"

    # --- 1. LOGICAL OPERATORS: AND, OR, NOT ---
    if rule_type in ("AND", "OR", "NOT") or rule.logic in ("AND", "OR", "NOT"):
        logic_op = (rule.logic or rule_type).upper()
        children = rule.conditions or []

        if logic_op == "NOT":
            if not children:
                return ConditionEvaluationResult(
                    matched=False, status=EvaluationStatus.ERROR, rule_type="NOT",
                    reason="NOT operator missing child condition"
                )
            child_res = evaluate_condition(children[0], context)
            if child_res.status == EvaluationStatus.DATA_UNAVAILABLE:
                return ConditionEvaluationResult(
                    matched=False, status=EvaluationStatus.DATA_UNAVAILABLE, rule_type="NOT",
                    reason=f"Child condition unavailable: {child_res.reason}"
                )
            matched = not child_res.matched
            status = EvaluationStatus.MATCHED if matched else EvaluationStatus.NOT_MATCHED
            return ConditionEvaluationResult(
                matched=matched, status=status, rule_type="NOT",
                reason=f"NOT (child matched={child_res.matched}) -> {matched}"
            )

        elif logic_op == "AND":
            if not children:
                return ConditionEvaluationResult(
                    matched=True, status=EvaluationStatus.MATCHED, rule_type="AND",
                    reason="Empty AND condition evaluates to TRUE"
                )
            child_results = [evaluate_condition(c, context) for c in children]
            
            # If any child is DATA_UNAVAILABLE, the whole AND is DATA_UNAVAILABLE
            for cr in child_results:
                if cr.status == EvaluationStatus.DATA_UNAVAILABLE:
                    return ConditionEvaluationResult(
                        matched=False, status=EvaluationStatus.DATA_UNAVAILABLE, rule_type="AND",
                        reason=f"AND operand unavailable: {cr.reason}"
                    )
            
            all_matched = all(cr.matched for cr in child_results)
            status = EvaluationStatus.MATCHED if all_matched else EvaluationStatus.NOT_MATCHED
            return ConditionEvaluationResult(
                matched=all_matched, status=status, rule_type="AND",
                reason=f"AND across {len(child_results)} condition(s) -> {all_matched}"
            )

        elif logic_op == "OR":
            if not children:
                return ConditionEvaluationResult(
                    matched=False, status=EvaluationStatus.NOT_MATCHED, rule_type="OR",
                    reason="Empty OR condition evaluates to FALSE"
                )
            child_results = [evaluate_condition(c, context) for c in children]
            
            # If any child is MATCHED, OR succeeds immediately
            if any(cr.matched for cr in child_results):
                return ConditionEvaluationResult(
                    matched=True, status=EvaluationStatus.MATCHED, rule_type="OR",
                    reason="At least one OR operand matched"
                )
            
            # If any child was DATA_UNAVAILABLE and none matched
            if any(cr.status == EvaluationStatus.DATA_UNAVAILABLE for cr in child_results):
                return ConditionEvaluationResult(
                    matched=False, status=EvaluationStatus.DATA_UNAVAILABLE, rule_type="OR",
                    reason="OR operand unavailable and no other operand matched"
                )

            return ConditionEvaluationResult(
                matched=False, status=EvaluationStatus.NOT_MATCHED, rule_type="OR",
                reason=f"All {len(child_results)} OR operand(s) failed"
            )

    # --- 2. PRICE COMPARISON ---
    if rule_type == "PRICE_COMPARISON":
        if context.current_price is None:
            return ConditionEvaluationResult(
                matched=False, status=EvaluationStatus.DATA_UNAVAILABLE, rule_type=rule_type,
                reason="Current market price is unavailable in context"
            )
        
        curr_p = float(context.current_price)
        threshold = float(rule.value if rule.value is not None else float(rule.price or 0.0))
        op = rule.operator or ">"
        matched = evaluate_comparison_operator(curr_p, threshold, op)
        status = EvaluationStatus.MATCHED if matched else EvaluationStatus.NOT_MATCHED

        return ConditionEvaluationResult(
            matched=matched, status=status, rule_type=rule_type,
            current_value=curr_p, threshold=threshold, operator=op,
            reason=f"Price ({curr_p}) {op} Threshold ({threshold}) -> {matched}"
        )

    # --- 3. PRICE CROSSOVER ---
    if rule_type == "PRICE_CROSSOVER":
        if context.current_price is None or context.previous_price is None:
            return ConditionEvaluationResult(
                matched=False, status=EvaluationStatus.DATA_UNAVAILABLE, rule_type=rule_type,
                reason="Price crossover requires both current_price and previous_price"
            )

        curr_p = float(context.current_price)
        prev_p = float(context.previous_price)
        threshold = float(rule.value if rule.value is not None else float(rule.price or 0.0))
        op = str(rule.operator or "CROSS_ABOVE").upper()

        if "ABOVE" in op: # CROSS_ABOVE / CROSSES_ABOVE
            matched = (prev_p <= threshold and curr_p > threshold)
        elif "BELOW" in op: # CROSS_BELOW / CROSSES_BELOW
            matched = (prev_p >= threshold and curr_p < threshold)
        else:
            matched = False

        status = EvaluationStatus.MATCHED if matched else EvaluationStatus.NOT_MATCHED
        return ConditionEvaluationResult(
            matched=matched, status=status, rule_type=rule_type,
            current_value=curr_p, previous_value=prev_p, threshold=threshold, operator=op,
            reason=f"Price crossover: prev={prev_p}, curr={curr_p}, threshold={threshold}, op={op} -> {matched}"
        )

    # --- 4. INDICATOR COMPARISON ---
    if rule_type == "INDICATOR_COMPARISON":
        # Check if comparing two indicators (e.g. 9 EMA > 21 EMA)
        if rule.left and rule.right:
            left_val = context.get_indicator(rule.left.indicator, rule.left.period)
            right_val = context.get_indicator(rule.right.indicator, rule.right.period)
            if left_val is None or right_val is None:
                return ConditionEvaluationResult(
                    matched=False, status=EvaluationStatus.DATA_UNAVAILABLE, rule_type=rule_type,
                    reason=f"Indicator comparison operands unavailable: left={left_val}, right={right_val}"
                )
            op = rule.operator or ">"
            matched = evaluate_comparison_operator(left_val, right_val, op)
            status = EvaluationStatus.MATCHED if matched else EvaluationStatus.NOT_MATCHED
            return ConditionEvaluationResult(
                matched=matched, status=status, rule_type=rule_type,
                current_value=left_val, threshold=right_val, operator=op,
                reason=f"{rule.left.indicator}({left_val}) {op} {rule.right.indicator}({right_val}) -> {matched}"
            )

        # Comparing single indicator against static value (e.g. RSI > 60)
        curr_val = context.get_indicator(rule.indicator, rule.period, is_previous=False)
        if curr_val is None:
            return ConditionEvaluationResult(
                matched=False, status=EvaluationStatus.DATA_UNAVAILABLE, rule_type=rule_type,
                reason=f"Indicator data unavailable for '{rule.indicator}' (period={rule.period})"
            )

        threshold = float(rule.value if rule.value is not None else 0.0)
        op = rule.operator or ">"
        matched = evaluate_comparison_operator(curr_val, threshold, op)
        status = EvaluationStatus.MATCHED if matched else EvaluationStatus.NOT_MATCHED

        return ConditionEvaluationResult(
            matched=matched, status=status, rule_type=rule_type,
            current_value=curr_val, threshold=threshold, operator=op,
            reason=f"{rule.indicator}({curr_val}) {op} Threshold({threshold}) -> {matched}"
        )

    # --- 5. INDICATOR CROSSOVER ---
    if rule_type == "INDICATOR_CROSSOVER":
        op = str(rule.operator or "CROSS_ABOVE").upper()

        # Crossover between two indicators (e.g. 9 EMA crosses 21 EMA)
        if rule.left and rule.right:
            prev_left = context.get_indicator(rule.left.indicator, rule.left.period, is_previous=True)
            curr_left = context.get_indicator(rule.left.indicator, rule.left.period, is_previous=False)
            prev_right = context.get_indicator(rule.right.indicator, rule.right.period, is_previous=True)
            curr_right = context.get_indicator(rule.right.indicator, rule.right.period, is_previous=False)

            if any(v is None for v in (prev_left, curr_left, prev_right, curr_right)):
                return ConditionEvaluationResult(
                    matched=False, status=EvaluationStatus.DATA_UNAVAILABLE, rule_type=rule_type,
                    reason=f"Dual indicator crossover data unavailable: prev_left={prev_left}, curr_left={curr_left}, prev_right={prev_right}, curr_right={curr_right}"
                )

            if "ABOVE" in op:
                matched = (prev_left <= prev_right and curr_left > curr_right)
            elif "BELOW" in op:
                matched = (prev_left >= prev_right and curr_left < curr_right)
            else:
                matched = False

            status = EvaluationStatus.MATCHED if matched else EvaluationStatus.NOT_MATCHED
            return ConditionEvaluationResult(
                matched=matched, status=status, rule_type=rule_type,
                current_value=curr_left, previous_value=prev_left, threshold=curr_right, operator=op,
                reason=f"Dual crossover: left({prev_left}->{curr_left}) vs right({prev_right}->{curr_right}) -> {matched}"
            )

        # Crossover of single indicator with numeric threshold (e.g. RSI crosses above 60)
        prev_val = context.get_indicator(rule.indicator, rule.period, is_previous=True)
        curr_val = context.get_indicator(rule.indicator, rule.period, is_previous=False)

        if prev_val is None or curr_val is None:
            return ConditionEvaluationResult(
                matched=False, status=EvaluationStatus.DATA_UNAVAILABLE, rule_type=rule_type,
                reason=f"Crossover requires both previous and current values for indicator '{rule.indicator}' (prev={prev_val}, curr={curr_val})"
            )

        threshold = float(rule.value if rule.value is not None else 0.0)

        if "ABOVE" in op:
            matched = (prev_val <= threshold and curr_val > threshold)
        elif "BELOW" in op:
            matched = (prev_val >= threshold and curr_val < threshold)
        else:
            matched = False

        status = EvaluationStatus.MATCHED if matched else EvaluationStatus.NOT_MATCHED
        return ConditionEvaluationResult(
            matched=matched, status=status, rule_type=rule_type,
            current_value=curr_val, previous_value=prev_val, threshold=threshold, operator=op,
            reason=f"{rule.indicator} crossover: prev={prev_val}, curr={curr_val}, threshold={threshold}, op={op} -> {matched}"
        )

    # Fallback / Default
    return ConditionEvaluationResult(
        matched=False, status=EvaluationStatus.ERROR, rule_type=rule_type,
        reason=f"Unsupported rule type '{rule_type}'"
    )
