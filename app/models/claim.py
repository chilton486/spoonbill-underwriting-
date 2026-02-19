import secrets
import base64
from datetime import datetime, date
from enum import Enum
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Date, BigInteger, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship

from ..database import Base


class ClaimStatus(str, Enum):
    NEW = "NEW"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    APPROVED = "APPROVED"
    PAID = "PAID"
    COLLECTING = "COLLECTING"
    CLOSED = "CLOSED"
    DECLINED = "DECLINED"
    PAYMENT_EXCEPTION = "PAYMENT_EXCEPTION"


CLAIM_STATUS_TRANSITIONS = {
    ClaimStatus.NEW: frozenset({ClaimStatus.NEEDS_REVIEW, ClaimStatus.APPROVED, ClaimStatus.DECLINED}),
    ClaimStatus.NEEDS_REVIEW: frozenset({ClaimStatus.APPROVED, ClaimStatus.DECLINED}),
    ClaimStatus.APPROVED: frozenset({ClaimStatus.PAID, ClaimStatus.DECLINED, ClaimStatus.PAYMENT_EXCEPTION}),
    ClaimStatus.PAID: frozenset({ClaimStatus.COLLECTING}),
    ClaimStatus.COLLECTING: frozenset({ClaimStatus.CLOSED}),
    ClaimStatus.CLOSED: frozenset(),
    ClaimStatus.DECLINED: frozenset(),
    ClaimStatus.PAYMENT_EXCEPTION: frozenset({ClaimStatus.APPROVED, ClaimStatus.DECLINED}),
}

TERMINAL_STATUSES = frozenset({ClaimStatus.CLOSED, ClaimStatus.DECLINED})


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False, index=True)
    patient_name = Column(String(255), nullable=True)
    payer = Column(String(255), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    procedure_date = Column(Date, nullable=True)
    
    status = Column(String(50), nullable=False, default=ClaimStatus.NEW.value)
    
    fingerprint = Column(String(255), unique=True, index=True, nullable=True)
    
    external_claim_id = Column(String(255), nullable=True, index=True)
    external_source = Column(String(50), nullable=True)
    procedure_codes = Column(String(500), nullable=True)
    
    claim_token = Column(String(20), unique=True, index=True, nullable=False)
    
    payment_exception = Column(Boolean, nullable=False, default=False)
    exception_code = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    practice = relationship("Practice", back_populates="claims")
    underwriting_decisions = relationship("UnderwritingDecision", back_populates="claim")
    audit_events = relationship("AuditEvent", back_populates="claim")
    documents = relationship("ClaimDocument", back_populates="claim")
    payment_intent = relationship("PaymentIntent", back_populates="claim", uselist=False)
    ledger_entries = relationship("LedgerEntry", back_populates="claim")
    
    @staticmethod
    def generate_claim_token() -> str:
        """Generate a unique, non-guessable claim token.
        
        Format: SB-CLM-<8 chars base32>
        Example: SB-CLM-A3B7C9D2
        """
        random_bytes = secrets.token_bytes(5)
        token_chars = base64.b32encode(random_bytes).decode('ascii')[:8]
        return f"SB-CLM-{token_chars}"
    
    @staticmethod
    def compute_fingerprint(practice_id: Optional[int], patient_name: str, procedure_date: date, amount_cents: int, payer: str) -> str:
        parts = [
            str(practice_id) if practice_id else "",
            patient_name or "",
            procedure_date.isoformat() if procedure_date else "",
            str(amount_cents),
            payer or "",
        ]
        return "|".join(parts)
