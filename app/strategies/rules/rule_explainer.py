from app.strategies.rules.rule_schema import ParsedRule

def explain_parsed_rule(rule: ParsedRule) -> str:
    """Generates a detailed human-readable explanation of how a rule is interpreted (e.g. crossover semantics)."""
    if not rule:
        return ""

    if rule.type == "AND" and rule.conditions:
        parts = [explain_parsed_rule(c) for c in rule.conditions]
        return " and ".join(parts)
        
    elif rule.type == "OR" and rule.conditions:
        parts = [explain_parsed_rule(c) for c in rule.conditions]
        return " or ".join(parts)

    elif rule.type == "NOT" and rule.conditions:
        return f"not ({explain_parsed_rule(rule.conditions[0])})"

    tf_clause = f" on {rule.timeframe} candle" if rule.timeframe else ""
    close_clause = " evaluated at candle close" if rule.evaluation == "CANDLE_CLOSE" else " evaluated in real-time"

    val_str = ""
    if rule.value is not None:
        val_str = str(int(rule.value)) if rule.value.is_integer() else str(rule.value)

    # Crossover Explanations
    if rule.type in ("INDICATOR_CROSSOVER", "PRICE_CROSSOVER"):
        if rule.operator == "CROSS_ABOVE":
            if rule.price in ("EMA", "SMA", "VWAP", "RSI"):
                exp = f"{rule.period} {rule.indicator} crosses from {int(rule.value)} {rule.price} or below to above {int(rule.value)} {rule.price}"
            elif rule.indicator:
                exp = f"{rule.indicator}({rule.period}) crosses from {val_str} or below to above {val_str}"
            else:
                price_ref = rule.price if rule.price else "Price"
                exp = f"{price_ref} crosses from {val_str} or below to above {val_str}"
        else: # CROSS_BELOW
            if rule.price in ("EMA", "SMA", "VWAP", "RSI"):
                exp = f"{rule.period} {rule.indicator} crosses from {int(rule.value)} {rule.price} or above to below {int(rule.value)} {rule.price}"
            elif rule.indicator:
                exp = f"{rule.indicator}({rule.period}) crosses from {val_str} or above to below {val_str}"
            else:
                price_ref = rule.price if rule.price else "Price"
                exp = f"{price_ref} crosses from {val_str} or above to below {val_str}"
        return f"{exp}{tf_clause}{close_clause}"

    # Comparison Explanations
    elif rule.type in ("INDICATOR_COMPARISON", "PRICE_COMPARISON"):
        comp = "greater than" if rule.operator in ("PRICE_ABOVE", "GREATER_THAN", "ABOVE") else "less than"
        if rule.price in ("EMA", "SMA", "VWAP", "RSI"):
            exp = f"{rule.period} {rule.indicator} remains {comp} {int(rule.value)} {rule.price}"
        elif rule.indicator:
            exp = f"{rule.indicator}({rule.period}) remains {comp} {val_str}"
        else:
            price_ref = rule.price if rule.price else "Price"
            exp = f"{price_ref} remains {comp} {val_str}"
        return f"{exp}{tf_clause}{close_clause}"

    if rule.confirmation:
        return f"Confirm that: {rule.confirmation.replace('_', ' ').lower()}"

    return "No interpretation available"
