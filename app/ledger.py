from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


class LedgerError(Exception):
    pass


class InvariantViolationError(LedgerError):
    pass


def check_pool_invariants(pool: CapitalPool) -> None:
    assert pool.available_capital >= 0, f"Available capital cannot be negative: {pool.available_capital}"
    assert pool.capital_allocated >= 0, f"Allocated capital cannot be negative: {pool.capital_allocated}"
    assert pool.capital_pending_settlement >= 0, f"Pending settlement cannot be negative: {pool.capital_pending_settlement}"
    assert pool.capital_returned >= 0, f"Returned capital cannot be negative: {pool.capital_returned}"

    expected_available = pool.total_capital - pool.capital_allocated + pool.capital_returned
    if pool.available_capital != expected_available:
        raise InvariantViolationError(
            f"Capital pool invariant violated: available_capital ({pool.available_capital}) != "
            f"total_capital ({pool.total_capital}) - capital_allocated ({pool.capital_allocated}) + "
            f"capital_returned ({pool.capital_returned}) = {expected_available}"
        )

    if pool.capital_pending_settlement > pool.capital_allocated:
        raise InvariantViolationError(
            f"Capital pool invariant violated: pending_settlement ({pool.capital_pending_settlement}) > "
            f"allocated ({pool.capital_allocated})"
        )

    logger.debug(
        "Pool invariants OK: pool_id=%s, available=%d, allocated=%d, pending=%d, returned=%d",
        pool.id, pool.available_capital, pool.capital_allocated,
        pool.capital_pending_settlement, pool.capital_returned
    )


def check_practice_invariants(practice: Practice) -> None:
    assert practice.current_exposure >= 0, f"Practice exposure cannot be negative: {practice.current_exposure}"
    assert practice.max_exposure_limit >= 0, f"Max exposure limit cannot be negative: {practice.max_exposure_limit}"

    if practice.current_exposure > practice.max_exposure_limit:
        raise InvariantViolationError(
            f"Practice invariant violated: current_exposure ({practice.current_exposure}) > "
            f"max_exposure_limit ({practice.max_exposure_limit}) for practice {practice.id}"
        )

    logger.debug(
        "Practice invariants OK: practice_id=%s, exposure=%d/%d",
        practice.id, practice.current_exposure, practice.max_exposure_limit
    )


def check_claim_invariants(claim: Claim) -> None:
    assert claim.billed_amount >= 0, f"Billed amount cannot be negative: {claim.billed_amount}"
    assert claim.expected_allowed_amount >= 0, f"Expected allowed amount cannot be negative: {claim.expected_allowed_amount}"
    assert claim.funded_amount >= 0, f"Funded amount cannot be negative: {claim.funded_amount}"

    if claim.status == ClaimStatus.funded and claim.funded_amount == 0:
        raise InvariantViolationError(
            f"Claim invariant violated: claim {claim.claim_id} is funded but funded_amount is 0"
        )

    if claim.status == ClaimStatus.submitted and claim.funded_amount > 0:
        raise InvariantViolationError(
            f"Claim invariant violated: claim {claim.claim_id} is submitted but has funded_amount {claim.funded_amount}"
        )

    logger.debug(
        "Claim invariants OK: claim_id=%s, status=%s, funded_amount=%d",
        claim.claim_id, claim.status.value, claim.funded_amount
    )


def get_remaining_practice_exposure_limit(*, practice: Practice) -> int:
    remaining = practice.max_exposure_limit - practice.current_exposure
    return max(0, remaining)


