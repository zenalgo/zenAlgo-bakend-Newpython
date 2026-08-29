from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime

class CreditDebitRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    description: Optional[str] = None
    referenceType: Optional[str] = Field(None, alias="referenceType")
    referenceId: Optional[str] = Field(None, alias="referenceId")
    idempotencyKey: Optional[str] = Field(None, alias="idempotencyKey")

    model_config = {
        "populate_by_name": True
    }

class WalletDto(BaseModel):
    id: int
    userId: int = Field(..., alias="userId")
    balance: Decimal
    currency: str
    updatedAt: datetime = Field(..., alias="updatedAt")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class WalletTransactionDto(BaseModel):
    id: int
    amount: Decimal
    balanceBefore: Decimal = Field(..., alias="balanceBefore")
    balanceAfter: Decimal = Field(..., alias="balanceAfter")
    transactionType: str = Field(..., alias="transactionType")
    description: Optional[str] = None
    referenceType: Optional[str] = Field(None, alias="referenceType")
    referenceId: Optional[str] = Field(None, alias="referenceId")
    status: str
    idempotencyKey: Optional[str] = Field(None, alias="idempotencyKey")
    createdAt: datetime = Field(..., alias="createdAt")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }
