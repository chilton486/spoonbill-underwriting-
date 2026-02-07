import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, BigInteger, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from ..database import Base


class LedgerAccountType(str, Enum):
    CAPITAL_CASH = "CAPITAL_CASH"
    PAYMENT_CLEARING = "PAYMENT_CLEARING"
    PRACTICE_PAYABLE = "PRACTICE_PAYABLE"


class LedgerEntryDirection(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class LedgerEntryStatus(str, Enum):
    PENDING = "PENDING"
    POSTED = "POSTED"
    REVERSED = "REVERSED"


class LedgerEntryRelatedType(str, Enum):
    PAYMENT_INTENT = "PAYMENT_INTENT"
    ADJUSTMENT = "ADJUSTMENT"


class LedgerAccount(Base):
    __tablename__ = "ledger_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_type = Column(String(50), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    practice = relationship("Practice", back_populates="ledger_accounts")
    entries = relationship("LedgerEntry", back_populates="account")

    __table_args__ = (
        UniqueConstraint("account_type", "practice_id", "currency", name="uq_ledger_account_type_practice_currency"),
        Index("idx_ledger_accounts_type", "account_type"),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("ledger_accounts.id"), nullable=False, index=True)
    
    related_type = Column(String(50), nullable=False)
    related_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    
    direction = Column(String(10), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    status = Column(String(20), nullable=False, default=LedgerEntryStatus.PENDING.value)
    
    idempotency_key = Column(String(255), nullable=False, unique=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    account = relationship("LedgerAccount", back_populates="entries")
    claim = relationship("Claim", back_populates="ledger_entries")
    payment_intent = relationship(
        "PaymentIntent",
        primaryjoin="and_(LedgerEntry.related_type=='PAYMENT_INTENT', foreign(LedgerEntry.related_id)==PaymentIntent.id)",
        back_populates="ledger_entries",
        viewonly=True,
    )

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_ledger_entry_amount_positive"),
        Index("idx_ledger_entries_related", "related_type", "related_id"),
        Index("idx_ledger_entries_status", "status"),
    )
