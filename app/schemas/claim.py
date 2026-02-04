from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, field_validator



class ClaimCreate(BaseModel):
    practice_id: Optional[str] = None
    patient_name: Optional[str] = None
    payer: str
    amount_cents: int
    procedure_date: Optional[date] = None
    external_claim_id: Optional[str] = None
    procedure_codes: Optional[str] = None

    @field_validator("payer")
    @classmethod
    def payer_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("payer cannot be empty")
        return v.strip()

    @field_validator("amount_cents")
    @classmethod
    def amount_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount_cents must be positive")
        return v


class ClaimUpdate(BaseModel):
    practice_id: Optional[str] = None
    patient_name: Optional[str] = None
    payer: Optional[str] = None
    amount_cents: Optional[int] = None
    procedure_date: Optional[date] = None
    procedure_codes: Optional[str] = None


class UnderwritingDecisionResponse(BaseModel):
    id: int
    decision: str
    reasons: Optional[str]
    decided_at: datetime
    decided_by: Optional[int]

    class Config:
        from_attributes = True


class AuditEventResponse(BaseModel):
    id: int
    action: str
    from_status: Optional[str]
    to_status: Optional[str]
    metadata_json: Optional[str]
    created_at: datetime
    actor_user_id: Optional[int]

    class Config:
        from_attributes = True


class ClaimResponse(BaseModel):
    id: int
    practice_id: Optional[str]
    patient_name: Optional[str]
    payer: str
    amount_cents: int
    procedure_date: Optional[date]
    status: str
    fingerprint: Optional[str]
    external_claim_id: Optional[str]
    procedure_codes: Optional[str]
    created_at: datetime
    updated_at: datetime
    underwriting_decisions: List[UnderwritingDecisionResponse] = []
    audit_events: List[AuditEventResponse] = []

    class Config:
        from_attributes = True


class ClaimListResponse(BaseModel):
    id: int
    practice_id: Optional[str]
    patient_name: Optional[str]
    payer: str
    amount_cents: int
    procedure_date: Optional[date]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClaimTransitionRequest(BaseModel):
    to_status: str
    reason: Optional[str] = None
