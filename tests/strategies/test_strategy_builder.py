import pytest
from app.strategies.parser.deterministic_parser import parse_deterministic_rule, parse_logical_expression
from app.strategies.rules.rule_validator import validate_strategy_rule
from app.strategies.rules.rule_explainer import explain_parsed_rule
from app.strategies.rules.rule_schema import StrategyRule, ParsedRule
from app.strategies.service import StrategyService
from app.strategies.schemas import StrategyRequest

def test_rsi_rules():
    # RSI above 60 (Ambiguity)
    r1 = parse_deterministic_rule("RSI above 60")
    assert r1.status == "INVALID"
    assert "crossover or comparison" in r1.errors[0]

    # RSI crosses above 60 (VALID crossover)
    r2 = parse_deterministic_rule("RSI crosses above 60")
    assert r2.status == "SUPPORTED"
    assert r2.parsed_rule.type == "INDICATOR_CROSSOVER"
    assert r2.parsed_rule.indicator == "RSI"
    assert r2.parsed_rule.operator == "CROSS_ABOVE"
    assert r2.parsed_rule.value == 60.0

    # RSI(14) crosses below 40
    r3 = parse_deterministic_rule("RSI(14) crosses below 40")
    assert r3.status == "SUPPORTED"
    assert r3.parsed_rule.period == 14
    assert r3.parsed_rule.operator == "CROSS_BELOW"
    assert r3.parsed_rule.value == 40.0

    # VIX comparison with prefix strip
    r4 = parse_deterministic_rule("Avoid entry if VIX < 11.5")
    assert r4.status == "SUPPORTED"
    assert r4.parsed_rule.type == "INDICATOR_COMPARISON"
    assert r4.parsed_rule.indicator == "VIX"
    assert r4.parsed_rule.operator == "LESS_THAN"
    assert r4.parsed_rule.value == 11.5
    assert r3.parsed_rule.period == 14
    assert r3.parsed_rule.operator == "CROSS_BELOW"
    assert r3.parsed_rule.value == 40.0

def test_ema_sma_rules():
    # Price above 20 EMA
    r1 = parse_deterministic_rule("Price above 20 EMA")
    assert r1.status == "SUPPORTED"
    assert r1.parsed_rule.type == "PRICE_COMPARISON"
    assert r1.parsed_rule.price == "PRICE"
    assert r1.parsed_rule.indicator == "EMA"
    assert r1.parsed_rule.period == 20
    assert r1.parsed_rule.operator == "PRICE_ABOVE"

    # Price below 50 SMA
    r2 = parse_deterministic_rule("Price below 50 SMA")
    assert r2.status == "SUPPORTED"
    assert r2.parsed_rule.type == "PRICE_COMPARISON"
    assert r2.parsed_rule.price == "PRICE"
    assert r2.parsed_rule.indicator == "SMA"
    assert r2.parsed_rule.period == 50
    assert r2.parsed_rule.operator == "PRICE_BELOW"

def test_indicator_to_indicator_crossover():
    # 9 EMA crosses above 21 EMA
    r1 = parse_deterministic_rule("9 EMA crosses above 21 EMA")
    assert r1.status == "SUPPORTED"
    assert r1.parsed_rule.type == "INDICATOR_CROSSOVER"
    assert r1.parsed_rule.indicator == "EMA"
    assert r1.parsed_rule.period == 9
    assert r1.parsed_rule.operator == "CROSS_ABOVE"
    assert r1.parsed_rule.price == "EMA"
    assert r1.parsed_rule.value == 21.0

    # 20 SMA crosses below 50 SMA
    r2 = parse_deterministic_rule("20 SMA crosses below 50 SMA")
    assert r2.status == "SUPPORTED"
    assert r2.parsed_rule.type == "INDICATOR_CROSSOVER"
    assert r2.parsed_rule.indicator == "SMA"
    assert r2.parsed_rule.period == 20
    assert r2.parsed_rule.operator == "CROSS_BELOW"
    assert r2.parsed_rule.price == "SMA"
    assert r2.parsed_rule.value == 50.0

