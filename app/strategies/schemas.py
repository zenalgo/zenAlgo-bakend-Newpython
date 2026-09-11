from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Union, Any, Dict
from decimal import Decimal
import re
from app.strategies.rules.rule_schema import StrategyRule, ParsedRule

class StrategyLegRequest(BaseModel):
    sequence: int = 1
    segment: str = "OPT" # EQUITY, FNO, OPT, CURRENCY, COMMODITY
    side: str = "BUY" # BUY, SELL
    strikeSelection: str = Field("ATM", alias="strikeSelection") # ATM, OTM, ITM, CUSTOM
    strikeValue: Optional[Decimal] = Field(None, alias="strikeValue")
    expiry: str = "WEEKLY" # WEEKLY, MONTHLY, NEXT_WEEKLY
    lots: int = Field(1, ge=1)
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
        "populate_by_name": True,
        "extra": "allow"
    }

    @model_validator(mode="before")
    @classmethod
    def normalize_leg(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "sequence" not in data or data["sequence"] is None:
            data["sequence"] = 1
        if "segment" not in data or not data["segment"]:
            data["segment"] = data.get("instrumentType") or "OPT"
        if "expiry" not in data or not data["expiry"]:
            data["expiry"] = "WEEKLY"
        if "lots" not in data or not data["lots"]:
            qty = data.get("quantity") or 50
            data["lots"] = max(1, int(qty) // 50) if int(qty) >= 50 else 1
        if "strikeSelection" not in data and "strike" in data:
            data["strikeSelection"] = data["strike"]
        if "side" not in data and "action" in data:
            data["side"] = data["action"]
        return data

class StrategyEntrySettingRequest(BaseModel):
    entryTime: str = Field("09:15", alias="entryTime") # HH:MM

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

    @model_validator(mode="before")
    @classmethod
    def normalize_entry_time(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "entryTime" not in data or not data["entryTime"]:
                data["entryTime"] = "09:15"
            else:
                # Trim seconds if provided as HH:MM:SS
                parts = str(data["entryTime"]).strip().split(":")
                if len(parts) >= 2:
                    data["entryTime"] = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        return data

class StrategyExitSettingRequest(BaseModel):
    profitMtmType: str = Field("NONE", alias="profitMtmType") # NONE, RUPEES, PERCENTAGE
    profitMtmValue: Optional[Decimal] = Field(None, alias="profitMtmValue")
    stopLossMtmType: str = Field("NONE", alias="stopLossMtmType")
    stopLossMtmValue: Optional[Decimal] = Field(None, alias="stopLossMtmValue")
    exitTime: str = Field("15:15", alias="exitTime") # HH:MM
    exitOnExpiry: bool = Field(False, alias="exitOnExpiry")
    exitAfterEntryType: str = Field("NONE", alias="exitAfterEntryType")
    exitAfterEntryValue: Optional[int] = Field(None, alias="exitAfterEntryValue")

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

    @model_validator(mode="before")
    @classmethod
    def normalize_exit_time(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "exitTime" not in data or not data["exitTime"]:
                data["exitTime"] = "15:15"
            else:
                # Trim seconds if provided as HH:MM:SS
                parts = str(data["exitTime"]).strip().split(":")
                if len(parts) >= 2:
                    data["exitTime"] = f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        return data

# --- Strategy Builder v2.0.0 Schemas ---

class StrategyMeta(BaseModel):
    strategyId: Optional[str] = Field(None, alias="strategyId")
    strategyName: Optional[str] = Field(None, alias="strategyName")
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
    type: Optional[str] = Field("Options", alias="type")

    model_config = {
        "populate_by_name": True,
        "extra": "allow"
    }

class ScheduleConfig(BaseModel):
    entryFrom: Optional[str] = Field("09:15", alias="entryFrom")
    entryTo: Optional[str] = Field("14:30", alias="entryTo")
    forcedExitTime: Optional[str] = Field("15:15", alias="forcedExitTime")
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
    maxTradesPerDay: Optional[Union[int, str]] = Field(None, alias="maxTradesPerDay")
    maxOpenPositions: Optional[Union[int, str]] = Field(None, alias="maxOpenPositions")
    cooldownPeriodMinutes: Optional[Union[int, str]] = Field(None, alias="cooldownPeriodMinutes")
    cooldownMinutes: Optional[Union[int, str]] = Field(None, alias="cooldownMinutes")
    positionSizing: Optional[str] = Field(None, alias="positionSizing")
    positionSizingMode: Optional[str] = Field(None, alias="positionSizingMode")
    consecutiveLossLimit: Optional[Union[int, str]] = Field(None, alias="consecutiveLossLimit")
    actionOnConsecutiveLoss: Optional[str] = Field(None, alias="actionOnConsecutiveLoss")
    afterLossAction: Optional[str] = Field(None, alias="afterLossAction")
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
    value: Optional[Union[str, float, int]] = None
    type: Optional[str] = None
    scaleOutPlan: Optional[str] = Field(None, alias="scaleOutPlan")
    targets: Optional[List[TargetParameter]] = None

    @model_validator(mode="before")
    @classmethod
    def parse_from_string_or_dict(cls, data: Any) -> Any:
        if isinstance(data, (str, int, float)):
            return {"value": str(data)}
        return data

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
    status: Optional[str] = None
    legs: Optional[List[StrategyLegRequest]] = None
    entrySetting: Optional[StrategyEntrySettingRequest] = None
    entryDays: Optional[List[str]] = None
    exitSetting: Optional[StrategyExitSettingRequest] = None
    
    # Builder fields
    meta: Optional[Union[StrategyMeta, dict]] = None
    description: Optional[str] = None
    youtubeUrl: Optional[str] = Field(None, alias="youtubeUrl")
    coreIdea: Optional[str] = Field(None, alias="coreIdea")
    category: Optional[str] = None
    marketBias: Optional[str] = Field(None, alias="marketBias")
    timeframe: Optional[str] = None
    instrument: Optional[Union[InstrumentConfig, dict]] = None
    schedule: Optional[Union[ScheduleConfig, dict]] = None
    
    entryConditions: Optional[List[Union[str, StrategyRule, dict]]] = Field(None, alias="entryConditions")
    exitConditions: Optional[List[Union[str, StrategyRule, dict]]] = Field(None, alias="exitConditions")
    goldenRules: Optional[List[Union[str, StrategyRule, dict]]] = Field(None, alias="goldenRules")
    keyRememberPoints: Optional[List[Union[str, StrategyRule, dict]]] = Field(None, alias="keyRememberPoints")
    
    riskManagement: Optional[Union[RiskManagementConfig, dict]] = Field(None, alias="riskManagement")
    target: Optional[Union[TargetConfig, dict, str]] = None
    options: Optional[dict] = None
    execution: Optional[dict] = None
    pivotConfiguration: Optional[dict] = Field(None, alias="pivotConfiguration")
    eventExclusion: Optional[dict] = Field(None, alias="eventExclusion")
    tradingHorizon: Optional[str] = Field("Intraday", alias="tradingHorizon")
    scriptExecutionPayload: Optional[dict] = Field(None, alias="scriptExecutionPayload")

    @model_validator(mode="before")
    @classmethod
    def normalize_incoming_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        
        # 1. Merge nested "config" dict if present
        config_data = data.get("config")
        if isinstance(config_data, dict):
            for k, v in config_data.items():
                if k not in data or data[k] is None:
                    data[k] = v
                elif k == "target" and isinstance(data[k], (str, int, float)) and isinstance(v, dict):
                    data[k] = v
                elif k == "timing" and ("schedule" not in data or data["schedule"] is None):
                    data["schedule"] = v

        # 2. Timing -> Schedule mapping
        if "timing" in data and ("schedule" not in data or data["schedule"] is None):
            data["schedule"] = data["timing"]

        # 3. Handle author -> meta mapping
        if "author" in data and ("meta" not in data or not data["meta"]):
            data["meta"] = {
                "strategyId": data.get("id") or "STRAT",
                "strategyName": data.get("name") or "Custom Strategy",
                "authorName": data.get("author")
            }
        elif "meta" in data and isinstance(data["meta"], dict):
            if "strategyName" not in data["meta"] and "name" in data:
                data["meta"]["strategyName"] = data["name"]

        # 4. Handle entryTimeframe -> timeframe
        if "entryTimeframe" in data and ("timeframe" not in data or not data["timeframe"]):
            data["timeframe"] = data["entryTimeframe"]

        # 5. Handle instrumentType -> instrument
        if "instrumentType" in data and ("instrument" not in data or not data["instrument"]):
            data["instrument"] = {
                "type": data["instrumentType"],
                "underlying": data.get("underlying", "NIFTY"),
                "indicesArray": data.get("indicesArray", []),
                "expiryType": data.get("expiryType", "Weekly")
            }

        # 6. Target normalization: if string or number, wrap in dict
        if "target" in data and isinstance(data["target"], (str, int, float)):
            data["target"] = {"value": str(data["target"])}

        # 7. Schedule normalization
        if "schedule" in data and isinstance(data["schedule"], dict):
            sched = data["schedule"]
            if not sched.get("entryFrom"):
                sched["entryFrom"] = "09:15"
            if not sched.get("forcedExitTime"):
                sched["forcedExitTime"] = "15:15"

        # 8. Defaults for entryDays, entrySetting, and exitSetting
        if "entryDays" not in data or not data["entryDays"]:
            data["entryDays"] = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"]
        if "entrySetting" not in data or not data["entrySetting"]:
            data["entrySetting"] = {"entryTime": "09:15", "entryType": "INTRADAY", "reEntryLimit": 3}
        if "exitSetting" not in data or not data["exitSetting"]:
            data["exitSetting"] = {"exitTime": "15:15", "exitType": "TIME_BASED"}

        # 9. Mode & Status normalization
        raw_mode = data.get("mode")
        raw_status = data.get("status")
        if raw_mode:
            data["mode"] = str(raw_mode).upper().strip()
        if raw_status:
            data["status"] = str(raw_status).upper().strip()
        elif raw_mode and str(raw_mode).upper().strip() == "LIVE":
            data["status"] = "ACTIVE_LIVE"
        elif "meta" in data and isinstance(data["meta"], dict) and data["meta"].get("status"):
            data["status"] = str(data["meta"]["status"]).upper().strip()

        return data

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
    latestExecution: Optional[dict] = Field(None, alias="latestExecution")

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

class AIGenerateStrategyRequest(BaseModel):
    provider: str = Field("OPENAI", description="AI Provider: OPENAI, GEMINI, or CLAUDE")
    apiKey: str = Field(..., description="API Key for the selected model provider")
    model: Optional[str] = Field(None, description="Specific model override, e.g. gpt-4o, gemini-1.5-flash, claude-3-5-sonnet")
    prompt: str = Field(..., description="Plain-English trading strategy idea or indicator description")

    model_config = {
        "populate_by_name": True
    }

class AIGenerateStrategyResponse(BaseModel):
    strategy: dict
    indicatorAudit: dict
    providerUsed: str
    modelUsed: str
