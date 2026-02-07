from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class UserRole(str, Enum):
    SPOONBILL_ADMIN = "SPOONBILL_ADMIN"
    SPOONBILL_OPS = "SPOONBILL_OPS"
    PRACTICE_MANAGER = "PRACTICE_MANAGER"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default=UserRole.SPOONBILL_OPS.value)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    practice = relationship("Practice", back_populates="users")
    audit_events = relationship("AuditEvent", back_populates="actor")
    underwriting_decisions = relationship("UnderwritingDecision", back_populates="decided_by_user")
    uploaded_documents = relationship("ClaimDocument", back_populates="uploaded_by")
    invites = relationship("PracticeManagerInvite", back_populates="user")
