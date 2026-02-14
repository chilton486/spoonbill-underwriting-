import logging
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..models.claim import Claim, ClaimStatus
from ..models.payment import PaymentIntent, PaymentIntentStatus, PaymentProvider
from ..providers.base import PaymentProviderBase, PaymentResultStatus
from ..providers.simulated import SimulatedProvider
from .ledger import LedgerService, LedgerError, InsufficientFundsError, DuplicateEntryError
from .audit import AuditService

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    pass


class PaymentAlreadyExistsError(PaymentError):
    pass


class InvalidClaimStateError(PaymentError):
    pass


class PaymentOrchestrationService:
    def __init__(self, provider: Optional[PaymentProviderBase] = None):
        self.provider = provider or SimulatedProvider(deterministic=False)

    def create_payment_intent(
        self,
        db: Session,
        claim: Claim,
        user_id: Optional[int] = None,
    ) -> PaymentIntent:
        if claim.status != ClaimStatus.APPROVED.value:
            raise InvalidClaimStateError(
                f"Cannot create payment for claim {claim.id} in status {claim.status}. "
                f"Claim must be in APPROVED status."
            )
        
        idempotency_key = PaymentIntent.generate_idempotency_key(claim.id)
        
        existing = db.query(PaymentIntent).filter(
            PaymentIntent.idempotency_key == idempotency_key
        ).first()
        if existing:
            logger.info(f"Payment intent already exists for claim {claim.id}: {existing.id}")
            return existing
        
        existing_by_claim = db.query(PaymentIntent).filter(
            PaymentIntent.claim_id == claim.id
        ).first()
        if existing_by_claim:
            logger.warning(f"Payment intent already exists for claim {claim.id} with different key")
            raise PaymentAlreadyExistsError(f"Payment already exists for claim {claim.id}")
        
        payment_intent = PaymentIntent(
            claim_id=claim.id,
            practice_id=claim.practice_id,
            amount_cents=claim.amount_cents,
            currency="USD",
            status=PaymentIntentStatus.QUEUED.value,
            idempotency_key=idempotency_key,
            provider=PaymentProvider.SIMULATED.value,
        )
        
        try:
            db.add(payment_intent)
            db.flush()
        except IntegrityError as e:
            db.rollback()
            logger.warning(f"IntegrityError creating payment intent: {e}")
            existing = db.query(PaymentIntent).filter(
                PaymentIntent.claim_id == claim.id
            ).first()
            if existing:
                return existing
            raise PaymentError(f"Failed to create payment intent: {e}")
        
        try:
            LedgerService.reserve_funds(db, payment_intent, payment_intent.amount_cents)
        except InsufficientFundsError as e:
            db.rollback()
            logger.error(f"Insufficient funds for payment {payment_intent.id}: {e}")
            raise
        except DuplicateEntryError:
            logger.info(f"Ledger entries already exist for payment {payment_intent.id}")
        
        AuditService.log_event(
            db=db,
            claim_id=claim.id,
            actor_user_id=user_id,
            action="PAYMENT_INTENT_CREATED",
            metadata={
                "payment_intent_id": str(payment_intent.id),
                "amount_cents": payment_intent.amount_cents,
                "idempotency_key": idempotency_key,
            },
        )
        
        logger.info(f"Created payment intent {payment_intent.id} for claim {claim.id}")
        return payment_intent

    def send_payment(
        self,
        db: Session,
        payment_intent: PaymentIntent,
        user_id: Optional[int] = None,
    ) -> PaymentIntent:
        if payment_intent.status != PaymentIntentStatus.QUEUED.value:
            if payment_intent.status in [PaymentIntentStatus.SENT.value, PaymentIntentStatus.CONFIRMED.value]:
                logger.info(f"Payment {payment_intent.id} already sent/confirmed")
                return payment_intent
            raise PaymentError(
                f"Cannot send payment {payment_intent.id} in status {payment_intent.status}"
            )
        
        result = self.provider.send_payment(
            payment_intent_id=str(payment_intent.id),
            amount_cents=payment_intent.amount_cents,
            currency=payment_intent.currency,
            recipient_practice_id=payment_intent.practice_id,
            idempotency_key=payment_intent.idempotency_key,
        )
        
        payment_intent.provider_reference = result.provider_reference
        payment_intent.sent_at = datetime.utcnow()
        
        if result.status == PaymentResultStatus.SUCCESS:
            payment_intent.status = PaymentIntentStatus.SENT.value
            
            AuditService.log_event(
                db=db,
                claim_id=payment_intent.claim_id,
                actor_user_id=user_id,
                action="PAYMENT_SENT",
                metadata={
                    "payment_intent_id": str(payment_intent.id),
                    "provider_reference": result.provider_reference,
                },
            )
            logger.info(f"Payment {payment_intent.id} sent successfully")
            
        elif result.status == PaymentResultStatus.FAILED:
            self._handle_payment_failure(db, payment_intent, result.failure_code, result.failure_message, user_id)
        
        return payment_intent

    def confirm_payment(
        self,
        db: Session,
        payment_intent: PaymentIntent,
        user_id: Optional[int] = None,
    ) -> PaymentIntent:
        if payment_intent.status == PaymentIntentStatus.CONFIRMED.value:
            logger.info(f"Payment {payment_intent.id} already confirmed")
            return payment_intent
        
        if payment_intent.status != PaymentIntentStatus.SENT.value:
            raise PaymentError(
                f"Cannot confirm payment {payment_intent.id} in status {payment_intent.status}"
            )
        
        try:
            LedgerService.confirm_payment(db, payment_intent)
        except DuplicateEntryError:
            logger.info(f"Settlement entries already exist for payment {payment_intent.id}")
        
        payment_intent.status = PaymentIntentStatus.CONFIRMED.value
        payment_intent.confirmed_at = datetime.utcnow()
        
        claim = db.query(Claim).filter(Claim.id == payment_intent.claim_id).first()
        if claim and claim.status == ClaimStatus.APPROVED.value:
            claim.status = ClaimStatus.PAID.value
        
        AuditService.log_event(
            db=db,
            claim_id=payment_intent.claim_id,
            actor_user_id=user_id,
            action="PAYMENT_CONFIRMED",
            from_status=ClaimStatus.APPROVED.value if claim else None,
            to_status=ClaimStatus.PAID.value if claim else None,
            metadata={
                "payment_intent_id": str(payment_intent.id),
                "amount_cents": payment_intent.amount_cents,
                "provider_reference": payment_intent.provider_reference,
            },
        )
        
        logger.info(f"Payment {payment_intent.id} confirmed, claim {payment_intent.claim_id} marked as PAID")
        return payment_intent

    def fail_payment(
        self,
        db: Session,
        payment_intent: PaymentIntent,
        failure_code: str,
        failure_message: str,
        user_id: Optional[int] = None,
    ) -> PaymentIntent:
        if payment_intent.status == PaymentIntentStatus.FAILED.value:
            logger.info(f"Payment {payment_intent.id} already failed")
            return payment_intent
        
        if payment_intent.status == PaymentIntentStatus.CONFIRMED.value:
            raise PaymentError(
                f"Cannot fail payment {payment_intent.id} that is already confirmed"
            )
        
        self._handle_payment_failure(db, payment_intent, failure_code, failure_message, user_id)
        return payment_intent

    def _handle_payment_failure(
        self,
        db: Session,
        payment_intent: PaymentIntent,
        failure_code: Optional[str],
        failure_message: Optional[str],
        user_id: Optional[int],
    ) -> None:
        try:
            LedgerService.release_reservation(db, payment_intent)
        except DuplicateEntryError:
            logger.info(f"Release entries already exist for payment {payment_intent.id}")
        except LedgerError as e:
            logger.error(f"Failed to release reservation for payment {payment_intent.id}: {e}")
        
        payment_intent.status = PaymentIntentStatus.FAILED.value
        payment_intent.failure_code = failure_code
        payment_intent.failure_message = failure_message
        
        claim = db.query(Claim).filter(Claim.id == payment_intent.claim_id).first()
        if claim:
            claim.payment_exception = True
            claim.exception_code = failure_code
            if claim.status == ClaimStatus.APPROVED.value:
                claim.status = ClaimStatus.PAYMENT_EXCEPTION.value
        
        AuditService.log_event(
            db=db,
            claim_id=payment_intent.claim_id,
            actor_user_id=user_id,
            action="PAYMENT_FAILED",
            metadata={
                "payment_intent_id": str(payment_intent.id),
                "failure_code": failure_code,
                "failure_message": failure_message,
            },
        )
        
        logger.warning(f"Payment {payment_intent.id} failed: {failure_code} - {failure_message}")

    def process_approved_claim(
        self,
        db: Session,
        claim: Claim,
        user_id: Optional[int] = None,
    ) -> Tuple[PaymentIntent, bool]:
        payment_intent = self.create_payment_intent(db, claim, user_id)
        
        if payment_intent.status != PaymentIntentStatus.QUEUED.value:
            return payment_intent, payment_intent.status == PaymentIntentStatus.CONFIRMED.value
        
        payment_intent = self.send_payment(db, payment_intent, user_id)
        
        if payment_intent.status == PaymentIntentStatus.SENT.value:
            payment_intent = self.confirm_payment(db, payment_intent, user_id)
        
        success = payment_intent.status == PaymentIntentStatus.CONFIRMED.value
        return payment_intent, success

    def get_payment_for_claim(self, db: Session, claim_id: int) -> Optional[PaymentIntent]:
        return db.query(PaymentIntent).filter(PaymentIntent.claim_id == claim_id).first()

    def retry_failed_payment(
        self,
        db: Session,
        payment_intent: PaymentIntent,
        user_id: Optional[int] = None,
    ) -> PaymentIntent:
        if payment_intent.status != PaymentIntentStatus.FAILED.value:
            raise PaymentError(
                f"Cannot retry payment {payment_intent.id} in status {payment_intent.status}"
            )
        
        claim = db.query(Claim).filter(Claim.id == payment_intent.claim_id).first()
        if not claim:
            raise PaymentError(f"Claim {payment_intent.claim_id} not found")
        
        claim.payment_exception = False
        claim.exception_code = None
        
        db.delete(payment_intent)
        db.flush()
        
        new_payment, success = self.process_approved_claim(db, claim, user_id)
        
        AuditService.log_event(
            db=db,
            claim_id=claim.id,
            actor_user_id=user_id,
            action="PAYMENT_RETRIED",
            metadata={
                "old_payment_intent_id": str(payment_intent.id),
                "new_payment_intent_id": str(new_payment.id),
                "success": success,
            },
        )
        
        return new_payment
