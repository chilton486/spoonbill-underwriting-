from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.claim import Claim, ClaimStatus
from ..models.user import User
from ..schemas.claim import ClaimCreate, ClaimUpdate, ClaimResponse, ClaimListResponse, ClaimTransitionRequest
from ..services.audit import AuditService
from ..services.underwriting import UnderwritingService
from ..state_machine import validate_status_transition, get_valid_transitions, InvalidStatusTransitionError
from .auth import get_current_user, require_spoonbill_user

router = APIRouter(prefix="/api/claims", tags=["claims"])


@router.post("", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
def create_claim(
    claim_data: ClaimCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    fingerprint = Claim.compute_fingerprint(
        practice_id=claim_data.practice_id,
        patient_name=claim_data.patient_name,
        procedure_date=claim_data.procedure_date,
        amount_cents=claim_data.amount_cents,
        payer=claim_data.payer,
    )
    
    existing = db.query(Claim).filter(Claim.fingerprint == fingerprint).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate claim detected (matches claim ID {existing.id})",
        )
    
    claim = Claim(
        practice_id=claim_data.practice_id,
        patient_name=claim_data.patient_name,
        payer=claim_data.payer,
        amount_cents=claim_data.amount_cents,
        procedure_date=claim_data.procedure_date,
        external_claim_id=claim_data.external_claim_id,
        procedure_codes=claim_data.procedure_codes,
        fingerprint=fingerprint,
        claim_token=Claim.generate_claim_token(),
        status=ClaimStatus.NEW.value,
    )
    db.add(claim)
    db.flush()
    
    user_id = current_user.id if current_user else None
    AuditService.log_claim_created(db, claim, actor_user_id=user_id)
    
    decision, reasons = UnderwritingService.run_underwriting(db, claim, user_id=user_id)
    AuditService.log_underwriting_decision(db, claim, decision.value, reasons, actor_user_id=user_id)
    
    target_status = UnderwritingService.get_target_status(decision)
    old_status = ClaimStatus(claim.status)
    claim.status = target_status.value
    AuditService.log_status_change(
        db, claim, old_status, target_status,
        actor_user_id=user_id,
        reason=f"Underwriting decision: {decision.value}",
    )
    
    db.commit()
    db.refresh(claim)
    return claim


@router.get("", response_model=List[ClaimListResponse])
def list_claims(
    status: Optional[str] = Query(None, description="Filter by status"),
    practice_id: Optional[int] = Query(None, description="Filter by practice ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    query = db.query(Claim)
    if status:
        query = query.filter(Claim.status == status)
    if practice_id:
        query = query.filter(Claim.practice_id == practice_id)
    query = query.order_by(Claim.created_at.desc())
    return query.all()


@router.get("/{claim_id}", response_model=ClaimResponse)
def get_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.patch("/{claim_id}", response_model=ClaimResponse)
def update_claim(
    claim_id: int,
    claim_data: ClaimUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    if claim.status in [ClaimStatus.CLOSED.value, ClaimStatus.DECLINED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit claim in {claim.status} status",
        )
    
    update_data = claim_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(claim, field, value)
    
    if any(f in update_data for f in ["practice_id", "patient_name", "procedure_date", "amount_cents", "payer"]):
        claim.fingerprint = Claim.compute_fingerprint(
            practice_id=claim.practice_id,
            patient_name=claim.patient_name,
            procedure_date=claim.procedure_date,
            amount_cents=claim.amount_cents,
            payer=claim.payer,
        )
    
    AuditService.log_event(
        db, claim.id, "CLAIM_UPDATED",
        actor_user_id=current_user.id,
        metadata={"updated_fields": list(update_data.keys())},
    )
    
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/{claim_id}/transition", response_model=ClaimResponse)
def transition_claim(
    claim_id: int,
    transition_data: ClaimTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    try:
        target = ClaimStatus(transition_data.to_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {transition_data.to_status}")
    
    current = ClaimStatus(claim.status)
    
    try:
        validate_status_transition(current, target)
    except InvalidStatusTransitionError as e:
        raise HTTPException(status_code=400, detail=e.message)
    
    claim.status = target.value
    AuditService.log_status_change(
        db, claim, current, target,
        actor_user_id=current_user.id,
        reason=transition_data.reason,
    )
    
    db.commit()
    db.refresh(claim)
    return claim


@router.get("/{claim_id}/transitions")
def get_claim_transitions(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    current = ClaimStatus(claim.status)
    valid = get_valid_transitions(current)
    
    return {
        "claim_id": claim.id,
        "current_status": claim.status,
        "valid_transitions": [s.value for s in valid],
    }
