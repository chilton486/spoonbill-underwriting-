from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Set

from .models import Claim, Practice


class DeclineReason(str, Enum):
    payer_not_approved = "PAYER_NOT_APPROVED"
    payer_plan_not_supported = "PAYER_PLAN_NOT_SUPPORTED"
    plan_type_not_approved = "PLAN_TYPE_NOT_APPROVED"
    procedure_not_allowed = "PROCEDURE_NOT_ALLOWED"
    procedure_below_pay_rate_threshold = "PROCEDURE_PAY_RATE_BELOW_THRESHOLD"
    practice_tenure_too_low = "PRACTICE_TENURE_TOO_LOW"
    practice_history_insufficient = "PRACTICE_HISTORY_INSUFFICIENT"
    exceeds_practice_exposure_limit = "EXCEEDS_PRACTICE_EXPOSURE_LIMIT"
    insufficient_pool_liquidity = "INSUFFICIENT_POOL_LIQUIDITY"


@dataclass(frozen=True)
class UnderwritingDecision:
    approved: bool
    funded_amount: int = 0
    reason_code: str | None = None


@dataclass(frozen=True)
class UnderwritingPolicy:
    approved_payers: Set[str]

    excluded_plan_keywords: Set[str]

    allowed_procedures: Set[str]

    procedure_pay_rate_threshold: float

    min_practice_tenure_months: int
    min_practice_clean_claim_rate: float

    procedure_historical_pay_rate: Dict[str, float]


def underwrite_claim(
    *,
    claim: Claim,
    practice: Practice,
    policy: UnderwritingPolicy,
    remaining_practice_exposure_limit: int,
    pool_available_capital: int,
) -> UnderwritingDecision:
    payer_normalized = claim.payer.strip()

    if payer_normalized not in policy.approved_payers:
        return UnderwritingDecision(False, reason_code=DeclineReason.payer_not_approved.value)

    payer_lower = payer_normalized.lower()
    for kw in policy.excluded_plan_keywords:
        if kw.lower() in payer_lower:
            return UnderwritingDecision(False, reason_code=DeclineReason.payer_plan_not_supported.value)

    procedure_codes = claim.procedure_code.split(";")
    for code in procedure_codes:
        code = code.strip()
        if code not in policy.allowed_procedures:
            return UnderwritingDecision(False, reason_code=DeclineReason.procedure_not_allowed.value)

        pay_rate = policy.procedure_historical_pay_rate.get(code)
        if pay_rate is None or pay_rate < policy.procedure_pay_rate_threshold:
            return UnderwritingDecision(
                False,
                reason_code=DeclineReason.procedure_below_pay_rate_threshold.value,
            )

    if practice.tenure_months < policy.min_practice_tenure_months:
        return UnderwritingDecision(False, reason_code=DeclineReason.practice_tenure_too_low.value)

    if practice.historical_clean_claim_rate < policy.min_practice_clean_claim_rate:
        return UnderwritingDecision(
            False,
            reason_code=DeclineReason.practice_history_insufficient.value,
        )

    if claim.expected_allowed_amount > remaining_practice_exposure_limit:
        return UnderwritingDecision(
            False,
            reason_code=DeclineReason.exceeds_practice_exposure_limit.value,
        )

    funded_amount = claim.expected_allowed_amount

    if funded_amount > pool_available_capital:
        return UnderwritingDecision(False, reason_code=DeclineReason.insufficient_pool_liquidity.value)

    return UnderwritingDecision(True, funded_amount=funded_amount, reason_code=None)
