from typing import List, Optional
from datetime import date
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..config import get_settings
from ..database import get_db
from ..models.claim import Claim, ClaimStatus
from ..models.document import ClaimDocument
from ..models.payment import PaymentIntent
from ..models.user import User
from ..schemas.claim import PracticeClaimCreate, ClaimResponse, ClaimListResponse
from ..schemas.document import DocumentUploadResponse, DocumentListResponse
from ..services.audit import AuditService
from ..services.underwriting import UnderwritingService
from .auth import require_practice_manager

router = APIRouter(prefix="/practice", tags=["practice-portal"])
settings = get_settings()

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/data/uploads")


def get_claim_for_practice(db: Session, claim_id: int, practice_id: int) -> Claim:
    claim = db.query(Claim).filter(
        Claim.id == claim_id,
        Claim.practice_id == practice_id
    ).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


def verify_claim_ownership(db: Session, claim_id: int, practice_id: int) -> Claim:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    if claim.practice_id != practice_id:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.post("/claims", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
def submit_claim(
    claim_data: PracticeClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    practice_id = current_user.practice_id
    
    fingerprint = Claim.compute_fingerprint(
        practice_id=practice_id,
        patient_name=claim_data.patient_name,
        procedure_date=claim_data.procedure_date,
        amount_cents=claim_data.amount_cents,
        payer=claim_data.payer,
    )
    
    existing = db.query(Claim).filter(
        Claim.fingerprint == fingerprint,
        Claim.practice_id == practice_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate claim detected (matches claim ID {existing.id})",
        )
    
    claim = Claim(
        practice_id=practice_id,
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
    
    AuditService.log_claim_created(db, claim, actor_user_id=current_user.id)
    
    decision, reasons = UnderwritingService.run_underwriting(db, claim, user_id=current_user.id)
    AuditService.log_underwriting_decision(db, claim, decision.value, reasons, actor_user_id=current_user.id)
    
    target_status = UnderwritingService.get_target_status(decision)
    old_status = ClaimStatus(claim.status)
    claim.status = target_status.value
    AuditService.log_status_change(
        db, claim, old_status, target_status,
        actor_user_id=current_user.id,
        reason=f"Underwriting decision: {decision.value}",
    )
    
    db.commit()
    db.refresh(claim)
    return claim


class PaginatedClaimsResponse:
    """Response model for paginated claims list."""
    pass


@router.get("/claims", response_model=List[ClaimListResponse])
def list_practice_claims(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    claim_id: Optional[int] = Query(None, description="Filter by claim ID"),
    claim_token: Optional[str] = Query(None, description="Filter by claim token"),
    submitted_from: Optional[date] = Query(None, description="Filter by submission date (from)"),
    submitted_to: Optional[date] = Query(None, description="Filter by submission date (to)"),
    decision_from: Optional[date] = Query(None, description="Filter by decision date (from)"),
    decision_to: Optional[date] = Query(None, description="Filter by decision date (to)"),
    q: Optional[str] = Query(None, description="Search across patient name, payer, external claim ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    """List claims for the current practice with filtering and pagination.
    
    All filters are optional and composable. Results are always tenant-scoped
    (practice_id derived from JWT) and ordered by most recent first.
    """
    practice_id = current_user.practice_id
    
    query = db.query(Claim).filter(Claim.practice_id == practice_id)
    
    if status_filter:
        query = query.filter(Claim.status == status_filter)
    
    if claim_id:
        query = query.filter(Claim.id == claim_id)
    
    if claim_token:
        query = query.filter(Claim.claim_token == claim_token)
    
    if submitted_from:
        query = query.filter(Claim.created_at >= submitted_from)
    
    if submitted_to:
        from datetime import datetime
        end_of_day = datetime.combine(submitted_to, datetime.max.time())
        query = query.filter(Claim.created_at <= end_of_day)
    
    if decision_from:
        from ..models.audit import AuditEvent
        subquery = db.query(AuditEvent.claim_id).filter(
            AuditEvent.action == "UNDERWRITING_DECISION",
            AuditEvent.created_at >= decision_from
        ).subquery()
        query = query.filter(Claim.id.in_(subquery))
    
    if decision_to:
        from ..models.audit import AuditEvent
        from datetime import datetime
        end_of_day = datetime.combine(decision_to, datetime.max.time())
        subquery = db.query(AuditEvent.claim_id).filter(
            AuditEvent.action == "UNDERWRITING_DECISION",
            AuditEvent.created_at <= end_of_day
        ).subquery()
        query = query.filter(Claim.id.in_(subquery))
    
    if q:
        search_term = f"%{q}%"
        query = query.filter(
            or_(
                Claim.patient_name.ilike(search_term),
                Claim.payer.ilike(search_term),
                Claim.external_claim_id.ilike(search_term),
            )
        )
    
    query = query.order_by(Claim.created_at.desc())
    
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    return query.all()


@router.get("/claims/{claim_id}", response_model=ClaimResponse)
def get_practice_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    practice_id = current_user.practice_id
    
    claim = get_claim_for_practice(db, claim_id, practice_id)
    verify_claim_ownership(db, claim_id, practice_id)
    
    return claim


@router.post("/claims/{claim_id}/documents", response_model=DocumentUploadResponse)
async def upload_document(
    claim_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    practice_id = current_user.practice_id
    
    get_claim_for_practice(db, claim_id, practice_id)
    verify_claim_ownership(db, claim_id, practice_id)
    
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    storage_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    content = await file.read()
    with open(storage_path, "wb") as f:
        f.write(content)
    
    document = ClaimDocument(
        claim_id=claim_id,
        practice_id=practice_id,
        filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        storage_path=storage_path,
        uploaded_by_user_id=current_user.id,
    )
    db.add(document)
    
    AuditService.log_event(
        db, claim_id, "DOCUMENT_UPLOADED",
        actor_user_id=current_user.id,
        metadata={"filename": document.filename, "document_id": None},
    )
    
    db.commit()
    db.refresh(document)
    
    AuditService.log_event(
        db, claim_id, "DOCUMENT_UPLOADED",
        actor_user_id=current_user.id,
        metadata={"filename": document.filename, "document_id": document.id},
    )
    db.commit()
    
    return document


@router.get("/claims/{claim_id}/documents", response_model=List[DocumentListResponse])
def list_claim_documents(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    practice_id = current_user.practice_id
    
    get_claim_for_practice(db, claim_id, practice_id)
    verify_claim_ownership(db, claim_id, practice_id)
    
    documents = db.query(ClaimDocument).filter(
        ClaimDocument.claim_id == claim_id,
        ClaimDocument.practice_id == practice_id
    ).order_by(ClaimDocument.created_at.desc()).all()
    
    return documents


@router.get("/documents/{document_id}")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    from fastapi.responses import FileResponse
    
    practice_id = current_user.practice_id
    
    document = db.query(ClaimDocument).filter(
        ClaimDocument.id == document_id,
        ClaimDocument.practice_id == practice_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    verify_claim_ownership(db, document.claim_id, practice_id)
    
    if not os.path.exists(document.storage_path):
        raise HTTPException(status_code=404, detail="Document file not found")
    
    return FileResponse(
        path=document.storage_path,
        filename=document.filename,
        media_type=document.content_type,
    )


@router.get("/claims/{claim_id}/payment")
def get_claim_payment_status(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_practice_manager),
):
    practice_id = current_user.practice_id
    
    get_claim_for_practice(db, claim_id, practice_id)
    verify_claim_ownership(db, claim_id, practice_id)
    
    payment = db.query(PaymentIntent).filter(
        PaymentIntent.claim_id == claim_id,
        PaymentIntent.practice_id == practice_id
    ).first()
    
    if not payment:
        return None
    
    return {
        "id": str(payment.id),
        "status": payment.status,
        "amount_cents": payment.amount_cents,
        "currency": payment.currency,
        "provider": payment.provider,
        "provider_reference": payment.provider_reference,
        "confirmed_at": payment.confirmed_at.isoformat() if payment.confirmed_at else None,
        "failure_code": payment.failure_code,
        "failure_message": payment.failure_message,
    }
