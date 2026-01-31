from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from .models import (
    CapitalPool,
    Claim,
    ClaimStatus,
    InvalidStatusTransitionError,
    Practice,
    validate_status_transition,
)


class LedgerError(Exception):
    pass


def get_remaining_practice_exposure_limit(*, practice: Practice) -> int:
    remaining = practice.max_exposure_limit - practice.current_exposure
    return max(0, remaining)


def fund_claim_atomic(*, session: Session, pool_id: str, claim_id: str, funded_amount: int) -> None:
    pool = session.exec(select(CapitalPool).where(CapitalPool.id == pool_id)).one()
    claim = session.exec(select(Claim).where(Claim.claim_id == claim_id)).one()
    practice = session.exec(select(Practice).where(Practice.id == claim.practice_id)).one()

    try:
        validate_status_transition(claim.status, ClaimStatus.funded)
    except InvalidStatusTransitionError as e:
        raise LedgerError(f"Claim {claim.claim_id}: {e.message}") from e

    remaining = get_remaining_practice_exposure_limit(practice=practice)
    if funded_amount > remaining:
        raise LedgerError("Insufficient remaining practice exposure limit")

    if funded_amount > pool.available_capital:
        raise LedgerError("Insufficient pool available capital")

    # Financial invariants:
    # - Available capital decreases immediately when we advance funds.
    # - Allocated/pending increase while we wait for settlement.
    # - Practice exposure tracks principal at risk (not profit).
    pool.available_capital -= funded_amount
    pool.capital_allocated += funded_amount
    pool.capital_pending_settlement += funded_amount

    practice.current_exposure += funded_amount

    claim.funded_amount = funded_amount
    claim.status = ClaimStatus.funded
    claim.decline_reason_code = None

    session.add(pool)
    session.add(practice)
    session.add(claim)


def settle_claim_atomic(
    *,
    session: Session,
    pool_id: str,
    claim_id: str,
    settlement_date: date,
    settlement_amount: int,
) -> None:
    pool = session.exec(select(CapitalPool).where(CapitalPool.id == pool_id)).one()
    claim = session.exec(select(Claim).where(Claim.claim_id == claim_id)).one()
    practice = session.exec(select(Practice).where(Practice.id == claim.practice_id)).one()

    target_status = ClaimStatus.exception if settlement_amount < claim.funded_amount else ClaimStatus.reimbursed
    try:
        validate_status_transition(claim.status, target_status)
    except InvalidStatusTransitionError as e:
        raise LedgerError(f"Claim {claim.claim_id}: {e.message}") from e

    principal = claim.funded_amount

    if principal > pool.capital_pending_settlement:
        raise LedgerError("Pool pending settlement invariant violated")

    # Duration metric: days between submission and settlement.
    days_outstanding = max(0, (settlement_date - claim.submission_date).days)
    pool.total_days_outstanding += days_outstanding
    pool.num_settled_claims += 1

    # V1: treat any settlement_amount < principal as an exception scenario.
    # We do not chase denials; we only reconcile and record outcomes.
    if settlement_amount < principal:
        claim.status = ClaimStatus.exception
    else:
        claim.status = ClaimStatus.reimbursed

    pool.capital_pending_settlement -= principal
    pool.capital_allocated -= principal

    # Capital returned is capped at principal for V1 accounting.
    # Any excess (interest/fees) is out of scope for this foundational engine.
    returned_principal = min(principal, settlement_amount)
    pool.available_capital += returned_principal
    pool.capital_returned += returned_principal

    practice.current_exposure -= principal
    if practice.current_exposure < 0:
        raise LedgerError("Practice exposure invariant violated")

    session.add(pool)
    session.add(practice)
    session.add(claim)
