import enum

class SignalType(str, enum.Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"

class SignalDirection(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"

class SignalStatus(str, enum.Enum):
    CREATED = "CREATED"
    PENDING_RISK = "PENDING_RISK"
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"
    EXECUTION_PENDING = "EXECUTION_PENDING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
