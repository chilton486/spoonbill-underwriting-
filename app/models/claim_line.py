"""ClaimLine model - represents line-item procedures on a claim."""
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, BigInteger, ForeignKey, Index
from sqlalchemy.orm import relationship

from ..database import Base


class ClaimLineStatus(str, Enum):
    PENDING = "PENDING"
    ADJUDICATED = "ADJUDICATED"
    DENIED = "DENIED"
    PARTIAL = "PARTIAL"


class ClaimLine(Base):
    __tablename__ = "claim_lines"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    procedure_code_id = Column(Integer, ForeignKey("procedure_codes.id"), nullable=True, index=True)
    provider_id = Column(Integer, ForeignKey("providers.id"), nullable=True, index=True)

    cdt_code = Column(String(10), nullable=True)  # denormalized for convenience
    tooth = Column(String(10), nullable=True)
    surface = Column(String(20), nullable=True)
    quadrant = Column(String(10), nullable=True)
    modifier = Column(String(50), nullable=True)

    billed_fee_cents = Column(BigInteger, nullable=False, default=0)
    allowed_fee_cents = Column(BigInteger, nullable=True)
    units = Column(Integer, nullable=False, default=1)
    line_status = Column(String(30), nullable=True, default=ClaimLineStatus.PENDING.value)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    claim = relationship("Claim", back_populates="claim_lines")
    procedure_code = relationship("ProcedureCode", back_populates="claim_lines")
    provider = relationship("Provider", back_populates="claim_lines")
    remittance_lines = relationship("RemittanceLine", back_populates="claim_line")

    __table_args__ = (
        Index("idx_claim_lines_claim", "claim_id"),
        Index("idx_claim_lines_procedure", "procedure_code_id"),
    )
