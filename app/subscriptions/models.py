from sqlalchemy import Column, BigInteger, String, Numeric, Integer, Boolean, DateTime, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base

class Plan(Base):
    __tablename__ = "plans"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String, nullable=True)
    monthly_price = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="INR")
    gst_percentage = Column(Numeric(5, 2), nullable=False, default=18.00)
    min_wallet_balance = Column(Numeric(15, 2), nullable=False, default=0.00)
    max_active_strategies = Column(Integer, nullable=True)
    max_strategy_executions_per_day = Column(Integer, nullable=True)
    max_portfolio_capital = Column(Numeric(15, 2), nullable=True)
    subscription_type = Column(String(30), nullable=False, default="MONTHLY")
    is_active = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, default=0)
    created_by_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    updated_by_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_id])
    updated_by = relationship("User", foreign_keys=[updated_by_id])
    features = relationship("PlanFeature", back_populates="plan", cascade="all, delete-orphan")
    strategy_access = relationship("PlanStrategyAccess", back_populates="plan", cascade="all, delete-orphan")

class PlanFeature(Base):
    __tablename__ = "plan_features"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    plan_id = Column(BigInteger, ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    feature_code = Column(String(100), nullable=False)
    feature_value = Column(String(255), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    created_by_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("plan_id", "feature_code", name="uq_plan_feature_code"),
    )

    plan = relationship("Plan", back_populates="features")

class PlanStrategyAccess(Base):
    __tablename__ = "plan_strategy_access"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    plan_id = Column(BigInteger, ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_id = Column(BigInteger, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    created_by_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    updated_by_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("plan_id", "strategy_id", name="uq_plan_strategy_access"),
    )

    plan = relationship("Plan", back_populates="strategy_access")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    plan_id = Column(BigInteger, ForeignKey("plans.id"), nullable=False)
    status = Column(String(30), nullable=False, index=True) # ACTIVE, EXPIRED, CANCELLED, etc.
    start_at = Column(DateTime(timezone=True), nullable=False)
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False, index=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(String(500), nullable=True)
    auto_renew = Column(Boolean, nullable=False, default=True)
    payment_provider = Column(String(30), nullable=True)
    external_subscription_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    plan = relationship("Plan")

class SubscriptionEvent(Base):
    __tablename__ = "subscription_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    old_plan_id = Column(BigInteger, nullable=True)
    new_plan_id = Column(BigInteger, nullable=True)
    old_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=True)
    reference_id = Column(String(255), nullable=True)
    event_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    subscription = relationship("Subscription")

class UserDailyStrategyUsage(Base):
    __tablename__ = "user_daily_strategy_usage"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    trading_date = Column(Date, nullable=False)
    strategy_execution_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "trading_date", name="uq_user_daily_usage"),
    )

    user = relationship("User")

class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    subscription_id = Column(BigInteger, ForeignKey("subscriptions.id"), nullable=True)
    plan_id = Column(BigInteger, ForeignKey("plans.id"), nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    gst_amount = Column(Numeric(15, 2), nullable=False, default=0.00)
    total_amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(10), nullable=False, default="INR")
    payment_provider = Column(String(30), nullable=False)
    provider_payment_id = Column(String(255), nullable=True, index=True)
    provider_order_id = Column(String(255), nullable=True)
    status = Column(String(30), nullable=False) # PENDING, SUCCESS, FAILED
    idempotency_key = Column(String(255), unique=True, nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User")
    subscription = relationship("Subscription")
    plan = relationship("Plan")
