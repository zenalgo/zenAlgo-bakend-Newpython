from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Date, ForeignKey, UniqueConstraint, Text, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base

class StrategySignal(Base):
    __tablename__ = "strategy_signals"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    strategy_id = Column(BigInteger, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_version_id = Column(BigInteger, ForeignKey("strategy_versions.id", ondelete="CASCADE"), nullable=False)
    trading_date = Column(Date, nullable=False, default=func.current_date)
    entry_time = Column(String(10), nullable=False, default="00:00")
    
    # Event-Driven Signal Engine Extensions
    signal_key = Column(String(255), nullable=True, unique=True, index=True)
    market_event_key = Column(String(255), nullable=True, index=True)
    signal_type = Column(String(20), nullable=False, default="ENTRY", server_default="ENTRY")
    direction = Column(String(20), nullable=False, default="BUY", server_default="BUY")
    status = Column(String(30), nullable=False, default="CREATED", server_default="CREATED")
    price = Column(Numeric(15, 2), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("strategy_id", "strategy_version_id", "trading_date", "entry_time", name="uk_strategy_version_date_time"),
    )

    strategy = relationship("Strategy")
    strategy_version = relationship("StrategyVersion")

class StrategyExecutionBatch(Base):
    __tablename__ = "strategy_execution_batches"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    signal_id = Column(BigInteger, ForeignKey("strategy_signals.id", ondelete="CASCADE"), nullable=False)
    strategy_id = Column(BigInteger, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_version_id = Column(BigInteger, ForeignKey("strategy_versions.id", ondelete="CASCADE"), nullable=False)
    trading_date = Column(Date, nullable=False)
    total_users = Column(Integer, nullable=False, default=0)
    eligible_users = Column(Integer, nullable=False, default=0)
    rejected_users = Column(Integer, nullable=False, default=0)
    execution_started_users = Column(Integer, nullable=False, default=0)
    successful_users = Column(Integer, nullable=False, default=0)
    failed_users = Column(Integer, nullable=False, default=0)
    not_executed_users = Column(Integer, nullable=False, default=0)
    status = Column(String(40), nullable=False) # PROCESSING, COMPLETED, COMPLETED_WITH_ERRORS
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    signal = relationship("StrategySignal")
    strategy = relationship("Strategy")
    strategy_version = relationship("StrategyVersion")
    traces = relationship("StrategyUserExecutionTrace", back_populates="execution_batch", cascade="all, delete-orphan")

class StrategyUserExecutionTrace(Base):
    __tablename__ = "strategy_user_execution_traces"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    execution_batch_id = Column(BigInteger, ForeignKey("strategy_execution_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    signal_id = Column(BigInteger, ForeignKey("strategy_signals.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_id = Column(BigInteger, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    strategy_version_id = Column(BigInteger, ForeignKey("strategy_versions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(BigInteger, nullable=True)
    broker_account_id = Column(BigInteger, nullable=True)
    broker = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, index=True) # PENDING, EXECUTED, BROKER_SESSION_INVALID, FAILED, NOT_EXECUTED, etc.
    eligibility_status = Column(String(50), nullable=True)
    execution_status = Column(String(50), nullable=True)
    failure_code = Column(String(100), nullable=True)
    failure_reason = Column(String(500), nullable=True)
    rejection_code = Column(String(100), nullable=True)
    rejection_reason = Column(String(500), nullable=True)
    current_step = Column(String(100), nullable=True)
    correlation_id = Column(String(255), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("signal_id", "user_id", name="uq_signal_user_execution_trace"),
    )

    execution_batch = relationship("StrategyExecutionBatch", back_populates="traces")
    signal = relationship("StrategySignal")
    strategy = relationship("Strategy")
    strategy_version = relationship("StrategyVersion")
    user = relationship("User")
    events = relationship("StrategyExecutionTraceEvent", back_populates="execution_trace", cascade="all, delete-orphan")

class StrategyExecutionTraceEvent(Base):
    __tablename__ = "strategy_execution_trace_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    execution_trace_id = Column(BigInteger, ForeignKey("strategy_user_execution_traces.id", ondelete="CASCADE"), nullable=False, index=True)
    step = Column(String(100), nullable=False) # INIT, USER_CHECK, SUBSCRIPTION_CHECK, etc.
    status = Column(String(50), nullable=False) # SUCCESS, FAILED, PENDING
    message = Column(String(1000), nullable=True)
    error_code = Column(String(100), nullable=True)
    event_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    execution_trace = relationship("StrategyUserExecutionTrace", back_populates="events")
