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
