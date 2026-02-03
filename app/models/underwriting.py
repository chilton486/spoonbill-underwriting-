from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from ..database import Base


class DecisionType(str, Enum):
    APPROVE = "APPROVE"
    DECLINE = "DECLINE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class UnderwritingDecision(Base):
    __tablename__ = "underwriting_decisions"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    decision = Column(String(50), nullable=False)
    reasons = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    claim = relationship("Claim", back_populates="underwriting_decisions")
    decided_by_user = relationship("User", back_populates="underwriting_decisions")
