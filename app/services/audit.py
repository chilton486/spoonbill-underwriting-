import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from ..models.audit import AuditEvent
from ..models.claim import Claim, ClaimStatus


class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        claim_id: Optional[int],
        action: str,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        actor_user_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            claim_id=claim_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            actor_user_id=actor_user_id,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.add(event)
        return event

    @staticmethod
    def log_status_change(
        db: Session,
        claim: Claim,
        from_status: ClaimStatus,
        to_status: ClaimStatus,
        actor_user_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> AuditEvent:
        metadata = {}
        if reason:
            metadata["reason"] = reason
        
        return AuditService.log_event(
            db=db,
            claim_id=claim.id,
            action="STATUS_CHANGE",
            from_status=from_status.value,
            to_status=to_status.value,
            actor_user_id=actor_user_id,
            metadata=metadata if metadata else None,
        )

    @staticmethod
    def log_claim_created(
        db: Session,
        claim: Claim,
        actor_user_id: Optional[int] = None,
    ) -> AuditEvent:
        return AuditService.log_event(
            db=db,
            claim_id=claim.id,
            action="CLAIM_CREATED",
            to_status=claim.status,
            actor_user_id=actor_user_id,
        )

    @staticmethod
    def log_underwriting_decision(
        db: Session,
        claim: Claim,
        decision: str,
        reasons: list,
        actor_user_id: Optional[int] = None,
    ) -> AuditEvent:
        return AuditService.log_event(
            db=db,
            claim_id=claim.id,
            action="UNDERWRITING_DECISION",
            actor_user_id=actor_user_id,
            metadata={"decision": decision, "reasons": reasons},
        )
