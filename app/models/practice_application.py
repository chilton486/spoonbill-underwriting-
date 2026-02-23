from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float, ForeignKey
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


class OwnershipStructure(str, Enum):
    SOLE_PROPRIETOR = "SOLE_PROPRIETOR"
    PARTNERSHIP = "PARTNERSHIP"
    LLC = "LLC"
    S_CORP = "S_CORP"
    C_CORP = "C_CORP"
    DSO_AFFILIATED = "DSO_AFFILIATED"
    OTHER = "OTHER"


class CashOnHandRange(str, Enum):
    UNDER_25K = "UNDER_25K"
    R_25K_50K = "25K_50K"
    R_50K_100K = "50K_100K"
    R_100K_250K = "100K_250K"
    R_250K_500K = "250K_500K"
    OVER_500K = "OVER_500K"


class FundingCadence(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"


class UnderwritingGrade(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class PracticeApplication(Base):
    __tablename__ = "practice_applications"

    id = Column(Integer, primary_key=True, index=True)

    # Step 1: Practice Identity & Compliance
    legal_name = Column(String(255), nullable=False)
    dba = Column(String(255), nullable=True)
    ein = Column(String(20), nullable=True)
    npi_individual = Column(String(20), nullable=True)
    npi_group = Column(String(20), nullable=True)
    years_in_operation = Column(Integer, nullable=False)
    ownership_structure = Column(String(50), nullable=True)
    prior_bankruptcy = Column(Boolean, nullable=True, default=False)
    pending_litigation = Column(Boolean, nullable=True, default=False)

    # Step 2: Revenue & Production (Last 12 months)
    gross_production_cents = Column(Integer, nullable=True)
    net_collections_cents = Column(Integer, nullable=True)
    insurance_collections_cents = Column(Integer, nullable=True)
    patient_collections_cents = Column(Integer, nullable=True)
    seasonality_swings = Column(Boolean, nullable=True, default=False)

    # Step 3: Payer & Claims Profile
    top_payers_json = Column(Text, nullable=True)
    pct_ppo = Column(Float, nullable=True)
    pct_medicaid = Column(Float, nullable=True)
    pct_ffs = Column(Float, nullable=True)
    pct_capitation = Column(Float, nullable=True)
    avg_claim_size_cents = Column(Integer, nullable=True)
    avg_monthly_claim_count = Column(Integer, nullable=True)
    avg_days_to_reimbursement = Column(Integer, nullable=True)
    estimated_denial_rate = Column(Float, nullable=True)

    # Step 4: Billing Operations
    practice_management_software = Column(String(100), nullable=True)
    billing_model = Column(String(50), nullable=False, default=BillingModel.IN_HOUSE.value)
    billing_staff_count = Column(Integer, nullable=True)
    dedicated_rcm_manager = Column(Boolean, nullable=True, default=False)
    written_billing_sop = Column(Boolean, nullable=True, default=False)
    avg_ar_days = Column(Integer, nullable=True)
    outstanding_ar_balance_cents = Column(Integer, nullable=True)

    # Step 5: Financial Stability
    primary_bank = Column(String(255), nullable=True)
    cash_on_hand_range = Column(String(50), nullable=True)
    existing_loc_cents = Column(Integer, nullable=True)
    monthly_debt_payments_cents = Column(Integer, nullable=True)
    missed_loan_payments_24m = Column(Boolean, nullable=True, default=False)

    # Step 6: Spoonbill Fit
    desired_funding_cadence = Column(String(50), nullable=True)
    expected_monthly_funding_cents = Column(Integer, nullable=True)
    urgency_scale = Column(Integer, nullable=True)
    willing_to_integrate_api = Column(Boolean, nullable=True, default=False)
    why_spoonbill = Column(Text, nullable=True)

    # Legacy fields (kept for backward compat with existing apps)
    address = Column(Text, nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    tax_id = Column(String(50), nullable=True)
    practice_type = Column(String(50), nullable=True)
    provider_count = Column(Integer, nullable=True)
    operatory_count = Column(Integer, nullable=True)
    avg_monthly_collections_range = Column(String(100), nullable=True)
    insurance_vs_self_pay_mix = Column(String(100), nullable=True)
    top_payers = Column(Text, nullable=True)
    follow_up_frequency = Column(String(100), nullable=True)
    claims_per_month = Column(Integer, nullable=True)
    electronic_claims = Column(Boolean, nullable=True, default=True)
    stated_goal = Column(Text, nullable=True)
    urgency_level = Column(String(50), nullable=True, default=UrgencyLevel.MEDIUM.value)

    # Contact Information
    contact_name = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=False, index=True)
    contact_phone = Column(String(50), nullable=True)

    # Status & Tracking
    status = Column(String(50), nullable=False, default=ApplicationStatus.SUBMITTED.value, index=True)
    review_notes = Column(Text, nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Underwriting Score
    underwriting_score = Column(Float, nullable=True)
    underwriting_grade = Column(String(20), nullable=True)
    underwriting_breakdown_json = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)

    # Relationships
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])

    # Link to created practice (set on approval)
    created_practice_id = Column(Integer, ForeignKey("practices.id"), nullable=True)
    created_practice = relationship("Practice", foreign_keys=[created_practice_id])
