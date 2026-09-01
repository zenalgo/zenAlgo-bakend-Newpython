from typing import List, Optional
from app.strategies.rules.rule_schema import ParsedRule, StrategyRule

SUPPORTED_TIMEFRAMES = {"1m", "3m", "5m", "15m", "30m", "1h"}
SUPPORTED_INDICATORS = {"EMA", "SMA", "RSI", "MACD", "VWAP", "BOLLINGER_BANDS", "PRICE", "VIX", "ATR"}
SUPPORTED_OPERATORS = {
    "PRICE_ABOVE", "PRICE_BELOW", 
    "CROSS_ABOVE", "CROSS_BELOW", 
    "GREATER_THAN", "LESS_THAN", 
    "ABOVE", "BELOW"
}
SUPPORTED_CONFIRMATIONS = {
    "CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL",
    "CANDLE_CLOSURE_BELOW_BREAKOUT_LEVEL",
    "WAIT_FOR_CANDLE_CLOSE",
    "NO_ENTRY_BEFORE_CANDLE_CLOSE"
}

def validate_parsed_rule(rule: ParsedRule) -> List[str]:
    """Validates structural correctness of a parsed rule, returning error messages."""
    errors = []

    if rule.type == "GOLDEN_RULE":
        if rule.mandatory is not True:
            errors.append("Golden Rule must be mandatory (mandatory=true)")
        if rule.evaluation != "CANDLE_CLOSE":
            errors.append(f"Golden Rule evaluation style '{rule.evaluation}' is not supported. Use 'CANDLE_CLOSE'.")
        if not rule.confirmation or rule.confirmation.upper() not in SUPPORTED_CONFIRMATIONS:
            errors.append(f"Golden Rule confirmation code '{rule.confirmation}' is not supported")
        if rule.timeframe not in SUPPORTED_TIMEFRAMES:
            errors.append(f"Golden Rule timeframe '{rule.timeframe}' is invalid")
        return errors

    if rule.type in ("AND", "OR", "NOT"):
        if not rule.conditions:
            errors.append(f"Logical node '{rule.type}' must contain child conditions")
        else:
            for cond in rule.conditions:
                errors.extend(validate_parsed_rule(cond))
        return errors

    # Validate Timeframe
    if rule.timeframe and rule.timeframe not in SUPPORTED_TIMEFRAMES:
        errors.append(f"Unsupported timeframe '{rule.timeframe}'")

    # Validate Indicators & Operator Types
    if rule.type in ("INDICATOR_COMPARISON", "INDICATOR_CROSSOVER"):
        if not rule.indicator or rule.indicator.upper() not in SUPPORTED_INDICATORS:
            errors.append(f"Unsupported indicator '{rule.indicator}'")
        if rule.period is not None and rule.period <= 0:
            errors.append(f"Period must be greater than zero, got {rule.period}")
        if rule.operator and rule.operator not in SUPPORTED_OPERATORS:
            errors.append(f"Unsupported operator '{rule.operator}' for indicator rule")

    elif rule.type in ("PRICE_COMPARISON", "PRICE_CROSSOVER"):
        if rule.operator and rule.operator not in SUPPORTED_OPERATORS:
            errors.append(f"Unsupported operator '{rule.operator}' for price rule")

    # Target indicator comparison check
    if rule.price and rule.price.upper() not in SUPPORTED_INDICATORS and rule.price.upper() not in ("SPOT", "PRICE"):
        # If it's not a known indicator name or price ref
        pass

    return errors

def validate_strategy_rule(rule: StrategyRule) -> StrategyRule:
    """Updates validation status and errors list on a StrategyRule."""
    if not rule.parsedRule:
        rule.validationStatus = "INVALID"
        if not rule.errors:
            rule.errors = ["Rule parsed representation is missing"]
        return rule

    errs = validate_parsed_rule(rule.parsedRule)
    if errs:
        rule.validationStatus = "INVALID"
        rule.errors = errs
    else:
        rule.validationStatus = "VALID"
        rule.errors = []
    return rule
