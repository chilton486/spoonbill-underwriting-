from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class ClaimStatus(str, Enum):
    submitted = "submitted"
    underwriting = "underwriting"
    funded = "funded"
    settled = "settled"
    reimbursed = "reimbursed"
    exception = "exception"


class AdjudicationStatus(str, Enum):
    unknown = "unknown"
    approved = "approved"
    denied = "denied"
    pending = "pending"


class Practice(SQLModel, table=True):
    id: str = Field(primary_key=True)

    # Underwriting inputs
    tenure_months: int
    historical_clean_claim_rate: float

    # Stored as a simple string blob in V1 (e.g., "Aetna:0.4;UHC:0.3;BCBS:0.3")
    # Keep minimal and auditable; normalize later if needed.
    payer_mix: str

    # Risk controls
    max_exposure_limit: int
    current_exposure: int = 0


class Claim(SQLModel, table=True):
    claim_id: str = Field(primary_key=True)
    practice_id: str = Field(index=True)

    payer: str
    procedure_code: str

    billed_amount: int
    expected_allowed_amount: int

    submission_date: date
    adjudication_status: AdjudicationStatus = AdjudicationStatus.unknown

    # Deterministic underwriting can still produce a score field for later analysis,
    # but V1 decisions must be rules-only.
    underwriting_confidence_score: float = 0.0

    funded_amount: int = 0
    status: ClaimStatus = ClaimStatus.submitted

    decline_reason_code: Optional[str] = None


class CapitalPool(SQLModel, table=True):
    id: str = Field(primary_key=True)

    total_capital: int
    available_capital: int

    capital_allocated: int = 0
    capital_pending_settlement: int = 0
    capital_returned: int = 0

    # Duration tracking (simple rolling totals for V1)
    total_days_outstanding: int = 0
    num_settled_claims: int = 0
