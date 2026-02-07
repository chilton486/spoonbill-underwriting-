import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, BigInteger, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


class PaymentIntentStatus(str, Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class PaymentProvider(str, Enum):
    SIMULATED = "SIMULATED"
    BANK_STUB = "BANK_STUB"


PAYMENT_INTENT_TRANSITIONS = {
    PaymentIntentStatus.QUEUED: frozenset({PaymentIntentStatus.SENT, PaymentIntentStatus.FAILED}),
    PaymentIntentStatus.SENT: frozenset({PaymentIntentStatus.CONFIRMED, PaymentIntentStatus.FAILED}),
    PaymentIntentStatus.CONFIRMED: frozenset(),
    PaymentIntentStatus.FAILED: frozenset(),
}

TERMINAL_PAYMENT_STATUSES = frozenset({PaymentIntentStatus.CONFIRMED, PaymentIntentStatus.FAILED})


class PaymentIntent(Base):
    __tablename__ = "payment_intents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, unique=True, index=True)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False, index=True)
    
    amount_cents = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    
    status = Column(String(20), nullable=False, default=PaymentIntentStatus.QUEUED.value)
    idempotency_key = Column(String(255), nullable=False, unique=True)
    
    provider = Column(String(50), nullable=False, default=PaymentProvider.SIMULATED.value)
    provider_reference = Column(String(255), nullable=True)
    
    failure_code = Column(String(100), nullable=True)
    failure_message = Column(String(1000), nullable=True)
    
    sent_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    claim = relationship("Claim", back_populates="payment_intent")
    practice = relationship("Practice", back_populates="payment_intents")
    ledger_entries = relationship("LedgerEntry", back_populates="payment_intent")

    @staticmethod
    def generate_idempotency_key(claim_id: int) -> str:
        return f"claim:{claim_id}:payment:v1"

    __table_args__ = (
        Index("idx_payment_intents_status", "status"),
    )
