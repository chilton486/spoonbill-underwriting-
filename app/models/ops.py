import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, BigInteger, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID

from ..database import Base


class TaskStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class PlaybookType(str, Enum):
    PAYMENT_FAILED = "PAYMENT_FAILED"
    INTEGRATION_SYNC_FAILED = "INTEGRATION_SYNC_FAILED"
    CLAIM_MISSING_INFO = "CLAIM_MISSING_INFO"
    DENIAL_SPIKE = "DENIAL_SPIKE"


class OpsTask(Base):
    __tablename__ = "ops_tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default=TaskStatus.OPEN.value)
    priority = Column(String(20), nullable=False, default="medium")
    playbook_type = Column(String(50), nullable=True)

    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    payment_intent_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    due_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_ops_tasks_status", "status"),
        Index("idx_ops_tasks_practice", "practice_id", "status"),
        Index("idx_ops_tasks_due", "due_at"),
    )


class ExternalBalanceSnapshot(Base):
    __tablename__ = "external_balance_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    facility = Column(String(100), nullable=False)
    balance_cents = Column(BigInteger, nullable=False)
    as_of = Column(DateTime, nullable=False)
    source = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_ext_balance_facility", "facility", "as_of"),
    )


class ExternalPaymentConfirmation(Base):
    __tablename__ = "external_payment_confirmations"

    id = Column(Integer, primary_key=True, index=True)
    payment_intent_id = Column(UUID(as_uuid=True), ForeignKey("payment_intents.id"), nullable=False, index=True)
    rail_ref = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False)
    confirmed_at = Column(DateTime, nullable=True)
    raw_json = Column(Text, nullable=True)
    resolved = Column(String(10), nullable=False, default="false")
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_ext_pay_confirm_pi", "payment_intent_id"),
        Index("idx_ext_pay_confirm_status", "status"),
    )
