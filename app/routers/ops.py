import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..routers.auth import require_spoonbill_user
from ..models.user import User
from ..models.practice import Practice
from ..models.audit import AuditEvent
from ..models.claim import Claim, ClaimStatus
from ..models.payment import PaymentIntent
from ..models.integration import IntegrationConnection
from ..services.economics import EconomicsService
from ..services.action_proposals import ActionProposalService
from ..services.audit import AuditService
from sqlalchemy import func, desc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/economics/summary")
def get_economics_summary(
    currency: str = Query("USD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    return EconomicsService.get_liquidity_summary(db, currency=currency)


@router.get("/economics/exposure")
def get_economics_exposure(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    return EconomicsService.get_exposure(db)


@router.get("/economics/payment-intents")
def get_economics_payment_intents(
    status_filter: Optional[str] = Query(None, alias="status"),
    practice_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    return EconomicsService.get_payment_intents_board(
        db,
        status_filter=status_filter,
        practice_id=practice_id,
        limit=limit,
        offset=offset,
    )


@router.get("/economics/exceptions")
def get_economics_exceptions(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    exceptions = db.query(Claim).filter(
        Claim.status == ClaimStatus.PAYMENT_EXCEPTION.value,
    ).order_by(desc(Claim.updated_at)).limit(limit).all()

    failed_payments = db.query(PaymentIntent).filter(
        PaymentIntent.status == "FAILED",
    ).order_by(desc(PaymentIntent.created_at)).limit(limit).all()

    return {
        "exception_claims": [
            {
                "id": c.id,
                "practice_id": c.practice_id,
                "patient_name": c.patient_name,
                "payer": c.payer,
                "amount_cents": c.amount_cents,
                "status": c.status,
                "exception_code": c.exception_code,
                "claim_token": c.claim_token,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in exceptions
        ],
        "failed_payments": [
            {
                "id": str(fp.id),
                "claim_id": fp.claim_id,
                "practice_id": fp.practice_id,
                "amount_cents": fp.amount_cents,
                "failure_code": fp.failure_code,
                "failure_message": fp.failure_message,
                "created_at": fp.created_at.isoformat() if fp.created_at else None,
            }
            for fp in failed_payments
        ],
    }


@router.get("/practices/{practice_id}/crm")
def get_practice_crm(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    practice = db.query(Practice).filter(Practice.id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    exposure = EconomicsService.get_practice_exposure(db, practice_id)

    claim_counts = dict(
        db.query(Claim.status, func.count(Claim.id))
        .filter(Claim.practice_id == practice_id)
        .group_by(Claim.status)
        .all()
    )

    total_claims = sum(claim_counts.values())
    total_funded = db.query(
        func.coalesce(func.sum(PaymentIntent.amount_cents), 0)
    ).filter(
        PaymentIntent.practice_id == practice_id,
    ).scalar() or 0

    timeline = db.query(AuditEvent).join(
        Claim, AuditEvent.claim_id == Claim.id, isouter=True
    ).filter(
        (Claim.practice_id == practice_id) | (AuditEvent.claim_id.is_(None))
    ).order_by(desc(AuditEvent.created_at)).limit(20).all()

    timeline_items = []
    for event in timeline:
        meta = {}
        if event.metadata_json:
            import json
            try:
                meta = json.loads(event.metadata_json)
            except (json.JSONDecodeError, TypeError):
                pass
        if meta.get("practice_id") and meta["practice_id"] != practice_id:
            continue
        timeline_items.append({
            "id": event.id,
            "action": event.action,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "claim_id": event.claim_id,
            "actor_user_id": event.actor_user_id,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "metadata": meta,
        })

    integrations = db.query(IntegrationConnection).filter(
        IntegrationConnection.practice_id == practice_id,
    ).all()

    integration_items = [
        {
            "id": ic.id,
            "provider": ic.provider,
            "status": ic.status,
            "last_synced_at": ic.last_synced_at.isoformat() if ic.last_synced_at else None,
        }
        for ic in integrations
    ]

    recent_exceptions = db.query(Claim).filter(
        Claim.practice_id == practice_id,
        Claim.status == ClaimStatus.PAYMENT_EXCEPTION.value,
    ).order_by(desc(Claim.updated_at)).limit(5).all()

    return {
        "practice": {
            "id": practice.id,
            "name": practice.name,
            "status": practice.status,
            "funding_limit_cents": practice.funding_limit_cents,
            "created_at": practice.created_at.isoformat() if practice.created_at else None,
        },
        "kpis": {
            "total_claims": total_claims,
            "claim_counts_by_status": claim_counts,
            "total_funded_cents": total_funded,
            **exposure,
        },
        "timeline": timeline_items[:20],
        "integrations": integration_items,
        "recent_exceptions": [
            {
                "id": c.id,
                "payer": c.payer,
                "amount_cents": c.amount_cents,
                "exception_code": c.exception_code,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in recent_exceptions
        ],
    }


@router.post("/action-proposals/generate")
def generate_action_proposals(
    practice_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    proposals = ActionProposalService.generate_proposals(db, practice_id=practice_id)
    return {"proposals": proposals, "count": len(proposals)}


@router.post("/action-proposals/execute")
def execute_action_proposal(
    proposal: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    result = ActionProposalService.execute_proposal(
        db, proposal, actor_user_id=current_user.id
    )
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": result["errors"]},
        )
    return result


@router.post("/action-proposals/validate")
def validate_action_proposal(
    proposal: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    return ActionProposalService.validate_proposal(db, proposal)
