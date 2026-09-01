from app.strategies.rules.rule_schema import ParsedRule

def normalize_parsed_rule(rule: ParsedRule) -> str:
    """Converts a parsed rule structure into a normalized natural language string."""
    if not rule:
        return ""

    if rule.type == "AND" and rule.conditions:
        parts = [normalize_parsed_rule(c) for c in rule.conditions]
        return " AND ".join(f"({p})" if " " in p else p for p in parts)
    
    elif rule.type == "OR" and rule.conditions:
        parts = [normalize_parsed_rule(c) for c in rule.conditions]
        return " OR ".join(f"({p})" if " " in p else p for p in parts)

    elif rule.type == "NOT" and rule.conditions:
        return f"NOT ({normalize_parsed_rule(rule.conditions[0])})"

    # Crossover rules
    if rule.type in ("INDICATOR_CROSSOVER", "PRICE_CROSSOVER"):
        op_text = "crosses above" if rule.operator == "CROSS_ABOVE" else "crosses below"
        tf_suffix = f" on {rule.timeframe} candle" if rule.timeframe else ""
        
        # Indicator to Indicator
        if rule.price in ("EMA", "SMA", "VWAP", "RSI"):
            return f"{rule.period} {rule.indicator} {op_text} {int(rule.value)} {rule.price}{tf_suffix}"
        
        # Indicator to Constant
        if rule.indicator:
            period_str = f"({rule.period})" if rule.period else ""
            return f"{rule.indicator}{period_str} {op_text} {rule.value}{tf_suffix}"
            
        # Price to Constant
        price_ref = rule.price if rule.price else "Price"
        return f"{price_ref} {op_text} {rule.value}{tf_suffix}"

    # Comparison rules
    elif rule.type in ("INDICATOR_COMPARISON", "PRICE_COMPARISON"):
        op_text = "above" if rule.operator in ("PRICE_ABOVE", "GREATER_THAN", "ABOVE") else "below"
        tf_suffix = f" on {rule.timeframe} timeframe" if rule.timeframe else ""
        
        # Indicator to Indicator
        if rule.price in ("EMA", "SMA", "VWAP", "RSI"):
            return f"{rule.period} {rule.indicator} is {op_text} {int(rule.value)} {rule.price}{tf_suffix}"
            
        # Indicator to Constant
        if rule.indicator:
            period_str = f"({rule.period})" if rule.period else ""
            return f"{rule.indicator}{period_str} is {op_text} {rule.value}{tf_suffix}"
            
        # Price to Constant
        price_ref = rule.price if rule.price else "Price"
        return f"{price_ref} is {op_text} {rule.value}{tf_suffix}"

    if rule.type == "GOLDEN_RULE" and rule.confirmation:
        if rule.confirmation == "CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL":
            return "Candle closure above breakout level"
        if rule.confirmation == "CANDLE_CLOSURE_BELOW_BREAKOUT_LEVEL":
            return "Candle closure below breakout level"
        if rule.confirmation == "WAIT_FOR_CANDLE_CLOSE":
            return "Wait for candle close"
        if rule.confirmation == "NO_ENTRY_BEFORE_CANDLE_CLOSE":
            return "Do not enter before candle close"
        return rule.confirmation.replace("_", " ").capitalize()

    if rule.confirmation:
        return rule.confirmation.replace("_", " ").capitalize()

    return "Unknown Rule"
