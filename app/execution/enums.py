import enum

class ExecutionStatus(str, enum.Enum):
    """Lifecycle states of an execution package and its broker submissions."""
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"

class ExecutionMode(str, enum.Enum):
    """Supported trading modes for order execution."""
    MOCK = "MOCK"
    PAPER = "PAPER"
    LIVE = "LIVE"

class OrderType(str, enum.Enum):
    """Supported broker order types."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SLM = "SLM"

class LegRole(str, enum.Enum):
    """Role of an individual leg within a multi-leg execution package."""
    PRIMARY = "PRIMARY"
    HEDGE = "HEDGE"
    PROTECTION = "PROTECTION"
    ENTRY = "ENTRY"
    EXIT = "EXIT"

class OptionStrikePolicy(str, enum.Enum):
    """Policy for selecting contract strike price."""
    ATM = "ATM"
    OTM = "OTM"
    ITM = "ITM"
    CUSTOM = "CUSTOM"

class OptionExpiryPolicy(str, enum.Enum):
    """Policy for selecting contract expiration date."""
    CURRENT_WEEKLY = "CURRENT_WEEKLY"
    NEXT_WEEKLY = "NEXT_WEEKLY"
    CURRENT_MONTHLY = "CURRENT_MONTHLY"
    NEXT_MONTHLY = "NEXT_MONTHLY"
