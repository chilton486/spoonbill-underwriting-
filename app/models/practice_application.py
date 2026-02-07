from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class ApplicationStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    NEEDS_INFO = "NEEDS_INFO"


class PracticeType(str, Enum):
    GENERAL_DENTISTRY = "GENERAL_DENTISTRY"
    PEDIATRIC_DENTISTRY = "PEDIATRIC_DENTISTRY"
    ORTHODONTICS = "ORTHODONTICS"
    PERIODONTICS = "PERIODONTICS"
    ENDODONTICS = "ENDODONTICS"
    ORAL_SURGERY = "ORAL_SURGERY"
    PROSTHODONTICS = "PROSTHODONTICS"
    MULTI_SPECIALTY = "MULTI_SPECIALTY"
    OTHER = "OTHER"


class BillingModel(str, Enum):
    IN_HOUSE = "IN_HOUSE"
    OUTSOURCED = "OUTSOURCED"
    HYBRID = "HYBRID"


class UrgencyLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PracticeApplication(Base):
    __tablename__ = "practice_applications"

    id = Column(Integer, primary_key=True, index=True)
    
    # Practice Information
    legal_name = Column(String(255), nullable=False)
    address = Column(Text, nullable=False)
    phone = Column(String(50), nullable=False)
    website = Column(String(255), nullable=True)
    tax_id = Column(String(50), nullable=True)
    practice_type = Column(String(50), nullable=False)
    
    # Practice Size & Operations
    years_in_operation = Column(Integer, nullable=False)
    provider_count = Column(Integer, nullable=False)
    operatory_count = Column(Integer, nullable=False)
    
    # Financial Information
    avg_monthly_collections_range = Column(String(100), nullable=False)
    insurance_vs_self_pay_mix = Column(String(100), nullable=False)
    top_payers = Column(Text, nullable=True)
    avg_ar_days = Column(Integer, nullable=True)
    
    # Billing Operations
    billing_model = Column(String(50), nullable=False)
    follow_up_frequency = Column(String(100), nullable=True)
    practice_management_software = Column(String(100), nullable=True)
    claims_per_month = Column(Integer, nullable=True)
    electronic_claims = Column(Boolean, nullable=True, default=True)
    
    # Application Details
    stated_goal = Column(Text, nullable=True)
    urgency_level = Column(String(50), nullable=False, default=UrgencyLevel.MEDIUM.value)
    
    # Contact Information (for initial manager invite)
    contact_name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=False, index=True)
    contact_phone = Column(String(50), nullable=True)
    
    # Status & Tracking
    status = Column(String(50), nullable=False, default=ApplicationStatus.SUBMITTED.value, index=True)
    review_notes = Column(Text, nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Relationships
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])
    
    # Link to created practice (set on approval)
    created_practice_id = Column(Integer, ForeignKey("practices.id"), nullable=True)
    created_practice = relationship("Practice", foreign_keys=[created_practice_id])
