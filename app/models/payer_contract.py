"""PayerContract model - represents practice-specific reimbursement rules."""
from datetime import datetime, date
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from ..database import Base


class NetworkStatus(str, Enum):
    IN_NETWORK = "IN_NETWORK"
    OUT_OF_NETWORK = "OUT_OF_NETWORK"
    PENDING = "PENDING"


class ContractStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    PENDING = "PENDING"
    TERMINATED = "TERMINATED"


class PayerContract(Base):
    __tablename__ = "payer_contracts"

    id = Column(Integer, primary_key=True, index=True)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False, index=True)
    payer_id = Column(Integer, ForeignKey("payers.id"), nullable=False, index=True)

    effective_start_date = Column(Date, nullable=True)
    effective_end_date = Column(Date, nullable=True)
    network_status = Column(String(50), nullable=False, default=NetworkStatus.IN_NETWORK.value)
    status = Column(String(50), nullable=False, default=ContractStatus.ACTIVE.value)

    annual_max_norms = Column(JSONB, nullable=True)
    documentation_rules = Column(JSONB, nullable=True)
    timely_filing_limit_days = Column(Integer, nullable=True)
    cob_rules = Column(Text, nullable=True)
    contract_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    practice = relationship("Practice", back_populates="payer_contracts")
    payer = relationship("Payer", back_populates="contracts")
    fee_schedule_items = relationship("FeeScheduleItem", back_populates="payer_contract")

    __table_args__ = (
        Index("idx_payer_contracts_practice_payer", "practice_id", "payer_id"),
        Index("idx_payer_contracts_status", "status"),
    )
