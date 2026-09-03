from sqlalchemy import Column, BigInteger, String, Numeric, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Instrument(Base):
    """Universal Instrument Master (sector-wise classified stocks, ETFs, indices)."""
    __tablename__ = "instruments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(50), unique=True, nullable=False, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    sector = Column(String(100), nullable=False, index=True)
    instrument_type = Column(String(50), nullable=False, default="EQUITY")  # EQUITY, ETF, INDEX
    is_fno = Column(Boolean, nullable=False, default=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    broker_mappings = relationship("BrokerInstrument", back_populates="instrument", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self):
        return f"<Instrument symbol={self.symbol} sector={self.sector}>"


class BrokerInstrument(Base):
    """Broker-specific execution parameters (e.g. Dhan securityId, segment, lot size)."""
    __tablename__ = "broker_instruments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    instrument_id = Column(BigInteger, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_code = Column(String(50), nullable=False, index=True)  # DHAN
    security_id = Column(String(50), nullable=False, index=True)  # e.g. "2885" for RELIANCE, "21401" for TATAGOLD
    exchange_segment = Column(String(50), nullable=False, default="NSE_EQ")  # NSE_EQ, BSE_EQ, NSE_FNO
    trading_symbol = Column(String(100), nullable=False)
    lot_size = Column(Integer, nullable=False, default=1)
    tick_size = Column(Numeric(10, 4), nullable=False, default=0.05)
    extra_data = Column(Text, nullable=True)  # JSON-encoded extra broker parameters
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("instrument_id", "broker_code", "exchange_segment", name="uk_inst_broker_segment"),
    )

    instrument = relationship("Instrument", back_populates="broker_mappings")

    def __repr__(self):
        return f"<BrokerInstrument broker={self.broker_code} sec_id={self.security_id}>"
