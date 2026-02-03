import json
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.claim import Claim, ClaimStatus
from ..models.underwriting import UnderwritingDecision, DecisionType

settings = get_settings()


class UnderwritingService:
    @staticmethod
    def run_underwriting(db: Session, claim: Claim, user_id: Optional[int] = None) -> Tuple[DecisionType, List[str]]:
        reasons: List[str] = []
        
        if not claim.payer or not claim.payer.strip():
            reasons.append("MISSING_PAYER")
        
        if not claim.amount_cents or claim.amount_cents <= 0:
            reasons.append("INVALID_AMOUNT")
        
        if claim.fingerprint:
            existing = db.query(Claim).filter(
                Claim.fingerprint == claim.fingerprint,
                Claim.id != claim.id
            ).first()
            if existing:
                reasons.append("DUPLICATE_CLAIM")
        
        if reasons:
            decision = DecisionType.NEEDS_REVIEW
            if "DUPLICATE_CLAIM" in reasons:
                decision = DecisionType.DECLINE
        elif claim.amount_cents > settings.underwriting_amount_threshold_cents:
            reasons.append("AMOUNT_EXCEEDS_THRESHOLD")
            decision = DecisionType.NEEDS_REVIEW
        elif claim.amount_cents <= settings.underwriting_auto_approve_below_cents:
            decision = DecisionType.APPROVE
        else:
            decision = DecisionType.APPROVE
        
        underwriting_decision = UnderwritingDecision(
            claim_id=claim.id,
            decision=decision.value,
            reasons=json.dumps(reasons) if reasons else None,
            decided_by=user_id,
        )
        db.add(underwriting_decision)
        
        return decision, reasons

    @staticmethod
    def get_target_status(decision: DecisionType) -> ClaimStatus:
        if decision == DecisionType.APPROVE:
            return ClaimStatus.APPROVED
        elif decision == DecisionType.DECLINE:
            return ClaimStatus.DECLINED
        else:
            return ClaimStatus.NEEDS_REVIEW
