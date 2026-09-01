import enum

class GoldenRuleStatus(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"

class GateDecision(str, enum.Enum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
