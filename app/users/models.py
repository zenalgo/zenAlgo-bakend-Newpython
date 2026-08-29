from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    TRADER = "TRADER"
    USER = "USER"
    PARTNER = "PARTNER"

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole, name="user_role", inherit_schema=True), nullable=False, default=UserRole.USER)
    is_active = Column(Boolean, nullable=False, default=True)
    referral_code = Column(String(50), unique=True, nullable=False, index=True)
    referred_by_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    first_name = Column(String(50), nullable=True)
    last_name = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    referred_by = relationship("User", remote_side=[id], backref="referrals")
    wallet = relationship("Wallet", uselist=False, back_populates="user", cascade="all, delete-orphan")
