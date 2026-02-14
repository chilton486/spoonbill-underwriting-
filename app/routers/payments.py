from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.claim import Claim, ClaimStatus
from ..models.payment import PaymentIntent, PaymentIntentStatus
from ..models.user import User
from ..services.payments import PaymentOrchestrationService, PaymentError
from ..services.ledger import LedgerService, InsufficientFundsError
from ..services.audit import AuditService
from .auth import require_spoonbill_user

router = APIRouter(prefix="/api/payments", tags=["payments"])


class PaymentIntentResponse(BaseModel):
    id: UUID
    claim_id: int
    practice_id: int
    amount_cents: int
    currency: str
    status: str
    idempotency_key: str
    provider: str
    provider_reference: Optional[str]
    failure_code: Optional[str]
    failure_message: Optional[str]
    sent_at: Optional[str]
    confirmed_at: Optional[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class ProcessPaymentRequest(BaseModel):
    claim_id: int


class ProcessPaymentResponse(BaseModel):
    payment_intent: PaymentIntentResponse
    success: bool
    message: str


class LedgerSummaryResponse(BaseModel):
    currency: str
    capital_cash_cents: int
    payment_clearing_cents: int
    total_practice_payable_cents: int


class SeedCapitalRequest(BaseModel):
    amount_cents: int
    currency: str = "USD"


@router.post("/process", response_model=ProcessPaymentResponse)
def process_payment_for_claim(
    request: ProcessPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    claim = db.query(Claim).filter(Claim.id == request.claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {request.claim_id} not found")
    
    if claim.status != ClaimStatus.APPROVED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Claim {request.claim_id} is not in APPROVED status (current: {claim.status})"
        )
    
    service = PaymentOrchestrationService()
    
    try:
        payment_intent, success = service.process_approved_claim(db, claim, current_user.id)
        db.commit()
        db.refresh(payment_intent)
        
        message = "Payment confirmed successfully" if success else f"Payment failed: {payment_intent.failure_code}"
        
        return ProcessPaymentResponse(
            payment_intent=_to_payment_response(payment_intent),
            success=success,
            message=message,
        )
    except InsufficientFundsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[PaymentIntentResponse])
def list_payments(
    status: Optional[str] = Query(None, description="Filter by status"),
    practice_id: Optional[int] = Query(None, description="Filter by practice ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    query = db.query(PaymentIntent)
    if status:
        query = query.filter(PaymentIntent.status == status)
    if practice_id:
        query = query.filter(PaymentIntent.practice_id == practice_id)
    query = query.order_by(PaymentIntent.created_at.desc())
    
    return [_to_payment_response(p) for p in query.all()]


@router.get("/claim/{claim_id}", response_model=Optional[PaymentIntentResponse])
def get_payment_for_claim(
    claim_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    
    payment = db.query(PaymentIntent).filter(PaymentIntent.claim_id == claim_id).first()
    if not payment:
        return None
    
    return _to_payment_response(payment)


@router.get("/{payment_id}", response_model=PaymentIntentResponse)
def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    payment = db.query(PaymentIntent).filter(PaymentIntent.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    
    return _to_payment_response(payment)


@router.post("/{payment_id}/retry", response_model=ProcessPaymentResponse)
def retry_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    payment = db.query(PaymentIntent).filter(PaymentIntent.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")
    
    if payment.status != PaymentIntentStatus.FAILED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed payments (current status: {payment.status})"
        )
    
    service = PaymentOrchestrationService()
    
    try:
        new_payment = service.retry_failed_payment(db, payment, current_user.id)
        db.commit()
        db.refresh(new_payment)
        
        success = new_payment.status == PaymentIntentStatus.CONFIRMED.value
        message = "Payment confirmed successfully" if success else f"Payment failed: {new_payment.failure_code}"
        
        return ProcessPaymentResponse(
            payment_intent=_to_payment_response(new_payment),
            success=success,
            message=message,
        )
    except InsufficientFundsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/ledger/summary", response_model=LedgerSummaryResponse)
def get_ledger_summary(
    currency: str = Query("USD", description="Currency code"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    summary = LedgerService.get_ledger_summary(db, currency)
    return LedgerSummaryResponse(**summary)


@router.post("/ledger/seed", response_model=LedgerSummaryResponse)
def seed_capital(
    request: SeedCapitalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    from ..models.ledger import LedgerAccountType, LedgerEntryDirection, LedgerEntryStatus, LedgerEntryRelatedType
    import uuid
    
    if request.amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    cash_account = LedgerService.get_or_create_account(
        db, LedgerAccountType.CAPITAL_CASH, None, request.currency
    )
    
    adjustment_id = uuid.uuid4()
    idempotency_key = f"seed:{adjustment_id}"
    
    try:
        LedgerService.create_entry(
            db=db,
            account=cash_account,
            direction=LedgerEntryDirection.CREDIT,
            amount_cents=request.amount_cents,
            related_type=LedgerEntryRelatedType.ADJUSTMENT,
            related_id=adjustment_id,
            idempotency_key=idempotency_key,
            status=LedgerEntryStatus.POSTED,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    
    summary = LedgerService.get_ledger_summary(db, request.currency)
    return LedgerSummaryResponse(**summary)


class CancelPaymentRequest(BaseModel):
    reason: str = "Cancelled by admin"


class ResolvePaymentRequest(BaseModel):
    resolution_note: str = "Manually resolved"


@router.post("/{payment_id}/cancel", response_model=ProcessPaymentResponse)
def cancel_payment(
    payment_id: UUID,
    request: CancelPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    payment = db.query(PaymentIntent).filter(PaymentIntent.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")

    if payment.status not in [PaymentIntentStatus.FAILED.value, PaymentIntentStatus.QUEUED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Can only cancel failed or queued payments (current: {payment.status})"
        )

    claim = db.query(Claim).filter(Claim.id == payment.claim_id).first()
    if claim:
        claim.payment_exception = False
        claim.exception_code = None
        if claim.status == ClaimStatus.PAYMENT_EXCEPTION.value:
            claim.status = ClaimStatus.DECLINED.value

    payment.status = PaymentIntentStatus.FAILED.value
    payment.failure_code = "CANCELLED"
    payment.failure_message = request.reason

    AuditService.log_event(
        db=db,
        claim_id=payment.claim_id,
        actor_user_id=current_user.id,
        action="PAYMENT_CANCELLED",
        metadata={
            "payment_intent_id": str(payment.id),
            "reason": request.reason,
        },
    )

    db.commit()
    db.refresh(payment)

    return ProcessPaymentResponse(
        payment_intent=_to_payment_response(payment),
        success=False,
        message=f"Payment cancelled: {request.reason}",
    )


@router.post("/{payment_id}/resolve", response_model=ProcessPaymentResponse)
def resolve_payment(
    payment_id: UUID,
    request: ResolvePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_user),
):
    payment = db.query(PaymentIntent).filter(PaymentIntent.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment {payment_id} not found")

    if payment.status != PaymentIntentStatus.FAILED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Can only resolve failed payments (current: {payment.status})"
        )

    claim = db.query(Claim).filter(Claim.id == payment.claim_id).first()
    if claim:
        claim.payment_exception = False
        claim.exception_code = None
        if claim.status == ClaimStatus.PAYMENT_EXCEPTION.value:
            claim.status = ClaimStatus.APPROVED.value

    AuditService.log_event(
        db=db,
        claim_id=payment.claim_id,
        actor_user_id=current_user.id,
        action="PAYMENT_RESOLVED",
        metadata={
            "payment_intent_id": str(payment.id),
            "resolution_note": request.resolution_note,
        },
    )

    db.commit()
    db.refresh(payment)

    return ProcessPaymentResponse(
        payment_intent=_to_payment_response(payment),
        success=True,
        message=f"Payment resolved: {request.resolution_note}",
    )


def _to_payment_response(payment: PaymentIntent) -> PaymentIntentResponse:
    return PaymentIntentResponse(
        id=payment.id,
        claim_id=payment.claim_id,
        practice_id=payment.practice_id,
        amount_cents=payment.amount_cents,
        currency=payment.currency,
        status=payment.status,
        idempotency_key=payment.idempotency_key,
        provider=payment.provider,
        provider_reference=payment.provider_reference,
        failure_code=payment.failure_code,
        failure_message=payment.failure_message,
        sent_at=payment.sent_at.isoformat() if payment.sent_at else None,
        confirmed_at=payment.confirmed_at.isoformat() if payment.confirmed_at else None,
        created_at=payment.created_at.isoformat(),
        updated_at=payment.updated_at.isoformat(),
    )
