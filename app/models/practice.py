from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class PracticeStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Practice(Base):
    __tablename__ = "practices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default=PracticeStatus.ACTIVE.value)
    funding_limit_cents = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    # Ontology expansion fields
    legal_name = Column(String(255), nullable=True)
    dba_name = Column(String(255), nullable=True)
    ein = Column(String(20), nullable=True)
    group_npi = Column(String(20), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    phone = Column(String(50), nullable=True)
    owners_metadata = Column(JSONB, nullable=True)
    bank_payout_profile = Column(JSONB, nullable=True)
    pms_type = Column(String(100), nullable=True)  # e.g. "Open Dental", "Dentrix"
    clearinghouse = Column(String(100), nullable=True)

    users = relationship("User", back_populates="practice")
    claims = relationship("Claim", back_populates="practice")
    documents = relationship("ClaimDocument", back_populates="practice")
    payment_intents = relationship("PaymentIntent", back_populates="practice")
    ledger_accounts = relationship("LedgerAccount", back_populates="practice")
    integration_connections = relationship("IntegrationConnection", back_populates="practice")
    providers = relationship("Provider", back_populates="practice")
    payer_contracts = relationship("PayerContract", back_populates="practice")
    remittances = relationship("Remittance", back_populates="practice")
