import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..routers.auth import require_spoonbill_user
from ..models.user import User, UserRole
from ..models.practice import Practice
from ..models.audit import AuditEvent
from ..models.claim import Claim, ClaimStatus
from ..models.payment import PaymentIntent
from ..models.integration import IntegrationConnection
from ..models.invite import PracticeManagerInvite
from ..services.auth import AuthService
from ..services.economics import EconomicsService
from ..services.action_proposals import ActionProposalService
from ..services.control_tower import ControlTowerService
from ..services.reconciliation import ReconciliationService
from ..services.playbooks import PlaybookService, PLAYBOOK_TEMPLATES
from ..services.audit import AuditService
from ..schemas.practice_application import PracticePatch, PracticeUserInviteRequest
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


INVITE_TOKEN_EXPIRY_DAYS = 7


@router.patch("/practices/{practice_id}")
def patch_practice(
    practice_id: int,
    patch: PracticePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    practice = db.query(Practice).filter(Practice.id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    changes = patch.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")

    old_values = {}
    for field, value in changes.items():
        old_values[field] = getattr(practice, field, None)
        setattr(practice, field, value)

    AuditService.log_event(
        db,
        claim_id=None,
        action="PRACTICE_UPDATED",
        actor_user_id=current_user.id,
        metadata={
            "practice_id": practice_id,
            "changes": {k: {"old": old_values.get(k), "new": v} for k, v in changes.items()},
        },
    )

    db.commit()
    db.refresh(practice)
    return {
        "id": practice.id,
        "name": practice.name,
        "status": practice.status,
        "funding_limit_cents": practice.funding_limit_cents,
        "created_at": practice.created_at.isoformat() if practice.created_at else None,
    }


@router.get("/practices/{practice_id}/users")
def get_practice_users(
    practice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    practice = db.query(Practice).filter(Practice.id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    users = db.query(User).filter(User.practice_id == practice_id).all()
    result = []
    for u in users:
        latest_invite = db.query(PracticeManagerInvite).filter(
            PracticeManagerInvite.user_id == u.id,
        ).order_by(PracticeManagerInvite.created_at.desc()).first()
        result.append({
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "invite_status": "USED" if (latest_invite and latest_invite.used_at) else "PENDING" if (latest_invite and latest_invite.is_valid) else "EXPIRED" if latest_invite else None,
        })
    return {"users": result}


@router.post("/practices/{practice_id}/users/invite")
def invite_practice_user(
    practice_id: int,
    invite_req: PracticeUserInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    practice = db.query(Practice).filter(Practice.id == practice_id).first()
    if not practice:
        raise HTTPException(status_code=404, detail="Practice not found")

    existing_user = db.query(User).filter(User.email == invite_req.email).first()
    if existing_user:
        existing_practice = db.query(Practice).filter(Practice.id == existing_user.practice_id).first() if existing_user.practice_id else None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"Email {invite_req.email} is already in use.",
                "existing_practice_id": existing_user.practice_id,
                "existing_practice_name": existing_practice.name if existing_practice else None,
            },
        )

    random_password = secrets.token_urlsafe(32)
    new_user = User(
        email=invite_req.email,
        password_hash=AuthService.get_password_hash(random_password),
        role=UserRole.PRACTICE_MANAGER.value,
        practice_id=practice_id,
        is_active=False,
    )
    db.add(new_user)
    db.flush()

    invite_token = secrets.token_urlsafe(32)
    invite = PracticeManagerInvite(
        user_id=new_user.id,
        token=invite_token,
        expires_at=datetime.utcnow() + timedelta(days=INVITE_TOKEN_EXPIRY_DAYS),
    )
    db.add(invite)

    AuditService.log_event(
        db,
        claim_id=None,
        action="PRACTICE_INVITE_CREATED",
        actor_user_id=current_user.id,
        metadata={
            "practice_id": practice_id,
            "invited_email": invite_req.email,
            "user_id": new_user.id,
        },
    )

    db.commit()

    settings = get_settings()
    invite_url = f"{settings.practice_portal_base_url}/#/set-password/{invite_token}"

    return {
        "user_id": new_user.id,
        "email": new_user.email,
        "invite_url": invite_url,
        "expires_at": invite.expires_at.isoformat(),
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


@router.post("/action-proposals/simulate")
def simulate_action_proposal(
    proposal: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    return ActionProposalService.simulate_proposal(db, proposal)


@router.get("/economics/control-tower")
def get_control_tower(
    currency: str = Query("USD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    return ControlTowerService.get_control_tower(db, currency=currency)


@router.get("/reconciliation/summary")
def get_reconciliation_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    return ReconciliationService.get_summary(db)


@router.get("/reconciliation/payment-intents")
def get_reconciliation_payment_intents(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    return ReconciliationService.get_payment_intent_reconciliation(
        db, status_filter=status_filter, limit=limit
    )


@router.post("/reconciliation/ingest")
def ingest_reconciliation_data(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    ingest_type = payload.get("type")
    if ingest_type == "balance":
        return ReconciliationService.ingest_balance(
            db,
            facility=payload["facility"],
            balance_cents=payload["balance_cents"],
            as_of=payload["as_of"],
            source=payload.get("source", "manual"),
        )
    elif ingest_type == "payment_confirmation":
        return ReconciliationService.ingest_payment_confirmation(
            db,
            payment_intent_id=payload["payment_intent_id"],
            rail_ref=payload.get("rail_ref"),
            status=payload["status"],
            confirmed_at=payload.get("confirmed_at"),
            raw_json=payload.get("raw_json"),
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="type must be 'balance' or 'payment_confirmation'",
        )


@router.post("/reconciliation/resolve")
def resolve_reconciliation_mismatch(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    result = ReconciliationService.resolve_mismatch(
        db,
        confirmation_id=payload["confirmation_id"],
        resolution_note=payload.get("resolution_note", ""),
        actor_user_id=current_user.id,
    )
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Not found"))
    return result


@router.get("/tasks")
def get_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    practice_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    return PlaybookService.get_tasks(
        db,
        status_filter=status_filter,
        practice_id=practice_id,
        limit=limit,
        offset=offset,
    )


@router.post("/tasks/{task_id}/update")
def update_task(
    task_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    result = PlaybookService.update_task(
        db,
        task_id=task_id,
        status=payload.get("status"),
        owner_user_id=payload.get("owner_user_id"),
        resolution_note=payload.get("resolution_note"),
        actor_user_id=current_user.id,
    )
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Not found"))
    return result


@router.post("/playbooks/run")
def run_playbook(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    result = PlaybookService.run_playbook(
        db,
        playbook_type=payload["playbook_type"],
        practice_id=payload.get("practice_id"),
        claim_id=payload.get("claim_id"),
        payment_intent_id=payload.get("payment_intent_id"),
        actor_user_id=current_user.id,
    )
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result.get("error", "Playbook failed"),
        )
    return result


@router.get("/playbooks/templates")
def get_playbook_templates(
    current_user: User = Depends(require_spoonbill_user),
):
    return {
        "templates": [
            {
                "type": k,
                "title_template": v["title_template"],
                "description": v["description"],
                "priority": v["priority"],
                "sla_hours": v["sla_hours"],
            }
            for k, v in PLAYBOOK_TEMPLATES.items()
        ]
    }
