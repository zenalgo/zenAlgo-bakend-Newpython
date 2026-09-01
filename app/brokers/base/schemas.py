from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal

class OrderRequest(BaseModel):
    trading_symbol: str
    security_id: Optional[str] = None
    transaction_type: str  # BUY, SELL
    order_type: str = "MARKET"  # MARKET, LIMIT, SL, SL-M
    product_type: str = "MIS"  # MIS, CNC, NRML
    quantity: int
    price: Decimal = Decimal("0.0")
    trigger_price: Decimal = Decimal("0.0")
    validity: str = "DAY"

class OrderResult(BaseModel):
    broker_order_id: str
    order_status: str  # SUCCESS, REJECTED, PENDING
    message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None

class OrderStatus(BaseModel):
    broker_order_id: str
    status: str
    filled_quantity: int = 0
    avg_price: Decimal = Decimal("0.0")
    rejection_reason: Optional[str] = None

class Position(BaseModel):
    trading_symbol: str
    security_id: Optional[str] = None
    position_type: str = "INTRADAY"
    exchange_segment: Optional[str] = None
    product_type: Optional[str] = None
    net_qty: int = 0
    buy_qty: int = 0
    sell_qty: int = 0
    buy_avg: Decimal = Decimal("0.0")
    sell_avg: Decimal = Decimal("0.0")
    realized_profit: Decimal = Decimal("0.0")
    unrealized_profit: Decimal = Decimal("0.0")

class Holding(BaseModel):
    trading_symbol: str
    security_id: Optional[str] = None
    isin: str
    exchange: str = "NSE"
    total_qty: int = 0
    dp_qty: int = 0
    t1_qty: int = 0
    available_qty: int = 0
    collateral_qty: int = 0
    avg_cost_price: Decimal = Decimal("0.0")
    last_traded_price: Decimal = Decimal("0.0")

class Funds(BaseModel):
    available_balance: Decimal = Decimal("0.0")
    sod_limit: Decimal = Decimal("0.0")
    collateral_amount: Decimal = Decimal("0.0")
    receiveable_amount: Decimal = Decimal("0.0")
    utilized_amount: Decimal = Decimal("0.0")
    blocked_payout_amount: Decimal = Decimal("0.0")
    withdrawable_balance: Decimal = Decimal("0.0")

class BrokerProfile(BaseModel):
    client_id: str
    name: str
    ucc: Optional[str] = ""
    email: Optional[str] = ""
    mobile_no: Optional[str] = ""

class ValidationResult(BaseModel):
    is_valid: bool
    status: str  # ACTIVE, EXPIRED, INVALID
    message: Optional[str] = None
    expiry_time: Optional[datetime] = None

class FormField(BaseModel):
    name: str
    label: str
    type: str = "text"  # text, password, select, number
    required: bool = True
    placeholder: Optional[str] = None
    options: Optional[List[Dict[str, str]]] = None  # for select type

class BrokerFormConfig(BaseModel):
    broker_code: str = Field(..., alias="brokerCode")
    name: str
    auth_type: str = Field(..., alias="authType")  # TOKEN, OAUTH, API_KEY
    connection_type: str = Field("TOKEN", alias="connectionType")
    fields: List[FormField]

    model_config = {
        "populate_by_name": True
    }

class BrokerMetadata(BaseModel):
    code: str
    name: str
    logo: Optional[str] = None
    enabled: bool = True
    auth_type: str = Field(..., alias="authType")
    connection_type: str = Field("TOKEN", alias="connectionType")

    model_config = {
        "populate_by_name": True
    }
