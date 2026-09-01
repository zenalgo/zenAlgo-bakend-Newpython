from pydantic import BaseModel, Field
from typing import Optional, List
from app.strategies.rules.rule_schema import ParsedRule

class ParserResult(BaseModel):
    status: str # SUPPORTED, UNSUPPORTED, INVALID
    parser: str = "DETERMINISTIC"
    raw_text: str = Field(..., alias="rawText")
    parsed_rule: Optional[ParsedRule] = Field(None, alias="parsedRule")
    confidence: float = 1.0
    errors: Optional[List[str]] = None
    message: Optional[str] = None
    choices: Optional[List[str]] = None

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }
