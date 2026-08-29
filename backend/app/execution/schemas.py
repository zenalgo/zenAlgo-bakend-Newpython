from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date

class StrategyExecutionTraceEventResponse(BaseModel):
    step: str
    status: str
    message: Optional[str] = None
    errorCode: Optional[str] = Field(None, alias="errorCode")
    timestamp: datetime

    model_config = {
        "populate_by_name": True
    }

class StrategyUserExecutionTraceResponse(BaseModel):
    userId: int = Field(..., alias="userId")
    status: str
    currentStep: str = Field(..., alias="currentStep")
    failureCode: Optional[str] = Field(None, alias="failureCode")
    failureReason: Optional[str] = Field(None, alias="failureReason")
    executionId: Optional[int] = Field(None, alias="executionId")
    timeline: Optional[List[StrategyExecutionTraceEventResponse]] = None

    model_config = {
        "populate_by_name": True
    }

class StrategyExecutionBatchResponse(BaseModel):
    batchId: int = Field(..., alias="batchId")
    signalId: int = Field(..., alias="signalId")
    strategyId: int = Field(..., alias="strategyId")
    strategyVersionId: int = Field(..., alias="strategyVersionId")
    tradingDate: date = Field(..., alias="tradingDate")
    totalUsers: int = Field(..., alias="totalUsers")
    eligibleUsers: int = Field(..., alias="eligibleUsers")
    rejectedUsers: int = Field(..., alias="rejectedUsers")
    executionStartedUsers: int = Field(..., alias="executionStartedUsers")
    successfulUsers: int = Field(..., alias="successfulUsers")
    failedUsers: int = Field(..., alias="failedUsers")
    notExecutedUsers: int = Field(..., alias="notExecutedUsers")
    status: str
    createdAt: datetime = Field(..., alias="createdAt")
    completedAt: Optional[datetime] = Field(None, alias="completedAt")

    model_config = {
        "populate_by_name": True
    }

class FailureReasonCount(BaseModel):
    code: str
    count: int

class ExecutionFailureSummaryResponse(BaseModel):
    totalFailures: int = Field(..., alias="totalFailures")
    reasons: List[FailureReasonCount]

    model_config = {
        "populate_by_name": True
    }

class UserExecutionResult(BaseModel):
    eligible: bool
    executed: bool
    status: str
    failureCode: Optional[str] = Field(None, alias="failureCode")
    failureReason: Optional[str] = Field(None, alias="failureReason")
    executionId: Optional[int] = Field(None, alias="executionId")

    model_config = {
        "populate_by_name": True
    }
