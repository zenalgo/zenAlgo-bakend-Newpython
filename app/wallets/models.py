from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    balance = Column(Numeric(18, 2), nullable=False, default=0.00)
    currency = Column(String(10), nullable=False, default="INR")
    version = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="wallet")
    transactions = relationship("WalletTransaction", back_populates="wallet", cascade="all, delete-orphan")

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    wallet_id = Column(BigInteger, ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    balance_before = Column(Numeric(18, 2), nullable=False)
    balance_after = Column(Numeric(18, 2), nullable=False)
    transaction_type = Column(String(50), nullable=False) # DEPOSIT, WITHDRAWAL, etc.
    description = Column(String(500), nullable=True)
    reference_type = Column(String(100), nullable=True)
    reference_id = Column(String(255), nullable=True)
    idempotency_key = Column(String(255), unique=True, nullable=True, index=True)
    status = Column(String(50), nullable=False, default="COMPLETED")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    wallet = relationship("Wallet", back_populates="transactions")
