import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator


class TopPayerEntry(BaseModel):
    name: str = Field(..., max_length=100)
    pct_revenue: float = Field(..., ge=0, le=100)


class PracticeApplicationCreate(BaseModel):
    legal_name: str = Field(..., min_length=1, max_length=255)
    dba: Optional[str] = Field(None, max_length=255)
    ein: Optional[str] = Field(None, max_length=20)
    npi_individual: Optional[str] = Field(None, max_length=20)
    npi_group: Optional[str] = Field(None, max_length=20)
    years_in_operation: int = Field(..., ge=0, le=200)
    ownership_structure: Optional[str] = Field(None, max_length=50)
    prior_bankruptcy: Optional[bool] = False
    pending_litigation: Optional[bool] = False

    gross_production_cents: Optional[int] = Field(None, ge=0)
    net_collections_cents: Optional[int] = Field(None, ge=0)
    insurance_collections_cents: Optional[int] = Field(None, ge=0)
    patient_collections_cents: Optional[int] = Field(None, ge=0)
    seasonality_swings: Optional[bool] = False

    top_payers_json: Optional[str] = None
    pct_ppo: Optional[float] = Field(None, ge=0, le=100)
    pct_medicaid: Optional[float] = Field(None, ge=0, le=100)
    pct_ffs: Optional[float] = Field(None, ge=0, le=100)
    pct_capitation: Optional[float] = Field(None, ge=0, le=100)
    avg_claim_size_cents: Optional[int] = Field(None, ge=0)
    avg_monthly_claim_count: Optional[int] = Field(None, ge=0)
    avg_days_to_reimbursement: Optional[int] = Field(None, ge=0, le=365)
    estimated_denial_rate: Optional[float] = Field(None, ge=0, le=100)

    practice_management_software: Optional[str] = Field(None, max_length=100)
    billing_model: Optional[str] = Field("IN_HOUSE", max_length=50)
    billing_staff_count: Optional[int] = Field(None, ge=0)
    dedicated_rcm_manager: Optional[bool] = False
    written_billing_sop: Optional[bool] = False
    avg_ar_days: Optional[int] = Field(None, ge=0, le=365)
    outstanding_ar_balance_cents: Optional[int] = Field(None, ge=0)

    primary_bank: Optional[str] = Field(None, max_length=255)
    cash_on_hand_range: Optional[str] = Field(None, max_length=50)
    existing_loc_cents: Optional[int] = Field(None, ge=0)
    monthly_debt_payments_cents: Optional[int] = Field(None, ge=0)
    missed_loan_payments_24m: Optional[bool] = False

    desired_funding_cadence: Optional[str] = Field(None, max_length=50)
    expected_monthly_funding_cents: Optional[int] = Field(None, ge=0)
    urgency_scale: Optional[int] = Field(None, ge=1, le=5)
    willing_to_integrate_api: Optional[bool] = False
    why_spoonbill: Optional[str] = Field(None, max_length=2000)

    contact_name: str = Field(..., min_length=1, max_length=255)
    contact_email: EmailStr
    contact_phone: Optional[str] = Field(None, max_length=50)

    company_url: Optional[str] = Field(None, max_length=255)

    @field_validator('contact_phone')
    @classmethod
    def validate_contact_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = re.sub(r'[\s\-\.\(\)]+', '', v)
        if not re.match(r'^\+?\d{7,15}$', cleaned):
            raise ValueError('Invalid phone number format.')
        return v

    class Config:
        from_attributes = True


class PracticeApplicationResponse(BaseModel):
    id: int
    legal_name: str
    dba: Optional[str] = None
    ein: Optional[str] = None
    npi_individual: Optional[str] = None
    npi_group: Optional[str] = None
    years_in_operation: int
    ownership_structure: Optional[str] = None
    prior_bankruptcy: Optional[bool] = None
    pending_litigation: Optional[bool] = None

    gross_production_cents: Optional[int] = None
    net_collections_cents: Optional[int] = None
    insurance_collections_cents: Optional[int] = None
    patient_collections_cents: Optional[int] = None
    seasonality_swings: Optional[bool] = None

    top_payers_json: Optional[str] = None
    pct_ppo: Optional[float] = None
    pct_medicaid: Optional[float] = None
    pct_ffs: Optional[float] = None
    pct_capitation: Optional[float] = None
    avg_claim_size_cents: Optional[int] = None
    avg_monthly_claim_count: Optional[int] = None
    avg_days_to_reimbursement: Optional[int] = None
    estimated_denial_rate: Optional[float] = None

    practice_management_software: Optional[str] = None
    billing_model: Optional[str] = None
    billing_staff_count: Optional[int] = None
    dedicated_rcm_manager: Optional[bool] = None
    written_billing_sop: Optional[bool] = None
    avg_ar_days: Optional[int] = None
    outstanding_ar_balance_cents: Optional[int] = None

    primary_bank: Optional[str] = None
    cash_on_hand_range: Optional[str] = None
    existing_loc_cents: Optional[int] = None
    monthly_debt_payments_cents: Optional[int] = None
    missed_loan_payments_24m: Optional[bool] = None

    desired_funding_cadence: Optional[str] = None
    expected_monthly_funding_cents: Optional[int] = None
    urgency_scale: Optional[int] = None
    willing_to_integrate_api: Optional[bool] = None
    why_spoonbill: Optional[str] = None

    contact_name: str
    contact_email: str
    contact_phone: Optional[str] = None

    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    tax_id: Optional[str] = None
    practice_type: Optional[str] = None
    provider_count: Optional[int] = None
    operatory_count: Optional[int] = None
    avg_monthly_collections_range: Optional[str] = None
    insurance_vs_self_pay_mix: Optional[str] = None
    top_payers: Optional[str] = None
    follow_up_frequency: Optional[str] = None
    claims_per_month: Optional[int] = None
    electronic_claims: Optional[bool] = None
    stated_goal: Optional[str] = None
    urgency_level: Optional[str] = None

    status: str
    review_notes: Optional[str] = None
    reviewed_by_user_id: Optional[int] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    created_practice_id: Optional[int] = None

    underwriting_score: Optional[float] = None
    underwriting_grade: Optional[str] = None
    underwriting_breakdown_json: Optional[str] = None

    class Config:
        from_attributes = True


class PracticeApplicationListResponse(BaseModel):
    id: int
    legal_name: str
    practice_type: Optional[str] = None
    contact_name: str
    contact_email: str
    status: str
    urgency_level: Optional[str] = None
    urgency_scale: Optional[int] = None
    underwriting_score: Optional[float] = None
    underwriting_grade: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApplicationReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|DECLINE|NEEDS_INFO)$")
    review_notes: Optional[str] = None


class ApplicationApprovalResult(BaseModel):
    application_id: int
    practice_id: int
    manager_user_id: int
    manager_email: str
    invite_token: str
    invite_url: str
    message: str


class ApplicationSubmissionResponse(BaseModel):
    id: int
    status: str
    message: str


class UnderwritingScoreOverride(BaseModel):
    score: float = Field(..., ge=0, le=100)
    grade: str = Field(..., pattern="^(GREEN|YELLOW|RED)$")
    reason: str = Field(..., min_length=1, max_length=500)
