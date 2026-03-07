"""Payer model - represents insurance entities."""
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from ..database import Base


class Payer(Base):
    __tablename__ = "payers"

    id = Column(Integer, primary_key=True, index=True)
    payer_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    plan_types = Column(JSONB, nullable=True)  # e.g. ["PPO", "HMO", "Medicaid"]
    eft_capable = Column(Boolean, nullable=False, default=False)
    era_capable = Column(Boolean, nullable=False, default=False)
    filing_limit_days = Column(Integer, nullable=True)
    contact_info = Column(JSONB, nullable=True)  # phone, fax, portal URL, etc.
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    contracts = relationship("PayerContract", back_populates="payer")
    remittances = relationship("Remittance", back_populates="payer")

    __table_args__ = (
        Index("idx_payers_name", "name"),
    )
