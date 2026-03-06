"""FundingDecision service - underwriting output with risk scoring.

Creates FundingDecision records for claims, supporting both rule-based
and model-based decisioning. When approved, can trigger PaymentIntent creation.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from ..models.claim import Claim, ClaimStatus
from ..models.funding_decision import FundingDecision, FundingDecisionType
from ..models.payment import PaymentIntent, PaymentIntentStatus
from ..models.payer_contract import PayerContract

logger = logging.getLogger(__name__)

# Default policy constants
DEFAULT_ADVANCE_RATE = 0.80
DEFAULT_FEE_RATE = 0.03
MAX_ADVANCE_CENTS = 500_000_00  # $500k
AUTO_APPROVE_BELOW_CENTS = 10_000_00  # $10k
NEEDS_REVIEW_ABOVE_CENTS = 100_000_00  # $100k
HIGH_RISK_THRESHOLD = 0.7


class FundingDecisionService:
    """Creates and manages FundingDecision records for claims."""

    @staticmethod
    def create_funding_decision(
        db: Session,
        claim: Claim,
        risk_score: Optional[float] = None,
        model_version: Optional[str] = None,
        user_id: Optional[int] = None,
        override_decision: Optional[str] = None,
    ) -> FundingDecision:
        """Create a FundingDecision for a claim using rules + optional model score.

        Decision logic:
        1. If override_decision is set, use it (manual override)
        2. If model risk_score is provided, use risk-based thresholds
        3. Otherwise, use rule-based heuristics

        Args:
            db: Database session
            claim: The claim to decision
            risk_score: Optional model-provided risk score (0.0 = low risk, 1.0 = high risk)
            model_version: Optional model version string
            user_id: Optional user ID for audit
            override_decision: Optional manual decision override

        Returns:
            Created FundingDecision
        """
        reasons: List[Dict[str, str]] = []
        decision = override_decision
        advance_rate = DEFAULT_ADVANCE_RATE
        fee_rate = DEFAULT_FEE_RATE

        if not decision:
            decision, reasons = FundingDecisionService._evaluate_claim(
                db, claim, risk_score
            )

        # Calculate advance amount
        billed = claim.total_billed_cents or claim.amount_cents or 0
        max_advance = min(int(billed * advance_rate), MAX_ADVANCE_CENTS)

        # Adjust rates based on risk
        if risk_score is not None:
            if risk_score > HIGH_RISK_THRESHOLD:
                advance_rate = max(0.50, advance_rate - 0.20)
                fee_rate = min(0.08, fee_rate + 0.03)
                max_advance = int(billed * advance_rate)
            elif risk_score > 0.4:
                advance_rate = max(0.65, advance_rate - 0.10)
                fee_rate = min(0.05, fee_rate + 0.01)
                max_advance = int(billed * advance_rate)

        fd = FundingDecision(
            claim_id=claim.id,
            decision=decision,
            advance_rate=advance_rate,
            max_advance_amount_cents=max_advance,
            fee_rate=fee_rate,
            risk_score=risk_score,
            reasons_json=reasons,
            decisioned_at=datetime.utcnow(),
            decisioned_by=user_id,
            model_version=model_version or "rules-v1",
            policy_version="policy-v1",
        )
        db.add(fd)
        db.flush()

        # Update claim status based on decision
        if decision == FundingDecisionType.APPROVE.value:
            claim.status = ClaimStatus.APPROVED.value
        elif decision == FundingDecisionType.DENY.value:
            claim.status = ClaimStatus.DECLINED.value
        elif decision == FundingDecisionType.NEEDS_REVIEW.value:
            claim.status = ClaimStatus.NEEDS_REVIEW.value

        logger.info(
            "FundingDecision created: claim_id=%s decision=%s risk_score=%s",
            claim.id, decision, risk_score,
        )

        return fd

    @staticmethod
    def _evaluate_claim(
        db: Session, claim: Claim, risk_score: Optional[float]
    ) -> tuple:
        """Evaluate a claim and return (decision, reasons)."""
        reasons = []
        billed = claim.total_billed_cents or claim.amount_cents or 0

        # Check for missing payer
        if not claim.payer and not claim.payer_id:
            reasons.append({"rule": "missing_payer", "detail": "No payer information on claim"})
            return FundingDecisionType.DENY.value, reasons

        # Check for zero/negative amount
        if billed <= 0:
            reasons.append({"rule": "invalid_amount", "detail": "Billed amount is zero or negative"})
            return FundingDecisionType.DENY.value, reasons

        # Model-based scoring
        if risk_score is not None:
            if risk_score > HIGH_RISK_THRESHOLD:
                reasons.append({"rule": "high_risk_score", "detail": f"Risk score {risk_score:.3f} exceeds threshold {HIGH_RISK_THRESHOLD}"})
                return FundingDecisionType.DENY.value, reasons
            elif risk_score > 0.4:
                reasons.append({"rule": "moderate_risk", "detail": f"Risk score {risk_score:.3f} requires manual review"})
                return FundingDecisionType.NEEDS_REVIEW.value, reasons

        # Amount-based rules
        if billed > NEEDS_REVIEW_ABOVE_CENTS:
            reasons.append({"rule": "high_amount", "detail": f"Amount {billed} cents exceeds review threshold"})
            return FundingDecisionType.NEEDS_REVIEW.value, reasons

        # Check payer contract if available
        if claim.payer_contract_id:
            contract = db.query(PayerContract).filter(
                PayerContract.id == claim.payer_contract_id
            ).first()
            if contract and contract.status != "ACTIVE":
                reasons.append({"rule": "inactive_contract", "detail": f"Payer contract status: {contract.status}"})
                return FundingDecisionType.NEEDS_REVIEW.value, reasons

        # Auto-approve small claims
        if billed < AUTO_APPROVE_BELOW_CENTS:
            reasons.append({"rule": "auto_approve", "detail": "Amount below auto-approve threshold"})
            return FundingDecisionType.APPROVE.value, reasons

        # Default: approve
        reasons.append({"rule": "standard_approval", "detail": "Passed all checks"})
        return FundingDecisionType.APPROVE.value, reasons

    @staticmethod
    def create_payment_from_decision(
        db: Session, funding_decision: FundingDecision, claim: Claim
    ) -> Optional[PaymentIntent]:
        """If a FundingDecision is APPROVE, create a PaymentIntent.

        Returns None if decision is not APPROVE or payment already exists.
        """
        if funding_decision.decision != FundingDecisionType.APPROVE.value:
            return None

        # Check if payment already exists
        existing = db.query(PaymentIntent).filter(
            PaymentIntent.claim_id == claim.id
        ).first()
        if existing:
            logger.info("PaymentIntent already exists for claim %s", claim.id)
            return existing

        amount = funding_decision.max_advance_amount_cents or claim.amount_cents or 0

        pi = PaymentIntent(
            claim_id=claim.id,
            practice_id=claim.practice_id,
            amount_cents=amount,
            status=PaymentIntentStatus.QUEUED.value,
            queued_at=datetime.utcnow(),
        )
        pi.idempotency_key = pi.generate_idempotency_key()
        db.add(pi)
        db.flush()

        logger.info(
            "PaymentIntent created from FundingDecision: claim_id=%s amount=%s",
            claim.id, amount,
        )
        return pi
