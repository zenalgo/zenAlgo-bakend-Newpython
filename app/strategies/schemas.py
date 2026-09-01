from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Union, Any
from decimal import Decimal
import re
from app.strategies.rules.rule_schema import StrategyRule, ParsedRule

class StrategyLegRequest(BaseModel):
    sequence: int
    segment: str # EQUITY, FNO, CURRENCY, COMMODITY
    side: str # BUY, SELL
    strikeSelection: str = Field(..., alias="strikeSelection") # ATM, OTM, ITM, CUSTOM
    strikeValue: Optional[Decimal] = Field(None, alias="strikeValue")
    expiry: str # WEEKLY, MONTHLY, NEXT_WEEKLY
    lots: int = Field(..., ge=1)
    targetType: str = Field("NONE", alias="targetType") # NONE, POINTS, PERCENTAGE
    targetValue: Optional[Decimal] = Field(None, alias="targetValue")
    stopLossType: str = Field("NONE", alias="stopLossType")
    stopLossValue: Optional[Decimal] = Field(None, alias="stopLossValue")
    trailingSlEnabled: bool = Field(False, alias="trailingSlEnabled")
    trailingSlActivateType: Optional[str] = Field(None, alias="trailingSlActivateType")
    trailingSlActivateValue: Optional[Decimal] = Field(None, alias="trailingSlActivateValue")
    trailingSlIncreaseBy: Optional[Decimal] = Field(None, alias="trailingSlIncreaseBy")
    trailingSlBy: Optional[Decimal] = Field(None, alias="trailingSlBy")

    model_config = {
        "populate_by_name": True
    }

class StrategyEntrySettingRequest(BaseModel):
    entryTime: str = Field(..., alias="entryTime") # HH:MM

    model_config = {
        "populate_by_name": True
    }

    @field_validator("entryTime")
    @classmethod
    def validate_time(cls, value: str) -> str:
        if not re.match(r"^\d{2}:\d{2}$", value):
            raise ValueError("Time must be in HH:MM format")
        return value

class StrategyExitSettingRequest(BaseModel):
    profitMtmType: str = Field("NONE", alias="profitMtmType") # NONE, RUPEES, PERCENTAGE
    profitMtmValue: Optional[Decimal] = Field(None, alias="profitMtmValue")
    stopLossMtmType: str = Field("NONE", alias="stopLossMtmType")
    stopLossMtmValue: Optional[Decimal] = Field(None, alias="stopLossMtmValue")
    exitTime: str = Field(..., alias="exitTime") # HH:MM
    exitOnExpiry: bool = Field(True, alias="exitOnExpiry")
    exitAfterEntryType: str = Field("NONE", alias="exitAfterEntryType")
    exitAfterEntryValue: Optional[int] = Field(None, alias="exitAfterEntryValue")

    model_config = {
        "populate_by_name": True
    }

    @field_validator("exitTime")
    @classmethod
    def validate_time(cls, value: str) -> str:
        if not re.match(r"^\d{2}:\d{2}$", value):
            raise ValueError("Time must be in HH:MM format")
        return value

# --- Strategy Builder v2.0.0 Schemas ---

class StrategyMeta(BaseModel):
    strategyId: Optional[str] = Field(None, alias="strategyId")
    strategyName: str = Field(..., alias="strategyName")
    authorName: Optional[str] = Field(None, alias="authorName")
    createdAt: Optional[str] = Field(None, alias="createdAt")
    status: Optional[str] = Field("DRAFT", alias="status")

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

class InstrumentConfig(BaseModel):
    underlying: str
    indicesArray: Optional[List[str]] = Field(None, alias="indicesArray")
    expiryType: Optional[str] = Field("Weekly", alias="expiryType")

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

class ScheduleConfig(BaseModel):
    entryFrom: str = Field(..., alias="entryFrom")
    entryTo: Optional[str] = Field("14:30", alias="entryTo")
    forcedExitTime: str = Field(..., alias="forcedExitTime")
    applicableDays: Optional[List[str]] = Field(None, alias="applicableDays")
    avoidEvents: Optional[str] = Field("", alias="avoidEvents")
    entryDay: Optional[str] = Field(None, alias="entryDay")
    exitDay: Optional[str] = Field(None, alias="exitDay")
    weeklyCycleScope: Optional[str] = Field(None, alias="weeklyCycleScope")
    entryDays: Optional[List[str]] = Field(None, alias="entryDays")
    exitDays: Optional[List[str]] = Field(None, alias="exitDays")
    applicableMonths: Optional[List[str]] = Field(None, alias="applicableMonths")
    selectedMonthlyDate: Optional[str] = Field(None, alias="selectedMonthlyDate")

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

