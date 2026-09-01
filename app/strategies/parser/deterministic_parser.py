import re
import uuid
from typing import Optional, List, Union
from app.strategies.parser.parser_result import ParserResult
from app.strategies.rules.rule_schema import ParsedRule
from app.strategies.parser import regex_patterns as pat

def parse_logical_expression(text: str, default_timeframe: str = "15m") -> Optional[ParsedRule]:
    """Tokenizes and parses logical AND/OR expressions into nested ParsedRules."""
    cleaned = text.strip()
    if not cleaned:
        return None
        
    # Standardize operators
    cleaned = re.sub(r"\s+AND\s+", " AND ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+OR\s+", " OR ", cleaned, flags=re.IGNORECASE)
    
    # Helper to split expression by a logical operator at the current parenthesis depth
    def split_by_op(expr: str, op: str) -> List[str]:
        parts = []
        current = []
        depth = 0
        tokens = re.split(r"(\(|\)|\s+AND\s+|\s+OR\s+)", expr)
        
        for t in tokens:
            if not t:
                continue
            if t == '(':
                depth += 1
                current.append(t)
            elif t == ')':
                depth -= 1
                current.append(t)
            elif depth == 0 and t.strip().upper() == op:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(t)
        if current:
            parts.append("".join(current).strip())
        return [p for p in parts if p]

    # Strip wrapping parentheses
    if cleaned.startswith('(') and cleaned.endswith(')'):
        depth = 0
        matching = True
        for i, char in enumerate(cleaned):
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0 and i < len(cleaned) - 1:
                    matching = False
                    break
        if matching:
            return parse_logical_expression(cleaned[1:-1], default_timeframe)

    # Split OR (lowest precedence)
    or_parts = split_by_op(cleaned, "OR")
    if len(or_parts) > 1:
        child_rules = []
        for part in or_parts:
            child = parse_logical_expression(part, default_timeframe)
            if child:
                child_rules.append(child)
        return ParsedRule(type="OR", logic="OR", conditions=child_rules, timeframe=default_timeframe)

    # Split AND (higher precedence)
    and_parts = split_by_op(cleaned, "AND")
    if len(and_parts) > 1:
        child_rules = []
        for part in and_parts:
            child = parse_logical_expression(part, default_timeframe)
            if child:
                child_rules.append(child)
        return ParsedRule(type="AND", logic="AND", conditions=child_rules, timeframe=default_timeframe)

    # Leaf node parsing
    res = parse_deterministic_rule(cleaned, default_timeframe)
    if res.status == "SUPPORTED" and res.parsed_rule:
        return res.parsed_rule
        
    return ParsedRule(type="CONFIRMATION_RULE", confirmation=cleaned)

