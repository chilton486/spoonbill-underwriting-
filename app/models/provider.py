"""Provider model - represents rendering/billing clinicians within a practice."""
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship

from ..database import Base


class ProviderRole(str, Enum):
    OWNER = "OWNER"
    ASSOCIATE = "ASSOCIATE"
    HYGIENIST = "HYGIENIST"
    SPECIALIST = "SPECIALIST"
    OTHER = "OTHER"


class Provider(Base):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False, index=True)

    full_name = Column(String(255), nullable=False)
    npi = Column(String(20), nullable=True, index=True)
    specialty = Column(String(100), nullable=True)
    role = Column(String(50), nullable=False, default=ProviderRole.ASSOCIATE.value)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    practice = relationship("Practice", back_populates="providers")
    claim_lines = relationship("ClaimLine", back_populates="provider")

    __table_args__ = (
        Index("idx_providers_practice_active", "practice_id", "is_active"),
    )
