from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from app.models.practice_application import PracticeType, BillingModel, UrgencyLevel


class PracticeApplicationCreate(BaseModel):
    """Schema for public intake form submission - no auth required."""
    
    # Practice Information
    legal_name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(..., min_length=1)
    phone: str = Field(..., min_length=1, max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    practice_type: PracticeType
    
    # Practice Size & Operations
    years_in_operation: int = Field(..., ge=0)
    provider_count: int = Field(..., ge=1)
    operatory_count: int = Field(..., ge=1)
    
    # Financial Information
    avg_monthly_collections_range: str = Field(..., max_length=100)
    insurance_vs_self_pay_mix: str = Field(..., max_length=100)
    top_payers: Optional[str] = None
    avg_ar_days: Optional[int] = Field(None, ge=0)
    
    # Billing Operations
    billing_model: BillingModel
    follow_up_frequency: Optional[str] = Field(None, max_length=100)
    practice_management_software: Optional[str] = Field(None, max_length=100)
    claims_per_month: Optional[int] = Field(None, ge=0)
    electronic_claims: Optional[bool] = True
    
    # Application Details
    stated_goal: Optional[str] = None
    urgency_level: UrgencyLevel = UrgencyLevel.MEDIUM
    
    # Contact Information (for initial manager invite)
    contact_name: str = Field(..., min_length=1, max_length=255)
    contact_email: EmailStr
    contact_phone: Optional[str] = Field(None, max_length=50)

    class Config:
        from_attributes = True


class PracticeApplicationResponse(BaseModel):
    """Response schema for practice application."""
    
    id: int
    legal_name: str
    address: str
    phone: str
    website: Optional[str]
    tax_id: Optional[str]
    practice_type: str
    
    years_in_operation: int
    provider_count: int
    operatory_count: int
    
    avg_monthly_collections_range: str
    insurance_vs_self_pay_mix: str
    top_payers: Optional[str]
    avg_ar_days: Optional[int]
    
    billing_model: str
    follow_up_frequency: Optional[str]
    practice_management_software: Optional[str]
    claims_per_month: Optional[int]
    electronic_claims: Optional[bool]
    
    stated_goal: Optional[str]
    urgency_level: str
    
    contact_name: str
    contact_email: str
    contact_phone: Optional[str]
    
    status: str
    review_notes: Optional[str]
    reviewed_by_user_id: Optional[int]
    created_at: datetime
    reviewed_at: Optional[datetime]
    created_practice_id: Optional[int]

    class Config:
        from_attributes = True


class PracticeApplicationListResponse(BaseModel):
    """Simplified response for list views."""
    
    id: int
    legal_name: str
    practice_type: str
    contact_name: str
    contact_email: str
    status: str
    urgency_level: str
    created_at: datetime
    reviewed_at: Optional[datetime]

    class Config:
        from_attributes = True


class ApplicationReviewRequest(BaseModel):
    """Schema for Ops review actions."""
    
    action: str = Field(..., pattern="^(APPROVE|DECLINE|NEEDS_INFO)$")
    review_notes: Optional[str] = None


class ApplicationApprovalResult(BaseModel):
    """Response after approving an application."""
    
    application_id: int
    practice_id: int
    manager_user_id: int
    manager_email: str
    temporary_password: str
    message: str


class ApplicationSubmissionResponse(BaseModel):
    """Response after submitting an application."""
    
    id: int
    status: str
    message: str