def parse_deterministic_rule(text: str, default_timeframe: str = "15m") -> ParserResult:
    """Parses standard rule strings against compiled regex patterns."""
    cleaned = text.strip()

    # Strip common sentence wrappers/prefixes to expose core condition
    prefix_pat = r"^(?:avoid\s+entry\s+if|avoid\s+if|only\s+enter\s+if|only\s+trade\s+if|do\s+not\s+enter\s+if|don't\s+enter\s+if)\s+"
    cleaned_cond = re.sub(prefix_pat, "", cleaned, flags=re.IGNORECASE).strip()

    # 1. Ambiguity Check: "RSI above 60" or "RSI below 40"
    if re.match(r"^RSI\s+(?:is\s+)?(above|below)\s+(\d+)$", cleaned_cond, re.IGNORECASE):
        op = cleaned_cond.split(" ")[-2].lower()
        val = cleaned_cond.split(" ")[-1]
        return ParserResult(
            status="INVALID",
            rawText=text,
            confidence=0.5,
            message="Clarification Required",
            choices=[
                f"RSI remains {op} {val}",
                f"RSI crosses {op} {val}"
            ],
            errors=["Ambiguous rule: Did you mean crossover or comparison?"]
        )

    # 2. Indicator to Indicator crossover (e.g. "9 EMA crosses above 21 EMA")
    m = pat.IND_IND_CROSS.match(cleaned_cond)
    if m:
        ind1_name = m.group(2).upper()
        ind1_period = int(m.group(1)) if m.group(1) else (int(m.group(3)) if m.group(3) else 14)
        
        verb = m.group(4).lower()
        ind2_name = m.group(6).upper()
        ind2_period = int(m.group(5)) if m.group(5) else (int(m.group(7)) if m.group(7) else 14)
        
        tf = m.group(8) if m.group(8) else default_timeframe
        
        is_cross = "cross" in verb or "crossover" in verb
        op = ("CROSS_ABOVE" if "above" in verb else "CROSS_BELOW") if is_cross else ("PRICE_ABOVE" if "above" in verb else "PRICE_BELOW")
        
        from app.strategies.rules.rule_schema import IndicatorOperand
        parsed = ParsedRule(
            type="INDICATOR_CROSSOVER" if is_cross else "INDICATOR_COMPARISON",
            indicator=ind1_name,
            period=ind1_period,
            operator=op,
            price=ind2_name,
            value=float(ind2_period),
            timeframe=tf,
            left=IndicatorOperand(indicator=ind1_name, period=ind1_period, timeframe=tf),
            right=IndicatorOperand(indicator=ind2_name, period=ind2_period, timeframe=tf)
        )
        return ParserResult(status="SUPPORTED", rawText=text, parsedRule=parsed)

    # 3. Indicator to Constant Crossover (e.g. "RSI crosses above 60")
    m = pat.IND_CONST_CROSS.match(cleaned_cond)
    if m:
        ind_name = m.group(1).upper()
        period = int(m.group(2)) if m.group(2) else 14
        verb = m.group(3).lower()
        val = float(m.group(4))
        tf = m.group(5) if m.group(5) else default_timeframe
        
        op = "CROSS_ABOVE" if "above" in verb else "CROSS_BELOW"
        parsed = ParsedRule(
            type="INDICATOR_CROSSOVER",
            indicator=ind_name,
            period=period,
            operator=op,
            value=val,
            timeframe=tf
        )
        return ParserResult(status="SUPPORTED", rawText=text, parsedRule=parsed)

    # 4. Indicator to Constant Comparison (e.g. "RSI above 60", "VIX < 11.5")
    m = pat.IND_CONST_COMP.match(cleaned_cond)
    if m:
        ind_name = m.group(1).upper()
        period = int(m.group(2)) if m.group(2) else 14
        verb = m.group(3).lower()
        val = float(m.group(4))
        tf = m.group(5) if m.group(5) else default_timeframe
        
        if verb in ("<", "<="):
            op = "LESS_THAN"
        elif verb in (">", ">="):
            op = "GREATER_THAN"
        else:
            op = "GREATER_THAN" if "above" in verb or "greater" in verb else "LESS_THAN"
            
        parsed = ParsedRule(
            type="INDICATOR_COMPARISON",
            indicator=ind_name,
            period=period,
            operator=op,
            value=val,
            timeframe=tf
        )
        return ParserResult(status="SUPPORTED", rawText=text, parsedRule=parsed)

    # 5. Price to Indicator Crossover (e.g. "Price crosses above 20 EMA")
    m = pat.PRICE_IND_CROSS.match(cleaned_cond)
    if m:
        price_ref = m.group(1).upper()
        verb = m.group(2).lower()
        ind_name = m.group(4).upper()
        period = int(m.group(3)) if m.group(3) else (int(m.group(5)) if m.group(5) else 200)
        tf = m.group(6) if m.group(6) else default_timeframe
        
        op = "CROSS_ABOVE" if "above" in verb else "CROSS_BELOW"
        parsed = ParsedRule(
            type="PRICE_CROSSOVER",
            price=price_ref,
            operator=op,
            indicator=ind_name,
            period=period,
            timeframe=tf
        )
        return ParserResult(status="SUPPORTED", rawText=text, parsedRule=parsed)

    # 6. Price to Indicator Comparison (e.g. "Price above 20 EMA")
    m = pat.PRICE_IND_COMP.match(cleaned_cond)
    if m:
        price_ref = m.group(1).upper()
        verb = m.group(2).lower()
        ind_name = m.group(4).upper()
        period = int(m.group(3)) if m.group(3) else (int(m.group(5)) if m.group(5) else 200)
        tf = m.group(6) if m.group(6) else default_timeframe
        
        op = "PRICE_ABOVE" if "above" in verb or "greater" in verb else "PRICE_BELOW"
        parsed = ParsedRule(
            type="PRICE_COMPARISON",
            price=price_ref,
            operator=op,
            indicator=ind_name,
            period=period,
            timeframe=tf
        )
        return ParserResult(status="SUPPORTED", rawText=text, parsedRule=parsed)

    # 7. Price to Constant Crossover
    m = pat.PRICE_CONST_CROSS.match(cleaned_cond)
    if m:
        price_ref = m.group(1).upper()
        verb = m.group(2).lower()
        val = float(m.group(3))
        tf = m.group(4) if m.group(4) else default_timeframe
        
        op = "CROSS_ABOVE" if "above" in verb else "CROSS_BELOW"
        parsed = ParsedRule(
            type="PRICE_CROSSOVER",
            price=price_ref,
            operator=op,
            value=val,
            timeframe=tf
        )
        return ParserResult(status="SUPPORTED", rawText=text, parsedRule=parsed)

    # 8. Price to Constant Comparison
    m = pat.PRICE_CONST_COMP.match(cleaned_cond)
    if m:
        price_ref = m.group(1).upper()
        verb = m.group(2).lower()
        val = float(m.group(3))
        tf = m.group(4) if m.group(4) else default_timeframe
        
        op = "GREATER_THAN" if "above" in verb or "greater" in verb else "LESS_THAN"
        parsed = ParsedRule(
            type="PRICE_COMPARISON",
            price=price_ref,
            operator=op,
            value=val,
            timeframe=tf
        )
        return ParserResult(status="SUPPORTED", rawText=text, parsedRule=parsed)

    # 9. Bollinger Bands Comparison/Crossover
    m = pat.BB_RULE.match(cleaned_cond)
    if m:
        price_ref = m.group(1).upper()
        verb = m.group(2).lower()
        band = "UPPER" if "upper" in m.group(3).lower() else "LOWER"
        period = int(m.group(4)) if m.group(4) else 20
        tf = m.group(5) if m.group(5) else default_timeframe
        
        is_cross = "cross" in verb or "crossover" in verb
        op = ("CROSS_ABOVE" if "above" in verb else "CROSS_BELOW") if is_cross else ("PRICE_ABOVE" if "above" in verb else "PRICE_BELOW")
        
        parsed = ParsedRule(
            type="PRICE_CROSSOVER" if is_cross else "PRICE_COMPARISON",
            price=price_ref,
            operator=op,
            indicator="BOLLINGER_BANDS",
            period=period,
            confirmation=f"{band}_BAND",
            timeframe=tf
        )
        return ParserResult(status="SUPPORTED", rawText=text, parsedRule=parsed)

    # 10. MACD Crossover
    m = pat.MACD_CROSS.match(cleaned_cond)
    if m:
        direction = m.group(2).lower()
        tf = m.group(3) if m.group(3) else default_timeframe
        
        parsed = ParsedRule(
            type="INDICATOR_CROSSOVER",
            indicator="MACD",
            operator="CROSS_ABOVE" if direction == "bullish" else "CROSS_BELOW",
            timeframe=tf
        )
        return ParserResult(status="SUPPORTED", rawText=text, parsedRule=parsed)

    # 11. Confirmation Prefix Check
    m = pat.CONFIRMATION_PREFIX.match(cleaned_cond)
    if m:
        action = m.group(2).strip()
        parsed = ParsedRule(
            type="CONFIRMATION_RULE",
            confirmation=action.upper().replace(" ", "_")
        )
        return ParserResult(status="SUPPORTED", rawText=text, parsedRule=parsed)

    # 12. Time Exit Match
    m = pat.TIME_EXIT_PAT.match(cleaned_cond)
    if m:
        t_val = m.group(1)
        parsed = ParsedRule(
            type="TIME_EXIT",
            operator="EQUAL",
            confirmation=t_val
        )
        return ParserResult(status="SUPPORTED", rawText=text, parsedRule=parsed)

    # Unrecognized / Unsupported -> Trigger Optional LLM Fallback
    llm_parsed = call_llm_fallback(text, default_timeframe)
    if llm_parsed:
        return ParserResult(
            status="SUPPORTED",
            parser="LLM_FALLBACK",
            rawText=text,
            parsedRule=llm_parsed,
            confidence=0.90
        )

    return ParserResult(
        status="UNSUPPORTED",
        rawText=text,
        message="Rule pattern is not supported",
        errors=["Regex pattern matching failed and no LLM fallback succeeded"]
    )

