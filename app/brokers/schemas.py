from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, date

from app.brokers.base.schemas import (
    BrokerFormConfig,
    FormField,
    BrokerMetadata,
    BrokerProfile
)

class ConnectBrokerRequest(BaseModel):
    credentials: Dict[str, Any]

class BrokerAccountResponse(BaseModel):
    id: int
    userId: int = Field(..., alias="userId")
    brokerCode: str = Field(..., alias="brokerCode")
    brokerName: Optional[str] = Field(None, alias="brokerName")
    accountClientId: str = Field(..., alias="accountClientId")
    status: str
    connectionDate: date = Field(..., alias="connectionDate")
    expiryTime: Optional[datetime] = Field(None, alias="expiryTime")

    model_config = {
        "populate_by_name": True
    }


# --- Backward Compatibility Schemas for Dhan HQ ---

class GenerateTokenRequest(BaseModel):
    clientId: str = Field(..., alias="clientId")
    accessToken: str = Field(..., alias="accessToken")
    expiryTime: Optional[datetime] = Field(None, alias="expiryTime")

    model_config = {
        "populate_by_name": True
    }

class TotpLoginRequest(BaseModel):
    dhanClientId: str = Field(..., alias="dhanClientId")
    pin: str
    totp: str

    model_config = {
        "populate_by_name": True
    }

class SetIpRequest(BaseModel):
    primaryIp: str = Field(..., alias="primaryIp")
    secondaryIp: Optional[str] = Field(None, alias="secondaryIp")

    model_config = {
        "populate_by_name": True
    }

class DhanProfileResponse(BaseModel):
    clientId: str = Field(..., alias="clientId")
    name: str
    ucc: str
    email: str
    mobileNo: str = Field(..., alias="mobileNo")

    model_config = {
        "populate_by_name": True
    }

class BrokerSessionResponse(BaseModel):
    userId: int = Field(..., alias="userId")
    clientId: str = Field(..., alias="clientId")
    brokerName: str = Field(..., alias="brokerName")
    status: str
    connectionDate: date = Field(..., alias="connectionDate")
    expiryTime: Optional[datetime] = Field(None, alias="expiryTime")

    model_config = {
        "populate_by_name": True
    }
