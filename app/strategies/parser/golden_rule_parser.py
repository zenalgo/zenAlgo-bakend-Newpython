import re
from typing import Optional
from app.strategies.parser.parser_result import ParserResult
from app.strategies.rules.rule_schema import ParsedRule

def parse_golden_rule(text: str, default_timeframe: str = "15m") -> ParserResult:
    """Parses natural language execution constraints into structured Golden Rules."""
    cleaned = text.strip().lower()

    # Timeframe extraction helper
    tf = default_timeframe
    tf_match = re.search(r"on\s+([135mhd0-9]+)\s+(?:candle|chart|timeframe)", cleaned)
    if tf_match:
        tf = tf_match.group(1)

    # 1. Candle closure above breakout level
    if "closure above breakout level" in cleaned or "close above breakout level" in cleaned:
        parsed = ParsedRule(
            type="GOLDEN_RULE",
            logic=None,
            conditions=None,
            indicator=None,
            period=None,
            operator=None,
            value=None,
            timeframe=tf,
            price=None,
            evaluation="CANDLE_CLOSE",
            confirmation="CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL"
        )
        return ParserResult(
            status="SUPPORTED",
            parser="DETERMINISTIC",
            rawText=text,
            parsedRule=parsed,
            confidence=1.0,
            validationStatus="VALID",
            normalizedText="Candle closure above breakout level"
        )

    # 2. Candle closure below breakout level
    if "closure below breakout level" in cleaned or "close below breakout level" in cleaned:
        parsed = ParsedRule(
            type="GOLDEN_RULE",
            logic=None,
            conditions=None,
            indicator=None,
            period=None,
            operator=None,
            value=None,
            timeframe=tf,
            price=None,
            evaluation="CANDLE_CLOSE",
            confirmation="CANDLE_CLOSURE_BELOW_BREAKOUT_LEVEL"
        )
        return ParserResult(
            status="SUPPORTED",
            parser="DETERMINISTIC",
            rawText=text,
            parsedRule=parsed,
            confidence=1.0,
            validationStatus="VALID",
            normalizedText="Candle closure below breakout level"
        )

    # 3. Wait for candle close
    if cleaned == "wait for candle close" or cleaned == "wait for candle closure":
        parsed = ParsedRule(
            type="GOLDEN_RULE",
            logic=None,
            conditions=None,
            indicator=None,
            period=None,
            operator=None,
            value=None,
            timeframe=tf,
            price=None,
            evaluation="CANDLE_CLOSE",
            confirmation="WAIT_FOR_CANDLE_CLOSE"
        )
        return ParserResult(
            status="SUPPORTED",
            parser="DETERMINISTIC",
            rawText=text,
            parsedRule=parsed,
            confidence=1.0,
            validationStatus="VALID",
            normalizedText="Wait for candle close"
        )

    # 4. Do not enter before candle close
    if "do not enter before candle close" in cleaned or "don't enter before candle close" in cleaned:
        parsed = ParsedRule(
            type="GOLDEN_RULE",
            logic=None,
            conditions=None,
            indicator=None,
            period=None,
            operator=None,
            value=None,
            timeframe=tf,
            price=None,
            evaluation="CANDLE_CLOSE",
            confirmation="NO_ENTRY_BEFORE_CANDLE_CLOSE"
        )
        return ParserResult(
            status="SUPPORTED",
            parser="DETERMINISTIC",
            rawText=text,
            parsedRule=parsed,
            confidence=1.0,
            validationStatus="VALID",
            normalizedText="Do not enter before candle close"
        )

    return ParserResult(
        status="UNSUPPORTED",
        parser="DETERMINISTIC",
        rawText=text,
        message="Golden Rule pattern is not supported",
        errors=["Unrecognized Golden Rule criteria phrasing"]
    )

def is_golden_rule_text(text: str) -> bool:
    """Helper to detect if a natural language condition matches a Golden Rule pattern."""
    cleaned = text.strip().lower()
    phrases = [
        "candle closure above breakout level",
        "candle closure below breakout level",
        "close above breakout level",
        "close below breakout level",
        "wait for candle close",
        "wait for candle closure",
        "do not enter before candle close",
        "don't enter before candle close"
    ]
    return any(p in cleaned for p in phrases)
