from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Dict, FrozenSet, Optional

from sqlmodel import Field, SQLModel


class ClaimStatus(str, Enum):
    submitted = "submitted"
    underwriting = "underwriting"
    funded = "funded"
    settled = "settled"
    reimbursed = "reimbursed"
    exception = "exception"


CLAIM_STATUS_TRANSITIONS: Dict[ClaimStatus, FrozenSet[ClaimStatus]] = {
    ClaimStatus.submitted: frozenset({ClaimStatus.underwriting, ClaimStatus.exception}),
    ClaimStatus.underwriting: frozenset({ClaimStatus.funded, ClaimStatus.exception}),
    ClaimStatus.funded: frozenset({ClaimStatus.reimbursed, ClaimStatus.exception, ClaimStatus.settled}),
    ClaimStatus.settled: frozenset(),
    ClaimStatus.reimbursed: frozenset(),
    ClaimStatus.exception: frozenset(),
}

TERMINAL_STATUSES: FrozenSet[ClaimStatus] = frozenset({
    ClaimStatus.settled,
    ClaimStatus.reimbursed,
    ClaimStatus.exception,
})


class InvalidStatusTransitionError(Exception):
    def __init__(self, current_status: ClaimStatus, target_status: ClaimStatus, message: str):
        self.current_status = current_status
        self.target_status = target_status
        self.message = message
        super().__init__(message)


def validate_status_transition(current_status: ClaimStatus, target_status: ClaimStatus) -> None:
    if current_status == target_status:
        raise InvalidStatusTransitionError(
            current_status,
            target_status,
            f"Claim is already in '{current_status.value}' status."
        )

    if current_status in TERMINAL_STATUSES:
        raise InvalidStatusTransitionError(
            current_status,
            target_status,
            f"Cannot transition from '{current_status.value}'. Claim lifecycle is complete."
        )

    valid_targets = CLAIM_STATUS_TRANSITIONS.get(current_status, frozenset())
    if target_status not in valid_targets:
        valid_list = ", ".join(f"'{s.value}'" for s in valid_targets) if valid_targets else "none"
        raise InvalidStatusTransitionError(
            current_status,
            target_status,
            f"Cannot transition from '{current_status.value}' to '{target_status.value}'. "
            f"Valid transitions from '{current_status.value}': {valid_list}."
        )


def can_transition(current_status: ClaimStatus, target_status: ClaimStatus) -> bool:
    if current_status == target_status:
        return False
    if current_status in TERMINAL_STATUSES:
        return False
    valid_targets = CLAIM_STATUS_TRANSITIONS.get(current_status, frozenset())
    return target_status in valid_targets


def get_valid_transitions(current_status: ClaimStatus) -> FrozenSet[ClaimStatus]:
    return CLAIM_STATUS_TRANSITIONS.get(current_status, frozenset())


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
