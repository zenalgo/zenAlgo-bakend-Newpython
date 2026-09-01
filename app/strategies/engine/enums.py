import enum

class EvaluationStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    NOT_MATCHED = "NOT_MATCHED"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"
