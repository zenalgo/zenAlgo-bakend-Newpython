from pydantic import BaseModel, Field
from typing import Optional, List, Union

class IndicatorOperand(BaseModel):
    indicator: str
    period: Optional[int] = None
    timeframe: Optional[str] = None

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class ParsedRule(BaseModel):
    type: str # PRICE_COMPARISON, PRICE_CROSSOVER, INDICATOR_COMPARISON, INDICATOR_CROSSOVER, AND, OR, NOT, GOLDEN_RULE
    logic: Optional[str] = None # "AND", "OR", "NOT"
    conditions: Optional[List['ParsedRule']] = None
    indicator: Optional[str] = None
    period: Optional[int] = None
    operator: Optional[str] = None # PRICE_ABOVE, PRICE_BELOW, CROSS_ABOVE, CROSS_BELOW, GREATER_THAN, LESS_THAN
    value: Optional[float] = None
    timeframe: Optional[str] = "15m"
    price: Optional[str] = None
    evaluation: Optional[str] = "CANDLE_CLOSE" # CANDLE_CLOSE or TICK
    confirmation: Optional[str] = None
    mandatory: Optional[bool] = None
    
    # Nested operands for crossovers (e.g. 9 EMA crosses 21 EMA)
    left: Optional[IndicatorOperand] = None
    right: Optional[IndicatorOperand] = None

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class StrategyRule(BaseModel):
    rawText: str = Field(..., alias="rawText")
    parser: str = Field("DETERMINISTIC", alias="parser")
    parsedRule: Optional[ParsedRule] = Field(None, alias="parsedRule")
    confidence: float = Field(1.0, alias="confidence")
    validationStatus: str = Field("VALID", alias="validationStatus") # VALID, INVALID, AMBIGUOUS, UNSUPPORTED
    errors: Optional[List[str]] = None

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }
