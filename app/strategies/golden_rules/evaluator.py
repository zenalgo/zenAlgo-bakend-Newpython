import json
import logging
from typing import Union, Optional, Dict, Any

from app.market_data.enums import MarketEventType
from app.strategies.models import StrategyGoldenRule
from app.strategies.rules.rule_schema import ParsedRule
from app.strategies.engine.context import MarketContext
from app.strategies.golden_rules.enums import GoldenRuleStatus
from app.strategies.golden_rules.schemas import GoldenRuleEvaluationResult

logger = logging.getLogger(__name__)

def evaluate_single_golden_rule(
    rule: Union[StrategyGoldenRule, ParsedRule],
    context: MarketContext
) -> GoldenRuleEvaluationResult:
    """
    Pure deterministic evaluation of a single mandatory Golden Rule against MarketContext.
    """
    # Extract metadata fields depending on whether model or schema was passed
    if isinstance(rule, StrategyGoldenRule):
        rule_id = rule.id
        raw_text = rule.raw_text
        confirmation = str(rule.confirmation or "CANDLE_CLOSE").upper()
        evaluation = str(rule.evaluation or "CANDLE_CLOSE").upper()
        mandatory = bool(rule.mandatory if rule.mandatory is not None else True)
        rule_val = None
        rule_op = None
        if rule.rule_json:
            try:
                rj = json.loads(rule.rule_json)
                rule_val = rj.get("value")
                rule_op = rj.get("operator")
            except Exception:
                pass
    else:
        rule_id = None
        raw_text = rule.confirmation or rule.type
        confirmation = str(rule.confirmation or rule.type or "CANDLE_CLOSE").upper()
        evaluation = str(rule.evaluation or "CANDLE_CLOSE").upper()
        mandatory = bool(rule.mandatory if rule.mandatory is not None else True)
        rule_val = rule.value
        rule_op = rule.operator

    # --- 1. CANDLE CLOSE ENFORCEMENT ---
    if evaluation == "CANDLE_CLOSE":
        if context.candle is None or context.candle.event_type != MarketEventType.CANDLE_CLOSED:
            return GoldenRuleEvaluationResult(
                rule_id=rule_id,
                raw_text=raw_text,
                confirmation=confirmation,
                evaluation_type=evaluation,
                mandatory=mandatory,
                status=GoldenRuleStatus.DATA_UNAVAILABLE,
                reason=f"Golden Rule requires CANDLE_CLOSED event, received {context.candle.event_type.value if context.candle else 'None'}"
            )

    # --- 2. EVALUATE CONFIRMATION CRITERIA ---

    # A. Wait for candle close / No entry before candle close
    if confirmation in ("WAIT_FOR_CANDLE_CLOSE", "NO_ENTRY_BEFORE_CANDLE_CLOSE"):
        is_closed = (context.candle is not None and context.candle.event_type == MarketEventType.CANDLE_CLOSED)
        status = GoldenRuleStatus.PASS if is_closed else GoldenRuleStatus.FAIL
        return GoldenRuleEvaluationResult(
            rule_id=rule_id,
            raw_text=raw_text,
            confirmation=confirmation,
            evaluation_type=evaluation,
            mandatory=mandatory,
            status=status,
            reason=f"Candle closure confirmed: {is_closed}"
        )

    # B. Volume Confirmation (e.g. Volume above average)
    if "VOLUME" in confirmation:
        observed_vol = float(context.candle.volume) if (context.candle and context.candle.volume is not None) else None
        if observed_vol is None and "VOLUME" in context.indicators:
            try:
                observed_vol = float(context.indicators["VOLUME"])
            except (ValueError, TypeError):
                pass

        avg_vol = float(rule_val) if rule_val is not None else None
        if avg_vol is None:
            avg_ind = context.indicators.get("AVG_VOLUME") or context.indicators.get("VOLUME_SMA") or context.indicators.get("VOLUME_AVG")
            if avg_ind is not None:
                try:
                    avg_vol = float(avg_ind)
                except (ValueError, TypeError):
                    pass

        if observed_vol is None or avg_vol is None:
            return GoldenRuleEvaluationResult(
                rule_id=rule_id,
                raw_text=raw_text,
                confirmation=confirmation,
                evaluation_type=evaluation,
                mandatory=mandatory,
                status=GoldenRuleStatus.DATA_UNAVAILABLE,
                observed_value=observed_vol,
                expected_value=avg_vol,
                reason=f"Missing volume or average volume data: observed_vol={observed_vol}, avg_vol={avg_vol}"
            )

        passed = observed_vol > avg_vol
        status = GoldenRuleStatus.PASS if passed else GoldenRuleStatus.FAIL
        return GoldenRuleEvaluationResult(
            rule_id=rule_id,
            raw_text=raw_text,
            confirmation=confirmation,
            evaluation_type=evaluation,
            mandatory=mandatory,
            status=status,
            observed_value=observed_vol,
            expected_value=avg_vol,
            threshold=avg_vol,
            reason=f"Volume ({observed_vol}) > Avg Volume ({avg_vol}) -> {passed}"
        )

    # C. Candle closure above breakout level / numeric level
    if "ABOVE" in confirmation or (rule_op and "ABOVE" in rule_op.upper()):
        observed = float(context.candle.close) if (context.candle and context.candle.close is not None) else (
            float(context.current_price) if context.current_price is not None else None
        )
        
        # Determine threshold
        threshold = float(rule_val) if rule_val is not None else None
        if threshold is None:
            threshold_ind = context.indicators.get("BREAKOUT_LEVEL") or context.indicators.get("RESISTANCE") or context.indicators.get("LEVEL")
            if threshold_ind is not None:
                try:
                    threshold = float(threshold_ind)
                except (ValueError, TypeError):
                    pass

        if observed is None or threshold is None:
            return GoldenRuleEvaluationResult(
                rule_id=rule_id,
                raw_text=raw_text,
                confirmation=confirmation,
                evaluation_type=evaluation,
                mandatory=mandatory,
                status=GoldenRuleStatus.DATA_UNAVAILABLE,
                observed_value=observed,
                expected_value=threshold,
                reason=f"Missing price or breakout level: observed={observed}, breakout_level={threshold}"
            )

        passed = observed > threshold
        status = GoldenRuleStatus.PASS if passed else GoldenRuleStatus.FAIL
        return GoldenRuleEvaluationResult(
            rule_id=rule_id,
            raw_text=raw_text,
            confirmation=confirmation,
            evaluation_type=evaluation,
            mandatory=mandatory,
            status=status,
            observed_value=observed,
            expected_value=threshold,
            threshold=threshold,
            reason=f"Candle close ({observed}) > Breakout Level ({threshold}) -> {passed}"
        )

    # D. Candle closure below breakout level
    if "BELOW" in confirmation or (rule_op and "BELOW" in rule_op.upper()):
        observed = float(context.candle.close) if (context.candle and context.candle.close is not None) else (
            float(context.current_price) if context.current_price is not None else None
        )
        threshold = float(rule_val) if rule_val is not None else None
        if threshold is None:
            threshold_ind = context.indicators.get("BREAKOUT_LEVEL") or context.indicators.get("SUPPORT") or context.indicators.get("LEVEL")
            if threshold_ind is not None:
                try:
                    threshold = float(threshold_ind)
                except (ValueError, TypeError):
                    pass

        if observed is None or threshold is None:
            return GoldenRuleEvaluationResult(
                rule_id=rule_id,
                raw_text=raw_text,
                confirmation=confirmation,
                evaluation_type=evaluation,
                mandatory=mandatory,
                status=GoldenRuleStatus.DATA_UNAVAILABLE,
                observed_value=observed,
                expected_value=threshold,
                reason=f"Missing price or breakout level: observed={observed}, breakout_level={threshold}"
            )

        passed = observed < threshold
        status = GoldenRuleStatus.PASS if passed else GoldenRuleStatus.FAIL
        return GoldenRuleEvaluationResult(
            rule_id=rule_id,
            raw_text=raw_text,
            confirmation=confirmation,
            evaluation_type=evaluation,
            mandatory=mandatory,
            status=status,
            observed_value=observed,
            expected_value=threshold,
            threshold=threshold,
            reason=f"Candle close ({observed}) < Breakout Level ({threshold}) -> {passed}"
        )

    # E. Default / Fallback
    return GoldenRuleEvaluationResult(
        rule_id=rule_id,
        raw_text=raw_text,
        confirmation=confirmation,
        evaluation_type=evaluation,
        mandatory=mandatory,
        status=GoldenRuleStatus.PASS,
        reason=f"Golden rule confirmation '{confirmation}' validated"
    )