def test_logical_and_or_nested():
    # AND expression
    expr = "RSI crosses above 60 AND Price above 200 EMA"
    tree = parse_logical_expression(expr)
    assert tree.type == "AND"
    assert len(tree.conditions) == 2
    assert tree.conditions[0].type == "INDICATOR_CROSSOVER"
    assert tree.conditions[1].type == "PRICE_COMPARISON"

    # Parentheses nested expression
    expr_nested = "(RSI crosses above 60 OR Price above 200 EMA) AND Spot crosses below 100 SMA"
    tree_nested = parse_logical_expression(expr_nested)
    assert tree_nested.type == "AND"
    assert tree_nested.conditions[0].type == "OR"
    assert tree_nested.conditions[1].type == "PRICE_CROSSOVER"

def test_rule_explainer_crossovers():
    # Verify crossover semantics explanation matches specs
    r = parse_deterministic_rule("RSI crosses above 60")
    exp = explain_parsed_rule(r.parsed_rule)
    assert "crosses from 60 or below to above 60" in exp

    r_ind = parse_deterministic_rule("9 EMA crosses above 21 EMA")
    exp_ind = explain_parsed_rule(r_ind.parsed_rule)
    assert "crosses from 21 EMA or below to above 21 EMA" in exp_ind

def test_rule_validation():
    # Invalid timeframe
    parsed = ParsedRule(
        type="INDICATOR_CROSSOVER",
        indicator="RSI",
        period=14,
        operator="CROSS_ABOVE",
        value=60,
        timeframe="99m"
    )
    rule_obj = StrategyRule(rawText="Test", parsedRule=parsed)
    validated = validate_strategy_rule(rule_obj)
    assert validated.validationStatus == "INVALID"
    assert "Unsupported timeframe" in validated.errors[0]

def test_strategy_validation_metadata():
    req = StrategyRequest(
        schemaVersion="2.0.0",
        name="Test Validation",
        timeframe="15m",
        meta={
            "strategyName": "Test Validation",
            "status": "DRAFT"
        },
        instrument={
            "underlying": "NIFTY 50"
        },
        schedule={
            "entryFrom": "invalid_time",
            "entryTo": "14:30",
            "forcedExitTime": "15:15",
            "applicableDays": ["Mon"]
        }
    )
    res = StrategyService.validate_strategy_definition(req)
    assert res.valid is False
    assert res.errors[0].field == "schedule.entryFrom"

def test_golden_rules_parsing():
    from app.strategies.parser.golden_rule_parser import parse_golden_rule, is_golden_rule_text
    
    # 1. Matches golden rule text
    assert is_golden_rule_text("Wait for candle closure above breakout level") is True
    assert is_golden_rule_text("Wait for candle close") is True
    assert is_golden_rule_text("RSI crosses above 60") is False
    
    # 2. Parse golden rule
    res = parse_golden_rule("Wait for candle closure above breakout level", default_timeframe="15m")
    assert res.status == "SUPPORTED"
    assert res.parsed_rule.type == "GOLDEN_RULE"
    assert res.parsed_rule.evaluation == "CANDLE_CLOSE"
    assert res.parsed_rule.confirmation == "CANDLE_CLOSURE_ABOVE_BREAKOUT_LEVEL"
    assert res.parsed_rule.timeframe == "15m"

def test_nested_indicator_operands():
    r = parse_deterministic_rule("9 EMA crosses above 21 EMA", default_timeframe="15m")
    assert r.status == "SUPPORTED"
    assert r.parsed_rule.type == "INDICATOR_CROSSOVER"
    assert r.parsed_rule.left is not None
    assert r.parsed_rule.left.indicator == "EMA"
    assert r.parsed_rule.left.period == 9
    assert r.parsed_rule.right is not None
    assert r.parsed_rule.right.indicator == "EMA"
    assert r.parsed_rule.right.period == 21

