from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, date

class PlanRequest(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    monthlyPrice: Decimal = Field(..., alias="monthlyPrice")
    currency: str = "INR"
    gstPercentage: Decimal = Field(Decimal("18.00"), alias="gstPercentage")
    minWalletBalance: Decimal = Field(Decimal("0.00"), alias="minWalletBalance")
    maxActiveStrategies: Optional[int] = Field(None, alias="maxActiveStrategies")
    maxStrategyExecutionsPerDay: Optional[int] = Field(None, alias="maxStrategyExecutionsPerDay")
    maxPortfolioCapital: Optional[Decimal] = Field(None, alias="maxPortfolioCapital")
    subscriptionType: str = Field("MONTHLY", alias="subscriptionType")

    model_config = {
        "populate_by_name": True
    }

class PlanResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    monthly_price: Decimal = Field(..., alias="monthlyPrice")
    currency: str
    gst_percentage: Decimal = Field(..., alias="gstPercentage")
    min_wallet_balance: Decimal = Field(..., alias="minWalletBalance")
    max_active_strategies: Optional[int] = Field(None, alias="maxActiveStrategies")
    max_strategy_executions_per_day: Optional[int] = Field(None, alias="maxStrategyExecutionsPerDay")
    max_portfolio_capital: Optional[Decimal] = Field(None, alias="maxPortfolioCapital")
    subscription_type: str = Field(..., alias="subscriptionType")
    is_active: bool = Field(..., alias="isActive")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class PlanSummary(BaseModel):
    id: int
    code: str
    name: str

    model_config = {
        "from_attributes": True
    }

class SubscriptionResponse(BaseModel):
    subscription_id: int = Field(..., alias="subscriptionId")
    plan: PlanSummary
    status: str
    start_at: datetime = Field(..., alias="startAt")
    current_period_start: datetime = Field(..., alias="currentPeriodStart")
    current_period_end: datetime = Field(..., alias="currentPeriodEnd")
    auto_renew: bool = Field(..., alias="autoRenew")
    days_remaining: int = Field(..., alias="daysRemaining")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class UsageResponse(BaseModel):
    plan: str
    daily_strategy_limit: int = Field(..., alias="dailyStrategyLimit")
    used_today: int = Field(..., alias="usedToday")
    remaining_today: int = Field(..., alias="remainingToday")
    trading_date: date = Field(..., alias="tradingDate")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class EligibilityResult(BaseModel):
    eligible: bool
    reason: Optional[str] = None
    plan: Optional[str] = None
    strategy_allowed: bool = Field(..., alias="strategyAllowed")
    daily_limit: int = Field(..., alias="dailyLimit")
    used_today: int = Field(..., alias="usedToday")
    remaining_today: int = Field(..., alias="remainingToday")
    wallet_eligible: bool = Field(..., alias="walletEligible")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class SubscriptionRequest(BaseModel):
    planId: int = Field(..., alias="planId")
    paymentProvider: str = Field(..., alias="paymentProvider")

    model_config = {
        "populate_by_name": True
    }

class UpgradeRequest(BaseModel):
    newPlanId: int = Field(..., alias="newPlanId")
    paymentProvider: str = Field(..., alias="paymentProvider")

    model_config = {
        "populate_by_name": True
    }

class DowngradeRequest(BaseModel):
    newPlanId: int = Field(..., alias="newPlanId")

    model_config = {
        "populate_by_name": True
    }

class CancelRequest(BaseModel):
    reason: Optional[str] = None

class SubscribeResponse(BaseModel):
    subscription_id: Optional[int] = Field(None, alias="subscriptionId")
    plan_id: int = Field(..., alias="planId")
    amount: Decimal
    total_amount: Decimal = Field(..., alias="totalAmount")
    provider_order_id: Optional[str] = Field(None, alias="providerOrderId")
    provider_payment_id: Optional[str] = Field(None, alias="providerPaymentId")
    status: str
    paid_at: Optional[datetime] = Field(None, alias="paidAt")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class PaymentResponse(BaseModel):
    id: int
    subscription_id: Optional[int] = Field(None, alias="subscriptionId")
    plan_id: int = Field(..., alias="planId")
    plan_name: str = Field(..., alias="planName")
    amount: Decimal
    gst_amount: Decimal = Field(..., alias="gstAmount")
    total_amount: Decimal = Field(..., alias="totalAmount")
    currency: str
    payment_provider: str = Field(..., alias="paymentProvider")
    provider_order_id: Optional[str] = Field(None, alias="providerOrderId")
    provider_payment_id: Optional[str] = Field(None, alias="providerPaymentId")
    status: str
    paid_at: Optional[datetime] = Field(None, alias="paidAt")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class AdminPlanResponse(BaseModel):
    id: int
    code: str
    name: str
    price: Decimal
    active: bool
    subscriber_count: int = Field(..., alias="subscriberCount")
    strategy_limit: Optional[int] = Field(None, alias="strategyLimit")
    daily_execution_limit: Optional[int] = Field(None, alias="dailyExecutionLimit")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    created_by: str = Field(..., alias="createdBy")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class AdminSubscriptionResponse(BaseModel):
    subscription_id: int = Field(..., alias="subscriptionId")
    user_id: int = Field(..., alias="userId")
    user_email: str = Field(..., alias="userEmail")
    plan_id: int = Field(..., alias="planId")
    plan_code: str = Field(..., alias="planCode")
    plan_name: str = Field(..., alias="planName")
    status: str
    start_at: datetime = Field(..., alias="startAt")
    current_period_start: datetime = Field(..., alias="currentPeriodStart")
    current_period_end: datetime = Field(..., alias="currentPeriodEnd")
    cancelled_at: Optional[datetime] = Field(None, alias="cancelledAt")
    cancellation_reason: Optional[str] = Field(None, alias="cancellationReason")
    auto_renew: bool = Field(..., alias="autoRenew")
    payment_provider: Optional[str] = Field(None, alias="paymentProvider")
    external_subscription_id: Optional[str] = Field(None, alias="externalSubscriptionId")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class QuotaReservation(BaseModel):
    reserved: bool
    reason: Optional[str] = None
    usedExecutionCount: int = Field(..., alias="usedExecutionCount")
    maxExecutionLimit: int = Field(..., alias="maxExecutionLimit")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class AdminPaymentMethodRequest(BaseModel):
    methodType: str = Field(..., alias="methodType") # BANK_ACCOUNT or UPI
    title: str
    bankName: Optional[str] = Field(None, alias="bankName")
    accountNumber: Optional[str] = Field(None, alias="accountNumber")
    ifscCode: Optional[str] = Field(None, alias="ifscCode")
    accountHolderName: Optional[str] = Field(None, alias="accountHolderName")
    upiId: Optional[str] = Field(None, alias="upiId")
    upiQrUrl: Optional[str] = Field(None, alias="upiQrUrl")
    isActive: bool = Field(True, alias="isActive")
    displayOrder: int = Field(0, alias="displayOrder")

    model_config = {
        "populate_by_name": True
    }

class AdminPaymentMethodResponse(BaseModel):
    id: int
    method_type: str = Field(..., alias="methodType")
    title: str
    bank_name: Optional[str] = Field(None, alias="bankName")
    account_number: Optional[str] = Field(None, alias="accountNumber")
    ifsc_code: Optional[str] = Field(None, alias="ifscCode")
    account_holder_name: Optional[str] = Field(None, alias="accountHolderName")
    upi_id: Optional[str] = Field(None, alias="upiId")
    upi_qr_url: Optional[str] = Field(None, alias="upiQrUrl")
    is_active: bool = Field(..., alias="isActive")
    display_order: int = Field(..., alias="displayOrder")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class PlanPurchaseRequest(BaseModel):
    planId: int = Field(..., alias="planId")
    paymentMode: str = Field("UPI", alias="paymentMode") # UPI, BANK_TRANSFER
    utrNumber: str = Field(..., alias="utrNumber", min_length=6)
    userRemarks: Optional[str] = Field(None, alias="userRemarks")

    model_config = {
        "populate_by_name": True
    }

class PendingSubscriptionRequestResponse(BaseModel):
    paymentId: int = Field(..., alias="paymentId")
    subscriptionId: Optional[int] = Field(None, alias="subscriptionId")
    userId: int = Field(..., alias="userId")
    userEmail: str = Field(..., alias="userEmail")
    userName: str = Field(..., alias="userName")
    planId: int = Field(..., alias="planId")
    planCode: str = Field(..., alias="planCode")
    planName: str = Field(..., alias="planName")
    amount: Decimal
    gstAmount: Decimal = Field(..., alias="gstAmount")
    totalAmount: Decimal = Field(..., alias="totalAmount")
    paymentMode: str = Field(..., alias="paymentMode")
    utrNumber: str = Field(..., alias="utrNumber")
    userRemarks: Optional[str] = Field(None, alias="userRemarks")
    adminNotes: Optional[str] = Field(None, alias="adminNotes")
    status: str
    requestedAt: datetime = Field(..., alias="requestedAt")

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

class SubscriptionApprovalActionRequest(BaseModel):
    adminNotes: Optional[str] = Field(None, alias="adminNotes")

    model_config = {
        "populate_by_name": True
    }

class PlanWalletLedgerItem(BaseModel):
    id: int
    paymentId: int = Field(..., alias="paymentId")
    userId: int = Field(..., alias="userId")
    userEmail: str = Field(..., alias="userEmail")
    userName: str = Field(..., alias="userName")
    planName: str = Field(..., alias="planName")
    amount: Decimal
    utrNumber: str = Field(..., alias="utrNumber")
    approvedBy: str = Field(..., alias="approvedBy")
    approvedAt: datetime = Field(..., alias="approvedAt")

    model_config = {
        "populate_by_name": True
    }

class AdminPlanWalletLedgerResponse(BaseModel):
    totalRevenue: Decimal = Field(..., alias="totalRevenue")
    pendingRevenue: Decimal = Field(..., alias="pendingRevenue")
    activeSubscribersCount: int = Field(..., alias="activeSubscribersCount")
    totalTransactionsCount: int = Field(..., alias="totalTransactionsCount")
    ledger: List[PlanWalletLedgerItem]

    model_config = {
        "populate_by_name": True
    }