class RiskParameter(BaseModel):
    type: str
    value: float

    model_config = {
        "populate_by_name": True
    }

class RiskManagementConfig(BaseModel):
    riskRewardRatio: Optional[str] = Field(None, alias="riskRewardRatio")
    stopLoss: Optional[Union[str, RiskParameter, dict]] = Field(None, alias="stopLoss")
    maxLossPerTrade: Optional[Union[str, float]] = Field(None, alias="maxLossPerTrade")
    maxLossPerDay: Optional[Union[str, float]] = Field(None, alias="maxLossPerDay")
    maxLossPerWeek: Optional[Union[str, float]] = Field(None, alias="maxLossPerWeek")
    capitalAllocationPerTrade: Optional[Union[str, float]] = Field(None, alias="capitalAllocationPerTrade")
    maxTradesPerDay: Optional[int] = Field(None, alias="maxTradesPerDay")
    maxOpenPositions: Optional[int] = Field(None, alias="maxOpenPositions")
    cooldownPeriodMinutes: Optional[int] = Field(None, alias="cooldownPeriodMinutes")
    positionSizing: Optional[str] = Field(None, alias="positionSizing")
    consecutiveLossLimit: Optional[int] = Field(None, alias="consecutiveLossLimit")
    actionOnConsecutiveLoss: Optional[str] = Field(None, alias="actionOnConsecutiveLoss")
    partialExit: Optional[dict] = Field(None, alias="partialExit")
    trailingStop: Optional[dict] = Field(None, alias="trailingStop")

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

class TargetParameter(BaseModel):
    value: float
    type: str
    exitPercentage: float = Field(..., alias="exitPercentage")

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

class TargetConfig(BaseModel):
    value: Optional[str] = None
    scaleOutPlan: Optional[str] = Field(None, alias="scaleOutPlan")
    targets: Optional[List[TargetParameter]] = None

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

class StrategyRequest(BaseModel):
    schemaVersion: Optional[str] = Field("2.0.0", alias="schemaVersion")
    executionEngine: Optional[str] = Field("ZENALGO_QUANT_ENGINE", alias="executionEngine")
    
    # Relational defaults/compat fields
    name: Optional[str] = None
    underlying: Optional[str] = None
    capital: Optional[Decimal] = None
    tradingType: Optional[str] = "INTRADAY"
    mode: Optional[str] = "PAPER"
    legs: Optional[List[StrategyLegRequest]] = None
    entrySetting: Optional[StrategyEntrySettingRequest] = None
    entryDays: Optional[List[str]] = None
    exitSetting: Optional[StrategyExitSettingRequest] = None
    
    # Builder fields
    meta: Optional[StrategyMeta] = None
    description: Optional[str] = None
    youtubeUrl: Optional[str] = Field(None, alias="youtubeUrl")
    coreIdea: Optional[str] = Field(None, alias="coreIdea")
    category: Optional[str] = None
    marketBias: Optional[str] = Field(None, alias="marketBias")
    timeframe: Optional[str] = None
    instrument: Optional[InstrumentConfig] = None
    schedule: Optional[ScheduleConfig] = None
    
    entryConditions: Optional[List[Union[str, StrategyRule, dict]]] = Field(None, alias="entryConditions")
    exitConditions: Optional[List[Union[str, StrategyRule, dict]]] = Field(None, alias="exitConditions")
    goldenRules: Optional[List[Union[str, StrategyRule, dict]]] = Field(None, alias="goldenRules")
    keyRememberPoints: Optional[List[Union[str, StrategyRule, dict]]] = Field(None, alias="keyRememberPoints")
    
    riskManagement: Optional[RiskManagementConfig] = Field(None, alias="riskManagement")
    target: Optional[TargetConfig] = None
    options: Optional[dict] = None
    execution: Optional[dict] = None
    pivotConfiguration: Optional[dict] = Field(None, alias="pivotConfiguration")
    eventExclusion: Optional[dict] = Field(None, alias="eventExclusion")
    tradingHorizon: Optional[str] = Field("Intraday", alias="tradingHorizon")
    scriptExecutionPayload: Optional[dict] = Field(None, alias="scriptExecutionPayload")

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

