from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, field_validator


class ExternalClaimLine(BaseModel):
    external_line_id: str
    cdt_code: str
    description: Optional[str] = None
    line_amount_cents: int
    tooth_number: Optional[str] = None
    surface: Optional[str] = None

    @field_validator("line_amount_cents")
    @classmethod
    def amount_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("line_amount_cents must be positive")
        return v


class ExternalClaim(BaseModel):
    external_claim_id: str
    external_patient_id: Optional[str] = None
    payer: str
    total_billed_cents: int
    procedure_date: Optional[date] = None
    submitted_date: Optional[date] = None
    procedure_codes: Optional[str] = None
    lines: List[ExternalClaimLine] = []

    @field_validator("payer")
    @classmethod
    def payer_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("payer cannot be empty")
        return v.strip()

    @field_validator("total_billed_cents")
    @classmethod
    def amount_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("total_billed_cents must be positive")
        return v


class IngestionSummary(BaseModel):
    total_received: int
    created: int
    updated: int
    skipped: int
    errors: List[str] = []


class IntegrationConnectionResponse(BaseModel):
    id: int
    practice_id: int
    provider: str
    status: str
    last_cursor: Optional[str]
    last_synced_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IntegrationSyncRunResponse(BaseModel):
    id: int
    connection_id: int
    practice_id: int
    provider: str
    started_at: datetime
    ended_at: Optional[datetime]
    status: str
    pulled_count: int
    upserted_count: int
    error_json: Optional[str]
    sync_type: str

    class Config:
        from_attributes = True


class IntegrationStatusResponse(BaseModel):
    connected: bool
    provider: Optional[str] = None
    status: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    last_cursor: Optional[str] = None
    recent_runs: List[IntegrationSyncRunResponse] = []


class CSVUploadResponse(BaseModel):
    sync_run_id: int
    summary: IngestionSummary
