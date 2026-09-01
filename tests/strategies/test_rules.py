import pytest
from app.strategies.parser.deterministic_parser import parse_deterministic_rule, parse_logical_expression
from app.strategies.rules.rule_schema import StrategyRule

def test_parse_simple_conditions_old():
    # 1. Indicator Cross
    r1 = parse_deterministic_rule("RSI(14) crosses above 60 on 15m candle")
    assert r1.status == "SUPPORTED"
    assert r1.parsed_rule.type == "INDICATOR_CROSSOVER"
    assert r1.parsed_rule.indicator == "RSI"
    assert r1.parsed_rule.period == 14
    assert r1.parsed_rule.operator == "CROSS_ABOVE"
    assert r1.parsed_rule.value == 60.0
    assert r1.parsed_rule.timeframe == "15m"

    # 1.5 Indicator-to-Indicator Cross
    r1_5 = parse_deterministic_rule("9 EMA crosses above 21 EMA")
    assert r1_5.status == "SUPPORTED"
    assert r1_5.parsed_rule.type == "INDICATOR_CROSSOVER"
    assert r1_5.parsed_rule.indicator == "EMA"
    assert r1_5.parsed_rule.period == 9
    assert r1_5.parsed_rule.operator == "CROSS_ABOVE"
    assert r1_5.parsed_rule.price == "EMA"
    assert r1_5.parsed_rule.value == 21.0

    # 2. Price Indicator Comparison
    r2 = parse_deterministic_rule("Price above 200 EMA")
    assert r2.status == "SUPPORTED"
    assert r2.parsed_rule.type == "PRICE_COMPARISON"
    assert r2.parsed_rule.price == "PRICE"
    assert r2.parsed_rule.indicator == "EMA"
    assert r2.parsed_rule.period == 200
    assert r2.parsed_rule.operator == "PRICE_ABOVE"
    assert r2.parsed_rule.timeframe == "15m" # Default

    # 3. Confirmation prefix checks
    r3_5 = parse_deterministic_rule("Check 15m candle close")
    assert r3_5.status == "SUPPORTED"
    assert r3_5.parsed_rule.type == "CONFIRMATION_RULE"
    assert r3_5.parsed_rule.confirmation == "15M_CANDLE_CLOSE"

    # 4. Ambiguity
    r4 = parse_deterministic_rule("RSI above 60")
    assert r4.status == "INVALID"
    assert r4.confidence == 0.5
