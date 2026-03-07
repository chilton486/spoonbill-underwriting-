"""Remittance and RemittanceLine models - ERA/payer explanation-of-payment."""
from datetime import datetime, date
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Date, BigInteger, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from ..database import Base


class PostingStatus(str, Enum):
    RECEIVED = "RECEIVED"
    POSTING = "POSTING"
    POSTED = "POSTED"
    EXCEPTION = "EXCEPTION"


class RemittanceSourceType(str, Enum):
    ERA_835 = "ERA_835"
    MANUAL = "MANUAL"
    CSV_IMPORT = "CSV_IMPORT"
    SYNTHETIC = "SYNTHETIC"


class Remittance(Base):
    __tablename__ = "remittances"

    id = Column(Integer, primary_key=True, index=True)
    payer_id = Column(Integer, ForeignKey("payers.id"), nullable=True, index=True)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False, index=True)

    payer_name = Column(String(255), nullable=True)  # denormalized for display
    trace_number = Column(String(100), nullable=True, index=True)
    payment_date = Column(Date, nullable=True)
    total_paid_cents = Column(BigInteger, nullable=False, default=0)
    total_adjustments_cents = Column(BigInteger, nullable=False, default=0)
    raw_file_ref = Column(String(500), nullable=True)
    posting_status = Column(String(30), nullable=False, default=PostingStatus.RECEIVED.value)
    source_type = Column(String(30), nullable=False, default=RemittanceSourceType.SYNTHETIC.value)
    era_reference = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    payer = relationship("Payer", back_populates="remittances")
    practice = relationship("Practice", back_populates="remittances")
    lines = relationship("RemittanceLine", back_populates="remittance")

    __table_args__ = (
        Index("idx_remittances_practice", "practice_id"),
        Index("idx_remittances_payer", "payer_id"),
        Index("idx_remittances_status", "posting_status"),
    )


class RemittanceLineMatchStatus(str, Enum):
    MATCHED = "MATCHED"
    UNMATCHED = "UNMATCHED"
    PARTIAL = "PARTIAL"
    MISMATCH = "MISMATCH"


class RemittanceLine(Base):
    __tablename__ = "remittance_lines"

    id = Column(Integer, primary_key=True, index=True)
    remittance_id = Column(Integer, ForeignKey("remittances.id"), nullable=False, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    claim_line_id = Column(Integer, ForeignKey("claim_lines.id"), nullable=True, index=True)

    external_claim_id = Column(String(255), nullable=True)
    cdt_code = Column(String(10), nullable=True)
    paid_cents = Column(BigInteger, nullable=False, default=0)
    allowed_cents = Column(BigInteger, nullable=True)
    adjustment_cents = Column(BigInteger, nullable=False, default=0)
    adjustment_reason_codes = Column(JSONB, nullable=True)
    match_status = Column(String(30), nullable=False, default=RemittanceLineMatchStatus.UNMATCHED.value)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    remittance = relationship("Remittance", back_populates="lines")
    claim = relationship("Claim", back_populates="remittance_lines")
    claim_line = relationship("ClaimLine", back_populates="remittance_lines")

    __table_args__ = (
        Index("idx_remittance_lines_remittance", "remittance_id"),
        Index("idx_remittance_lines_claim", "claim_id"),
        Index("idx_remittance_lines_match", "match_status"),
    )
