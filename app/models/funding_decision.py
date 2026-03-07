"""FundingDecision model - represents Spoonbill underwriting output for a claim.

This is the ontology-first replacement for the simpler UnderwritingDecision.
UnderwritingDecision is kept for backward compatibility; FundingDecision adds
risk scoring, advance rates, model versioning, and structured reasons.
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Float, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from ..database import Base


class FundingDecisionType(str, Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class FundingDecision(Base):
    __tablename__ = "funding_decisions"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)

    decision = Column(String(50), nullable=False)
    advance_rate = Column(Float, nullable=True)  # e.g. 0.85 = 85% of billed
    max_advance_amount_cents = Column(BigInteger, nullable=True)
    fee_rate = Column(Float, nullable=True)  # e.g. 0.03 = 3% fee
    required_docs_flags = Column(JSONB, nullable=True)
    risk_score = Column(Float, nullable=True)  # 0.0 - 1.0
    reasons_json = Column(JSONB, nullable=True)
    decisioned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    decisioned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    model_version = Column(String(50), nullable=True)  # e.g. "synthetic-v1"
    policy_version = Column(String(50), nullable=True)  # e.g. "rules-v1"

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    claim = relationship("Claim", back_populates="funding_decisions")
    decisioned_by_user = relationship("User")

    __table_args__ = (
        Index("idx_funding_decisions_claim", "claim_id"),
        Index("idx_funding_decisions_decision", "decision"),
    )
