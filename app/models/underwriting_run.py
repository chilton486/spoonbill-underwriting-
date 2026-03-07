"""UnderwritingRun model - persistence for LLM-assisted underwriting intelligence.

Every cognitive underwriting call creates an UnderwritingRun record for full
auditability: model name, prompt version, input hash, structured output,
latency, fallback status, and merged recommendation.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from ..database import Base


class UnderwritingRun(Base):
    __tablename__ = "underwriting_runs"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False, index=True)

    # Model/provider info
    model_provider = Column(String(50), nullable=False, default="anthropic")
    model_name = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)

    # Input audit
    input_hash = Column(String(64), nullable=True)
    input_snapshot_json = Column(JSONB, nullable=True)  # optional full input snapshot

    # Output
    output_json = Column(JSONB, nullable=True)
    raw_response = Column(Text, nullable=True)  # raw model response for debugging

    # Decision fields
    recommendation = Column(String(50), nullable=True)  # model recommendation
    risk_score = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)

    # Merge result
    deterministic_recommendation = Column(String(50), nullable=True)
    merged_recommendation = Column(String(50), nullable=True)  # final after merge

    # Run metadata
    run_type = Column(String(50), nullable=False, default="underwrite_claim")  # underwrite_claim, parse_eob, ontology_updates
    latency_ms = Column(Integer, nullable=True)
    fallback_used = Column(Boolean, nullable=False, default=False)
    fallback_reason = Column(Text, nullable=True)
    parse_success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)

    # Review
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer_override = Column(String(50), nullable=True)
    reviewer_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    claim = relationship("Claim", backref="underwriting_runs")
    practice = relationship("Practice")
    reviewer = relationship("User", foreign_keys=[reviewer_user_id])

    __table_args__ = (
        Index("idx_uw_runs_claim_id", "claim_id"),
        Index("idx_uw_runs_practice_id", "practice_id"),
        Index("idx_uw_runs_run_type", "run_type"),
        Index("idx_uw_runs_created_at", "created_at"),
    )
