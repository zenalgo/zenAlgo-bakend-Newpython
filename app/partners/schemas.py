from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime

class PartnerDashboardStatsResponse(BaseModel):
    totalReferrals: int = 0
    activeSubscribers: int = 0
    totalCommissionEarned: Decimal = Decimal("0.00")
    availablePayoutBalance: Decimal = Decimal("0.00")
    pendingCommission: Decimal = Decimal("0.00")
    conversionRate: float = 0.0
    monthlyReferredVolume: Decimal = Decimal("0.00")
    referralCode: str
    referralLink: str

class ReferredClientResponse(BaseModel):
    userId: int
    name: str
    email: str
    registeredAt: datetime
    planName: str
    status: str
    activeStrategyCount: int
    totalCommissionContributed: Decimal

class CommissionTransactionResponse(BaseModel):
    id: int
    clientName: str
    clientEmail: str
    eventType: str # "PLAN_SUBSCRIPTION", "PROFIT_SHARE", "RENEWAL"
    amount: Decimal
    commissionRate: float # e.g. 25.0%
    status: str # "CREDITED", "PROCESSING"
    timestamp: datetime
    description: str

class PayoutRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    bankAccountNumber: str
    ifscCode: str
    accountHolderName: str
    upiId: Optional[str] = None

class PayoutResponse(BaseModel):
    payoutId: str
    amount: Decimal
    status: str # "PROCESSING", "COMPLETED"
    requestedAt: datetime
    bankAccount: str
    utrNumber: Optional[str] = None

class PartnerMarketingLinksResponse(BaseModel):
    referralCode: str
    referralLink: str
    dhanPartnerOnboardingUrl: str
    commissionTier: str
    commissionRatePercent: float