# --- Response Schemas ---

class StrategyLegResponse(BaseModel):
    id: int
    sequence: int
    segment: str
    side: str
    strikeSelection: str = Field(..., alias="strikeSelection")
    strikeValue: Optional[Decimal] = Field(None, alias="strikeValue")
    expiry: str
    lots: int
    targetType: str = Field(..., alias="targetType")
    targetValue: Optional[Decimal] = Field(None, alias="targetValue")
    stopLossType: str = Field(..., alias="stopLossType")
    stopLossValue: Optional[Decimal] = Field(None, alias="stopLossValue")
    trailingSlEnabled: bool = Field(..., alias="trailingSlEnabled")
    trailingSlActivateType: Optional[str] = Field(None, alias="trailingSlActivateType")
    trailingSlActivateValue: Optional[Decimal] = Field(None, alias="trailingSlActivateValue")
    trailingSlIncreaseBy: Optional[Decimal] = Field(None, alias="trailingSlIncreaseBy")
    trailingSlBy: Optional[Decimal] = Field(None, alias="trailingSlBy")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class StrategyEntrySettingResponse(BaseModel):
    entryTime: str = Field(..., alias="entryTime")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class StrategyExitSettingResponse(BaseModel):
    profitMtmType: str = Field(..., alias="profitMtmType")
    profitMtmValue: Optional[Decimal] = Field(None, alias="profitMtmValue")
    stopLossMtmType: str = Field(..., alias="stopLossMtmType")
    stopLossMtmValue: Optional[Decimal] = Field(None, alias="stopLossMtmValue")
    exitTime: str = Field(..., alias="exitTime")
    exitOnExpiry: bool = Field(..., alias="exitOnExpiry")
    exitAfterEntryType: str = Field(..., alias="exitAfterEntryType")
    exitAfterEntryValue: Optional[int] = Field(None, alias="exitAfterEntryValue")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class StrategyResponse(BaseModel):
    schemaVersion: str = Field("2.0.0", alias="schemaVersion")
    executionEngine: str = Field("ZENALGO_QUANT_ENGINE", alias="executionEngine")
    
    id: int
    userId: int = Field(..., alias="userId")
    name: str
    description: Optional[str] = None
    status: str
    mode: str
    currentVersionId: Optional[int] = Field(None, alias="currentVersionId")
    versionNumber: int = Field(..., alias="versionNumber")
    underlying: str
    capital: Decimal
    tradingType: str = Field(..., alias="tradingType")
    legs: List[StrategyLegResponse]
    entrySetting: StrategyEntrySettingResponse = Field(..., alias="entrySetting")
    entryDays: List[str] = Field(..., alias="entryDays")
    exitSetting: StrategyExitSettingResponse = Field(..., alias="exitSetting")

    # Strategy Builder fields
    meta: Optional[StrategyMeta] = None
    youtubeUrl: Optional[str] = Field(None, alias="youtubeUrl")
    coreIdea: Optional[str] = Field(None, alias="coreIdea")
    category: Optional[str] = None
    marketBias: Optional[str] = Field(None, alias="marketBias")
    timeframe: Optional[str] = None
    instrument: Optional[InstrumentConfig] = None
    schedule: Optional[ScheduleConfig] = None
    
    entryConditions: Optional[List[StrategyRule]] = Field(None, alias="entryConditions")
    exitConditions: Optional[List[StrategyRule]] = Field(None, alias="exitConditions")
    goldenRules: Optional[List[StrategyRule]] = Field(None, alias="goldenRules")
    keyRememberPoints: Optional[List[StrategyRule]] = Field(None, alias="keyRememberPoints")
    
    riskManagement: Optional[RiskManagementConfig] = Field(None, alias="riskManagement")
    target: Optional[TargetConfig] = None
    options: Optional[dict] = None
    execution: Optional[dict] = None
    pivotConfiguration: Optional[dict] = Field(None, alias="pivotConfiguration")
    eventExclusion: Optional[dict] = Field(None, alias="eventExclusion")
    tradingHorizon: Optional[str] = Field("Intraday", alias="tradingHorizon")
    scriptExecutionPayload: Optional[dict] = Field(None, alias="scriptExecutionPayload")

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

class StrategyValidationError(BaseModel):
    field: str
    code: str
    message: str

class StrategyValidationResponse(BaseModel):
    valid: bool
    errors: List[StrategyValidationError]
