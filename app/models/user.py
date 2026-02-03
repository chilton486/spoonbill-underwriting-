from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship

from ..database import Base


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPS = "OPS"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default=UserRole.OPS.value)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    audit_events = relationship("AuditEvent", back_populates="actor")
    underwriting_decisions = relationship("UnderwritingDecision", back_populates="decided_by_user")
