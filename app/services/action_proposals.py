import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.practice import Practice, PracticeStatus
from ..models.payment import PaymentIntent, PaymentIntentStatus
from ..models.claim import Claim, ClaimStatus
from ..models.ledger import (
    LedgerAccount, LedgerAccountType, LedgerEntry,
    LedgerEntryDirection, LedgerEntryStatus,
)
from ..services.economics import EconomicsService
from ..services.audit import AuditService

logger = logging.getLogger(__name__)

GLOBAL_MAX_EXPOSURE_CENTS = 10_000_000_00
PER_PRACTICE_MAX_EXPOSURE_CENTS = 1_000_000_00


class ActionProposalService:
    @staticmethod
    def generate_proposals(
        db: Session,
        practice_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        proposals = []

        if practice_id:
            practices = db.query(Practice).filter(
                Practice.id == practice_id,
                Practice.status == PracticeStatus.ACTIVE.value,
            ).all()
        else:
            practices = db.query(Practice).filter(
                Practice.status == PracticeStatus.ACTIVE.value,
            ).all()

        liquidity = EconomicsService.get_liquidity_summary(db)

        for practice in practices:
            exposure = EconomicsService.get_practice_exposure(db, practice.id)
            practice_proposals = ActionProposalService._analyze_practice(
                db, practice, exposure, liquidity
            )
            proposals.extend(practice_proposals)

        return proposals

    @staticmethod
    def _analyze_practice(
        db: Session,
        practice: Practice,
        exposure: dict,
        liquidity: dict,
    ) -> List[Dict[str, Any]]:
        proposals = []

        funded = exposure.get("funded_outstanding_cents", 0)
        limit = practice.funding_limit_cents or 0
        utilization = exposure.get("utilization_pct", 0)
        exceptions = exposure.get("exception_count", 0)

        if limit > 0 and utilization >= 80 and utilization < 95:
            new_limit = int(limit * 1.25)
            if new_limit <= PER_PRACTICE_MAX_EXPOSURE_CENTS:
                proposals.append({
                    "action": "ADJUST_LIMIT",
                    "practice_id": practice.id,
                    "practice_name": practice.name,
                    "params": {
                        "current_limit_cents": limit,
                        "proposed_limit_cents": new_limit,
                    },
                    "reason": f"Utilization at {utilization}%. Increasing limit by 25% to avoid funding delays.",
                    "supporting_metrics": {
                        "utilization_pct": utilization,
                        "funded_outstanding_cents": funded,
                        "current_limit_cents": limit,
                    },
                    "severity": "medium",
                    "required_approvals": ["SPOONBILL_OPS"],
                })

        if utilization >= 95:
            proposals.append({
                "action": "PAUSE_FUNDING",
                "practice_id": practice.id,
                "practice_name": practice.name,
                "params": {
                    "reason": "near_limit",
                },
                "reason": f"Utilization at {utilization}%. Near or at limit. Consider pausing new funding until exposure decreases.",
                "supporting_metrics": {
                    "utilization_pct": utilization,
                    "funded_outstanding_cents": funded,
                    "funding_limit_cents": limit,
                },
                "severity": "high",
                "required_approvals": ["SPOONBILL_OPS"],
            })

        if exceptions >= 3:
            proposals.append({
                "action": "REVIEW_EXCEPTIONS",
                "practice_id": practice.id,
                "practice_name": practice.name,
                "params": {
                    "exception_count": exceptions,
                },
                "reason": f"{exceptions} payment exceptions detected. Review and resolve to prevent funding disruption.",
                "supporting_metrics": {
                    "exception_count": exceptions,
                    "funded_outstanding_cents": funded,
                },
                "severity": "high",
                "required_approvals": ["SPOONBILL_OPS"],
            })

        if limit == 0 and practice.status == PracticeStatus.ACTIVE.value:
            active_claims = db.query(func.count(Claim.id)).filter(
                Claim.practice_id == practice.id,
                Claim.status.in_([
                    ClaimStatus.APPROVED.value,
                    ClaimStatus.PAID.value,
                ]),
            ).scalar() or 0

            if active_claims >= 3:
                proposals.append({
                    "action": "ADJUST_LIMIT",
                    "practice_id": practice.id,
                    "practice_name": practice.name,
                    "params": {
                        "current_limit_cents": 0,
                        "proposed_limit_cents": 50_000_00,
                    },
                    "reason": f"Practice has {active_claims} approved/paid claims but no funding limit. Recommend setting initial limit.",
                    "supporting_metrics": {
                        "active_claim_count": active_claims,
                    },
                    "severity": "medium",
                    "required_approvals": ["SPOONBILL_OPS"],
                })

        return proposals

    @staticmethod
    def validate_proposal(
        db: Session,
        proposal: Dict[str, Any],
    ) -> Dict[str, Any]:
        action = proposal.get("action")
        practice_id = proposal.get("practice_id")
        params = proposal.get("params", {})

        errors = []

        if not action:
            errors.append("Missing action type")
        if not practice_id:
            errors.append("Missing practice_id")

        practice = db.query(Practice).filter(Practice.id == practice_id).first()
        if not practice:
            errors.append(f"Practice {practice_id} not found")
        elif practice.status != PracticeStatus.ACTIVE.value:
            errors.append(f"Practice {practice_id} is not active")

        if action == "ADJUST_LIMIT":
            new_limit = params.get("proposed_limit_cents")
            if new_limit is None:
                errors.append("Missing proposed_limit_cents")
            elif new_limit > PER_PRACTICE_MAX_EXPOSURE_CENTS:
                errors.append(
                    f"Proposed limit {new_limit} exceeds max per-practice exposure "
                    f"({PER_PRACTICE_MAX_EXPOSURE_CENTS})"
                )

            liquidity = EconomicsService.get_liquidity_summary(db)
            available = liquidity.get("available_cash_cents", 0)
            if new_limit and new_limit > available:
                errors.append(
                    f"Proposed limit {new_limit} exceeds available capital ({available})"
                )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
        }

    @staticmethod
    def execute_proposal(
        db: Session,
        proposal: Dict[str, Any],
        actor_user_id: int,
    ) -> Dict[str, Any]:
        validation = ActionProposalService.validate_proposal(db, proposal)
        if not validation["valid"]:
            return {"success": False, "errors": validation["errors"]}

        action = proposal["action"]
        practice_id = proposal["practice_id"]
        params = proposal.get("params", {})

        AuditService.log_event(
            db=db,
            claim_id=None,
            action="ACTION_PROPOSED",
            actor_user_id=actor_user_id,
            metadata={
                "action_type": action,
                "practice_id": practice_id,
                "params": params,
                "reason": proposal.get("reason"),
            },
        )

        result = {}

        if action == "ADJUST_LIMIT":
            practice = db.query(Practice).filter(Practice.id == practice_id).first()
            old_limit = practice.funding_limit_cents
            new_limit = params["proposed_limit_cents"]
            practice.funding_limit_cents = new_limit

            AuditService.log_event(
                db=db,
                claim_id=None,
                action="ACTION_EXECUTED",
                actor_user_id=actor_user_id,
                metadata={
                    "action_type": "ADJUST_LIMIT",
                    "practice_id": practice_id,
                    "old_limit_cents": old_limit,
                    "new_limit_cents": new_limit,
                },
            )
            result = {
                "action": "ADJUST_LIMIT",
                "old_limit_cents": old_limit,
                "new_limit_cents": new_limit,
            }

        elif action == "PAUSE_FUNDING":
            practice = db.query(Practice).filter(Practice.id == practice_id).first()
            old_status = practice.status
            practice.status = PracticeStatus.INACTIVE.value

            AuditService.log_event(
                db=db,
                claim_id=None,
                action="ACTION_EXECUTED",
                actor_user_id=actor_user_id,
                metadata={
                    "action_type": "PAUSE_FUNDING",
                    "practice_id": practice_id,
                    "old_status": old_status,
                    "new_status": PracticeStatus.INACTIVE.value,
                },
            )
            result = {
                "action": "PAUSE_FUNDING",
                "old_status": old_status,
                "new_status": PracticeStatus.INACTIVE.value,
            }

        elif action == "REVIEW_EXCEPTIONS":
            AuditService.log_event(
                db=db,
                claim_id=None,
                action="ACTION_EXECUTED",
                actor_user_id=actor_user_id,
                metadata={
                    "action_type": "REVIEW_EXCEPTIONS",
                    "practice_id": practice_id,
                    "note": "Flagged for manual review",
                },
            )
            result = {
                "action": "REVIEW_EXCEPTIONS",
                "note": "Flagged for manual review",
            }
        else:
            return {"success": False, "errors": [f"Unknown action: {action}"]}

        db.commit()

        return {"success": True, "result": result}
