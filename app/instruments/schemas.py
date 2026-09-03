from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

class BrokerMappingDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    brokerCode: str
    securityId: str
    exchangeSegment: str
    tradingSymbol: str
    lotSize: int
    tickSize: float

class InstrumentDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    companyName: str
    sector: str
    instrumentType: str
    isFno: bool
    brokerMappings: List[BrokerMappingDTO] = []

class InstrumentSearchResultDTO(BaseModel):
    symbol: str
    companyName: str
    sector: str
    instrumentType: str
    securityId: str
    exchangeSegment: str
    tradingSymbol: str
    lotSize: int
    tickSize: float
    brokerCode: str = "DHAN"
    lastPrice: Optional[float] = None
    changePct: Optional[float] = None

class InstrumentQuoteDTO(BaseModel):
    symbol: str
    companyName: Optional[str] = None
    securityId: Optional[str] = None
    exchangeSegment: str = "NSE_EQ"
    lastPrice: float
    prevClose: float
    change: float
    changePct: float
    dayHigh: Optional[float] = None
    dayLow: Optional[float] = None
    lotSize: int = 1
    currency: str = "INR"
    isLive: bool = True

class SectorSummaryDTO(BaseModel):
    sector: str
    count: int