def fund_claim_atomic(*, session: Session, pool_id: str, claim_id: str, funded_amount: int) -> None:
    assert funded_amount > 0, f"Funded amount must be positive: {funded_amount}"

    logger.info(
        "Funding claim: claim_id=%s, pool_id=%s, funded_amount=%d",
        claim_id, pool_id, funded_amount
    )

    pool = session.exec(select(CapitalPool).where(CapitalPool.id == pool_id)).one()
    claim = session.exec(select(Claim).where(Claim.claim_id == claim_id)).one()
    practice = session.exec(select(Practice).where(Practice.id == claim.practice_id)).one()

    check_pool_invariants(pool)
    check_practice_invariants(practice)
    check_claim_invariants(claim)

    try:
        validate_status_transition(claim.status, ClaimStatus.funded)
    except InvalidStatusTransitionError as e:
        logger.warning(
            "Invalid status transition for claim %s: %s -> funded",
            claim_id, claim.status.value
        )
        raise LedgerError(f"Claim {claim.claim_id}: {e.message}") from e

    remaining = get_remaining_practice_exposure_limit(practice=practice)
    if funded_amount > remaining:
        logger.warning(
            "Insufficient practice exposure limit: claim_id=%s, requested=%d, remaining=%d",
            claim_id, funded_amount, remaining
        )
        raise LedgerError("Insufficient remaining practice exposure limit")

    if funded_amount > pool.available_capital:
        logger.warning(
            "Insufficient pool capital: claim_id=%s, requested=%d, available=%d",
            claim_id, funded_amount, pool.available_capital
        )
        raise LedgerError("Insufficient pool available capital")

    pool.available_capital -= funded_amount
    pool.capital_allocated += funded_amount
    pool.capital_pending_settlement += funded_amount

    practice.current_exposure += funded_amount

    claim.funded_amount = funded_amount
    claim.status = ClaimStatus.funded
    claim.decline_reason_code = None

    check_pool_invariants(pool)
    check_practice_invariants(practice)
    check_claim_invariants(claim)

    session.add(pool)
    session.add(practice)
    session.add(claim)

    logger.info(
        "Claim funded successfully: claim_id=%s, funded_amount=%d, pool_available=%d",
        claim_id, funded_amount, pool.available_capital
    )


def settle_claim_atomic(
    *,
    session: Session,
    pool_id: str,
    claim_id: str,
    settlement_date: date,
    settlement_amount: int,
) -> None:
    assert settlement_amount >= 0, f"Settlement amount cannot be negative: {settlement_amount}"

    logger.info(
        "Settling claim: claim_id=%s, pool_id=%s, settlement_amount=%d, settlement_date=%s",
        claim_id, pool_id, settlement_amount, settlement_date
    )

    pool = session.exec(select(CapitalPool).where(CapitalPool.id == pool_id)).one()
    claim = session.exec(select(Claim).where(Claim.claim_id == claim_id)).one()
    practice = session.exec(select(Practice).where(Practice.id == claim.practice_id)).one()

    check_pool_invariants(pool)
    check_practice_invariants(practice)
    check_claim_invariants(claim)

    target_status = ClaimStatus.exception if settlement_amount < claim.funded_amount else ClaimStatus.reimbursed
    try:
        validate_status_transition(claim.status, target_status)
    except InvalidStatusTransitionError as e:
        logger.warning(
            "Invalid status transition for claim %s: %s -> %s",
            claim_id, claim.status.value, target_status.value
        )
        raise LedgerError(f"Claim {claim.claim_id}: {e.message}") from e

    principal = claim.funded_amount
    assert principal > 0, f"Cannot settle claim with zero funded amount: {claim_id}"

    if principal > pool.capital_pending_settlement:
        logger.error(
            "Pool pending settlement invariant violated: principal=%d > pending=%d",
            principal, pool.capital_pending_settlement
        )
        raise InvariantViolationError("Pool pending settlement invariant violated")

    days_outstanding = max(0, (settlement_date - claim.submission_date).days)
    pool.total_days_outstanding += days_outstanding
    pool.num_settled_claims += 1

    if settlement_amount < principal:
        claim.status = ClaimStatus.exception
        logger.warning(
            "Claim settled as exception (underpayment): claim_id=%s, funded=%d, settled=%d",
            claim_id, principal, settlement_amount
        )
    else:
        claim.status = ClaimStatus.reimbursed
        logger.info(
            "Claim settled as reimbursed: claim_id=%s, funded=%d, settled=%d",
            claim_id, principal, settlement_amount
        )

    pool.capital_pending_settlement -= principal
    pool.capital_allocated -= principal

    returned_principal = min(principal, settlement_amount)
    pool.available_capital += returned_principal
    pool.capital_returned += returned_principal

    practice.current_exposure -= principal
    if practice.current_exposure < 0:
        logger.error(
            "Practice exposure went negative: practice_id=%s, exposure=%d",
            practice.id, practice.current_exposure
        )
        raise InvariantViolationError("Practice exposure invariant violated")

    check_pool_invariants(pool)
    check_practice_invariants(practice)

    session.add(pool)
    session.add(practice)
    session.add(claim)

    logger.info(
        "Claim settled successfully: claim_id=%s, days_outstanding=%d, pool_available=%d",
        claim_id, days_outstanding, pool.available_capital
    )
