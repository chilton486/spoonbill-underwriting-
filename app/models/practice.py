from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, BigInteger
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

    users = relationship("User", back_populates="practice")
    claims = relationship("Claim", back_populates="practice")
    documents = relationship("ClaimDocument", back_populates="practice")
    payment_intents = relationship("PaymentIntent", back_populates="practice")
    ledger_accounts = relationship("LedgerAccount", back_populates="practice")