def call_llm_fallback(text: str, default_timeframe: str = "15m") -> Optional[ParsedRule]:
    """Optional LLM translation fallback when local patterns fail. Safe & isolated."""
    from app.core.config import settings
    import httpx
    import json
    
    # Fast exit if no keys configured to avoid latency
    if not settings.GEMINI_API_KEY and not settings.OPENAI_API_KEY:
        return None
        
    prompt = f"""
    Translate the following natural language trading rule into a structured JSON payload conforming to the Pydantic schema details:
    Rule: "{text}"
    Default Timeframe: "{default_timeframe}"
    
    Target Schema:
    {{
      "type": "INDICATOR_CROSSOVER" | "INDICATOR_COMPARISON" | "PRICE_COMPARISON" | "PRICE_CROSSOVER" | "CONFIRMATION_RULE",
      "indicator": Optional[string],
      "period": Optional[integer],
      "operator": Optional["CROSS_ABOVE" | "CROSS_BELOW" | "PRICE_ABOVE" | "PRICE_BELOW" | "GREATER_THAN" | "LESS_THAN"],
      "value": Optional[float],
      "timeframe": string,
      "price": Optional[string],
      "evaluation": "CANDLE_CLOSE",
      "confirmation": Optional[string]
    }}
    
    Respond only with a single, valid JSON block. Do not include markdown code block formatting (like ```json).
    """

    if settings.GEMINI_API_KEY:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        try:
            res = httpx.post(url, json=payload, timeout=5.0)
            if res.status_code == 200:
                resp_data = res.json()
                text_out = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                # Clean up wrapping markers if LLM returns them anyway
                text_out = re.sub(r"^```(?:json)?\s*|\s*```$", "", text_out, flags=re.MULTILINE)
                parsed_json = json.loads(text_out)
                return ParsedRule.model_validate(parsed_json)
        except Exception:
            pass

    elif settings.OPENAI_API_KEY:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"}
        }
        try:
            res = httpx.post(url, headers=headers, json=payload, timeout=5.0)
            if res.status_code == 200:
                resp_data = res.json()
                text_out = resp_data["choices"][0]["message"]["content"].strip()
                parsed_json = json.loads(text_out)
                return ParsedRule.model_validate(parsed_json)
        except Exception:
            pass

    return None
