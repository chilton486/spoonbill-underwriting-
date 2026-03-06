"""ProcedureCode model - represents CDT procedure codes."""
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from ..database import Base


class ProcedureCategory(str, Enum):
    DIAGNOSTIC = "DIAGNOSTIC"
    PREVENTIVE = "PREVENTIVE"
    RESTORATIVE = "RESTORATIVE"
    ENDODONTICS = "ENDODONTICS"
    PERIODONTICS = "PERIODONTICS"
    PROSTHODONTICS = "PROSTHODONTICS"
    ORAL_SURGERY = "ORAL_SURGERY"
    ORTHODONTICS = "ORTHODONTICS"
    ADJUNCTIVE = "ADJUNCTIVE"
    IMPLANTS = "IMPLANTS"
    OTHER = "OTHER"


class ProcedureCode(Base):
    __tablename__ = "procedure_codes"

    id = Column(Integer, primary_key=True, index=True)
    cdt_code = Column(String(10), unique=True, nullable=False, index=True)
    short_description = Column(String(500), nullable=False)
    category = Column(String(50), nullable=False, default=ProcedureCategory.OTHER.value)
    documentation_requirements = Column(Text, nullable=True)
    common_denial_reasons = Column(JSONB, nullable=True)
    risk_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    claim_lines = relationship("ClaimLine", back_populates="procedure_code")

    __table_args__ = (
        Index("idx_procedure_codes_category", "category"),
    )
