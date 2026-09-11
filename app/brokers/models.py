from sqlalchemy import Column, BigInteger, String, Numeric, Integer, Boolean, DateTime, Date, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.core.security import encrypt_credentials, decrypt_credentials

class BrokerAccount(Base):
    """Generic broker account entity supporting any registered broker."""

    __tablename__ = "broker_accounts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_code = Column(String(50), nullable=False, index=True)  # DHAN, ZERODHA, MOCK, etc.
    account_client_id = Column(String(100), nullable=False, index=True)
    account_name = Column(String(200), nullable=True)
    email = Column(String(255), nullable=True)
    mobile_no = Column(String(50), nullable=True)
    auth_type = Column(String(50), nullable=False, default="TOKEN")
    encrypted_credentials = Column(Text, nullable=True)
    expiry_time = Column(DateTime(timezone=True), nullable=True)
    primary_ip = Column(String(100), nullable=True)
    secondary_ip = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="ACTIVE", index=True)  # ACTIVE, EXPIRED, DISABLED
    connection_date = Column(Date, nullable=False, server_default=func.now())
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "broker_code", name="uk_user_broker_code"),
    )

    user = relationship("User")

    @property
    def credentials(self) -> dict:
        return decrypt_credentials(self.encrypted_credentials)

    def get_credentials(self) -> dict:
        return self.credentials

    def set_credentials(self, cred_dict: dict) -> None:
        self.encrypted_credentials = encrypt_credentials(cred_dict)

    # Backward compatibility properties for Dhan session accessors
    @property
    def dhan_client_id(self) -> str:
        return self.account_client_id

    @dhan_client_id.setter
    def dhan_client_id(self, val: str):
        self.account_client_id = val

    @property
    def access_token(self) -> str:
        creds = self.credentials
        return creds.get("accessToken", "")

    @access_token.setter
    def access_token(self, val: str):
        creds = self.credentials
        creds["accessToken"] = val
        self.set_credentials(creds)

    @property
    def broker_name(self) -> str:
        return self.broker_code

    @broker_name.setter
    def broker_name(self, val: str):
        self.broker_code = val


class UserDailyBrokerConnection(Base):
    """Tracks daily active broker selection per user for business date (Asia/Kolkata).
    Enforces EXACTLY ONE BROKER PER USER PER CALENDAR DAY at database level.
    """
    __tablename__ = "user_daily_broker_connections"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    connection_date = Column(Date, nullable=False, index=True)  # Calendar date in Asia/Kolkata
    broker_account_id = Column(BigInteger, ForeignKey("broker_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_code = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="ACTIVE")  # ACTIVE, DISCONNECTED
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "connection_date", name="uk_user_daily_broker_date"),
    )

    user = relationship("User")
    broker_account = relationship("BrokerAccount")


# Alias DhanBrokerSession to BrokerAccount for legacy queries/imports
DhanBrokerSession = BrokerAccount


class UserHolding(Base):
    __tablename__ = "user_holdings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_name = Column(String(50), nullable=False, default="DHAN")
    trading_symbol = Column(String(100), nullable=False, index=True)
    security_id = Column(String(50), nullable=True)
    isin = Column(String(50), nullable=False)
    exchange = Column(String(20), default="NSE")
    total_qty = Column(Integer, nullable=False, default=0)
    dp_qty = Column(Integer, default=0)
    t1_qty = Column(Integer, default=0)
    available_qty = Column(Integer, default=0)
    collateral_qty = Column(Integer, default=0)
    avg_cost_price = Column(Numeric(15, 2), default=0.00)
    last_traded_price = Column(Numeric(15, 2), default=0.00)
    synced_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "broker_name", "isin", name="uk_user_holdings_user_broker_isin"),
    )

    user = relationship("User")


