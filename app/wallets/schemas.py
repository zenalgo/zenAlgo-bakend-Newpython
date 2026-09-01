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
    user_id: int = Field(..., alias="userId")
    balance: Decimal
    currency: str
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class WalletTransactionDto(BaseModel):
    id: int
    amount: Decimal
    balance_before: Decimal = Field(..., alias="balanceBefore")
    balance_after: Decimal = Field(..., alias="balanceAfter")
    transaction_type: str = Field(..., alias="transactionType")
    description: Optional[str] = None
    reference_type: Optional[str] = Field(None, alias="referenceType")
    reference_id: Optional[str] = Field(None, alias="referenceId")
    status: str
    idempotency_key: Optional[str] = Field(None, alias="idempotencyKey")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }
