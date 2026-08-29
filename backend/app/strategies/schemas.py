from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from decimal import Decimal
import re

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

class StrategyRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=150)
    description: Optional[str] = None
    underlying: str
    capital: Decimal = Field(..., gt=0)
    tradingType: str = Field("INTRADAY", alias="tradingType")
    mode: str = Field("PAPER", alias="mode") # PAPER, LIVE
    legs: List[StrategyLegRequest]
    entrySetting: StrategyEntrySettingRequest = Field(..., alias="entrySetting")
    entryDays: List[str] = Field(..., alias="entryDays") # MONDAY, etc.
    exitSetting: StrategyExitSettingRequest = Field(..., alias="exitSetting")

    model_config = {
        "populate_by_name": True
    }

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
    id: int
    userId: int = Field(..., alias="userId")
    name: str
    description: Optional[str] = None
    status: str
    mode: str
    versionNumber: int = Field(..., alias="versionNumber")
    underlying: str
    capital: Decimal
    tradingType: str = Field(..., alias="tradingType")
    legs: List[StrategyLegResponse]
    entrySetting: StrategyEntrySettingResponse = Field(..., alias="entrySetting")
    entryDays: List[str] = Field(..., alias="entryDays")
    exitSetting: StrategyExitSettingResponse = Field(..., alias="exitSetting")

    model_config = {
        "populate_by_name": True
    }

class StrategyValidationError(BaseModel):
    field: str
    code: str
    message: str

class StrategyValidationResponse(BaseModel):
    valid: bool
    errors: List[StrategyValidationError]