class UserPosition(Base):
    __tablename__ = "user_positions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_name = Column(String(50), nullable=False, default="DHAN")
    trading_symbol = Column(String(100), nullable=False)
    security_id = Column(String(50), nullable=True)
    position_type = Column(String(50), nullable=False, default="INTRADAY")
    exchange_segment = Column(String(50), nullable=True)
    product_type = Column(String(50), nullable=True)
    net_qty = Column(Integer, nullable=False, default=0)
    buy_qty = Column(Integer, default=0)
    sell_qty = Column(Integer, default=0)
    buy_avg = Column(Numeric(15, 2), default=0.00)
    sell_avg = Column(Numeric(15, 2), default=0.00)
    realized_profit = Column(Numeric(15, 2), default=0.00)
    unrealized_profit = Column(Numeric(15, 2), default=0.00)
    synced_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "broker_name", "security_id", "position_type", name="uk_user_positions_user_sec_pos"),
    )

    user = relationship("User")


class UserOrder(Base):
    __tablename__ = "user_orders"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_name = Column(String(50), nullable=False, default="DHAN")
    broker_order_id = Column(String(100), nullable=True, index=True)
    correlation_id = Column(String(100), nullable=True, unique=True, index=True)
    trading_symbol = Column(String(100), nullable=True)
    security_id = Column(String(50), nullable=True)
    exchange_segment = Column(String(50), nullable=True)
    transaction_type = Column(String(20), nullable=False)
    order_type = Column(String(50), nullable=False)
    product_type = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    requested_quantity = Column(Integer, nullable=True)
    filled_quantity = Column(Integer, default=0)
    remaining_quantity = Column(Integer, default=0)
    disclosed_quantity = Column(Integer, default=0)
    price = Column(Numeric(15, 2), default=0.00)
    requested_price = Column(Numeric(15, 2), default=0.00)
    average_fill_price = Column(Numeric(15, 2), default=0.00)
    trigger_price = Column(Numeric(15, 2), default=0.00)
    order_status = Column(String(50), nullable=False, default="PENDING", index=True)
    rejection_reason = Column(Text, nullable=True)
    reconciliation_attempts = Column(Integer, default=0)
    last_reconciled_at = Column(DateTime(timezone=True), nullable=True)
    square_off_order_id = Column(String(100), nullable=True)
    order_timestamp = Column(DateTime(timezone=True), nullable=True)
    synced_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "broker_name", "broker_order_id", name="uk_user_orders_user_order_id"),
    )

    user = relationship("User")


class UserTrade(Base):
    __tablename__ = "user_trades"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_name = Column(String(50), nullable=False, default="DHAN")
    broker_trade_id = Column(String(100), nullable=False)
    broker_order_id = Column(String(100), nullable=True)
    trading_symbol = Column(String(100), nullable=True)
    security_id = Column(String(50), nullable=True)
    exchange_segment = Column(String(50), nullable=True)
    transaction_type = Column(String(20), nullable=False)
    traded_quantity = Column(Integer, nullable=False)
    traded_price = Column(Numeric(15, 2), nullable=False)
    traded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "broker_name", "broker_trade_id", name="uk_user_trades_user_trade_id"),
    )

    user = relationship("User")


class UserFundSnapshot(Base):
    __tablename__ = "user_fund_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_name = Column(String(50), nullable=False, default="DHAN")
    account_client_id = Column(String(100), nullable=True)
    available_balance = Column(Numeric(15, 2), default=0.00)
    sod_limit = Column(Numeric(15, 2), default=0.00)
    collateral_amount = Column(Numeric(15, 2), default=0.00)
    receiveable_amount = Column(Numeric(15, 2), default=0.00)
    utilized_amount = Column(Numeric(15, 2), default=0.00)
    blocked_payout_amount = Column(Numeric(15, 2), default=0.00)
    withdrawable_balance = Column(Numeric(15, 2), default=0.00)
    snapshot_date = Column(Date, nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "broker_name", "snapshot_date", name="uk_user_funds_user_date"),
    )

    user = relationship("User")

    # Backward compatibility accessor
    @property
    def dhan_client_id(self) -> str:
        return self.account_client_id

    @dhan_client_id.setter
    def dhan_client_id(self, val: str):
        self.account_client_id = val
