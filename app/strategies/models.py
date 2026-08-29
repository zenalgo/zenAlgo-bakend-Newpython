from sqlalchemy import Column, BigInteger, String, Numeric, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    strategy_type = Column(String(50), nullable=False, default="CUSTOM_MULTI_LEG")
    status = Column(String(30), nullable=False, default="DRAFT", index=True) # DRAFT, PAPER, ACTIVE_LIVE, PAUSED, STOPPED
    target_profit = Column(Numeric(15, 2), nullable=True)
    stop_loss = Column(Numeric(15, 2), nullable=True)
    trailing_stop_loss = Column(Numeric(15, 2), nullable=True)
    allocated_capital = Column(Numeric(15, 2), nullable=True)
    parameters = Column(Text, nullable=True)
    mode = Column(String(30), nullable=False, default="PAPER") # PAPER, LIVE
    created_by = Column(String(255), nullable=True)
    is_prebuilt = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    current_version_id = Column(BigInteger, ForeignKey("strategy_versions.id", ondelete="SET NULL", use_alter=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    current_version = relationship("StrategyVersion", foreign_keys=[current_version_id], post_update=True)
    versions = relationship("StrategyVersion", back_populates="strategy", foreign_keys="[StrategyVersion.strategy_id]", cascade="all, delete-orphan")
    executions = relationship("StrategyExecution", back_populates="strategy", cascade="all, delete-orphan")

class StrategyVersion(Base):
    __tablename__ = "strategy_versions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    strategy_id = Column(BigInteger, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    underlying = Column(String(50), nullable=False)
    capital = Column(Numeric(15, 2), nullable=False)
    trading_type = Column(String(30), nullable=False, default="INTRADAY")
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("strategy_id", "version_number", name="uk_strategy_version"),
    )

    strategy = relationship("Strategy", back_populates="versions", foreign_keys=[strategy_id])
    legs = relationship("StrategyLeg", back_populates="version", cascade="all, delete-orphan")
    entry_setting = relationship("StrategyEntrySetting", uselist=False, back_populates="version", cascade="all, delete-orphan")
    entry_days = relationship("StrategyEntryDay", back_populates="version", cascade="all, delete-orphan")
    exit_setting = relationship("StrategyExitSetting", uselist=False, back_populates="version", cascade="all, delete-orphan")

class StrategyLeg(Base):
    __tablename__ = "strategy_legs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    strategy_version_id = Column(BigInteger, ForeignKey("strategy_versions.id", ondelete="CASCADE"), nullable=False)
    sequence = Column(Integer, nullable=False)
    segment = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)
    strike_selection = Column(String(50), nullable=False)
    strike_value = Column(Numeric(15, 2), nullable=True)
    expiry = Column(String(50), nullable=False)
    lots = Column(Integer, nullable=False)
    target_type = Column(String(50), nullable=False, default="NONE")
    target_value = Column(Numeric(15, 2), nullable=True)
    stop_loss_type = Column(String(50), nullable=False, default="NONE")
    stop_loss_value = Column(Numeric(15, 2), nullable=True)
    trailing_sl_enabled = Column(Boolean, nullable=False, default=False)
    trailing_sl_activate_type = Column(String(50), nullable=True)
    trailing_sl_activate_value = Column(Numeric(15, 2), nullable=True)
    trailing_sl_increase_by = Column(Numeric(15, 2), nullable=True)
    trailing_sl_by = Column(Numeric(15, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("strategy_version_id", "sequence", name="uk_version_sequence"),
    )

    version = relationship("StrategyVersion", back_populates="legs")

class StrategyEntrySetting(Base):
    __tablename__ = "strategy_entry_settings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    strategy_version_id = Column(BigInteger, ForeignKey("strategy_versions.id", ondelete="CASCADE"), nullable=False)
    entry_time = Column(String(10), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    version = relationship("StrategyVersion", back_populates="entry_setting")

class StrategyEntryDay(Base):
    __tablename__ = "strategy_entry_days"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    strategy_version_id = Column(BigInteger, ForeignKey("strategy_versions.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("strategy_version_id", "day_of_week", name="uk_version_day"),
    )

    version = relationship("StrategyVersion", back_populates="entry_days")

class StrategyExitSetting(Base):
    __tablename__ = "strategy_exit_settings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    strategy_version_id = Column(BigInteger, ForeignKey("strategy_versions.id", ondelete="CASCADE"), nullable=False)
    profit_mtm_type = Column(String(50), nullable=False, default="NONE")
    profit_mtm_value = Column(Numeric(15, 2), nullable=True)
    stop_loss_mtm_type = Column(String(50), nullable=False, default="NONE")
    stop_loss_mtm_value = Column(Numeric(15, 2), nullable=True)
    exit_time = Column(String(10), nullable=False)
    exit_on_expiry = Column(Boolean, nullable=False, default=True)
    exit_after_entry_type = Column(String(50), nullable=False, default="NONE")
    exit_after_entry_value = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    version = relationship("StrategyVersion", back_populates="exit_setting")

class StrategyExecution(Base):
    __tablename__ = "strategy_executions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    strategy_id = Column(BigInteger, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_version_id = Column(BigInteger, ForeignKey("strategy_versions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_trace_id = Column(BigInteger, ForeignKey("strategy_user_execution_traces.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(30), nullable=False, default="RUNNING") # RUNNING, SUCCESS, FAILED, SQUARED_OFF
    entry_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    exit_time = Column(DateTime(timezone=True), nullable=True)
    realized_pnl = Column(Numeric(15, 2), default=0.00)
    unrealized_pnl = Column(Numeric(15, 2), default=0.00)
    execution_logs = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    strategy = relationship("Strategy", back_populates="executions")
    strategy_version = relationship("StrategyVersion")
    user = relationship("User")
    execution_trace = relationship("StrategyUserExecutionTrace")
    legs = relationship("StrategyExecutionLeg", back_populates="strategy_execution", cascade="all, delete-orphan")

class StrategyExecutionLeg(Base):
    __tablename__ = "strategy_execution_legs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    strategy_execution_id = Column(BigInteger, ForeignKey("strategy_executions.id", ondelete="CASCADE"), nullable=False)
    strategy_leg_id = Column(BigInteger, ForeignKey("strategy_legs.id", ondelete="CASCADE"), nullable=False)
    broker_order_id = Column(String(100), nullable=True, index=True)
    correlation_id = Column(String(100), nullable=True, unique=True, index=True)
    status = Column(String(30), nullable=False, default="PENDING") # PENDING, OPEN, FILLED, REJECTED, CANCELLED, UNKNOWN
    quantity = Column(Integer, nullable=False)
    requested_quantity = Column(Integer, nullable=True)
    filled_quantity = Column(Integer, default=0)
    remaining_quantity = Column(Integer, default=0)
    price = Column(Numeric(15, 2), nullable=True)
    requested_price = Column(Numeric(15, 2), default=0.00)
    average_fill_price = Column(Numeric(15, 2), default=0.00)
    rejection_reason = Column(Text, nullable=True)
    reconciliation_attempts = Column(Integer, default=0)
    last_reconciled_at = Column(DateTime(timezone=True), nullable=True)
    square_off_order_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    strategy_execution = relationship("StrategyExecution", back_populates="legs")
    strategy_leg = relationship("StrategyLeg")
