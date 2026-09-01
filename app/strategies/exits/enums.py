from enum import Enum

class ExitType(str, Enum):
    """Specific exit condition types supported by the Exit Engine."""
    STOP_LOSS = "STOP_LOSS"
    TARGET = "TARGET"
    R_MULTIPLE_TARGET = "R_MULTIPLE_TARGET"
    TRAILING_STOP = "TRAILING_STOP"
    INDICATOR_REVERSAL = "INDICATOR_REVERSAL"
    FORCED_TIME_EXIT = "FORCED_TIME_EXIT"
    EXPIRY_EXIT = "EXPIRY_EXIT"
    PARTIAL_EXIT = "PARTIAL_EXIT"
    STRATEGY_INVALIDATION = "STRATEGY_INVALIDATION"
    EMERGENCY_EXIT = "EMERGENCY_EXIT"


class ExitDecision(str, Enum):
    """Outcome decision of an exit evaluation check."""
    TRIGGERED = "TRIGGERED"
    NOT_TRIGGERED = "NOT_TRIGGERED"
    SKIPPED = "SKIPPED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"


class PositionDirection(str, Enum):
    """Market direction of the open position."""
    BUY = "BUY"
    SELL = "SELL"
