import uuid
import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.ledger import (
    LedgerAccount, LedgerAccountType, LedgerEntry, 
    LedgerEntryDirection, LedgerEntryStatus, LedgerEntryRelatedType
)
from ..models.payment import PaymentIntent

logger = logging.getLogger(__name__)


class LedgerError(Exception):
    pass


class InsufficientFundsError(LedgerError):
    pass


class DuplicateEntryError(LedgerError):
    pass


class LedgerService:
    @staticmethod
    def get_account(db: Session, account_type: LedgerAccountType, practice_id: Optional[int] = None, currency: str = "USD") -> Optional[LedgerAccount]:
        return db.query(LedgerAccount).filter(
            LedgerAccount.account_type == account_type.value,
            LedgerAccount.practice_id == practice_id,
            LedgerAccount.currency == currency,
        ).first()

    @staticmethod
    def get_or_create_account(db: Session, account_type: LedgerAccountType, practice_id: Optional[int] = None, currency: str = "USD") -> LedgerAccount:
        account = LedgerService.get_account(db, account_type, practice_id, currency)
        if account:
            return account
        
        account = LedgerAccount(
            account_type=account_type.value,
            practice_id=practice_id,
            currency=currency,
        )
        db.add(account)
        db.flush()
        logger.info(f"Created ledger account: type={account_type.value}, practice_id={practice_id}, currency={currency}")
        return account

    @staticmethod
    def compute_balance(db: Session, account: LedgerAccount, status_filter: Optional[LedgerEntryStatus] = None) -> int:
        query = db.query(
            func.coalesce(
                func.sum(
                    func.case(
                        (LedgerEntry.direction == LedgerEntryDirection.CREDIT.value, LedgerEntry.amount_cents),
                        else_=-LedgerEntry.amount_cents
                    )
                ),
                0
            )
        ).filter(LedgerEntry.account_id == account.id)
        
        if status_filter:
            query = query.filter(LedgerEntry.status == status_filter.value)
        else:
            query = query.filter(LedgerEntry.status != LedgerEntryStatus.REVERSED.value)
        
        return query.scalar() or 0

    @staticmethod
    def get_available_capital(db: Session, currency: str = "USD") -> int:
        account = LedgerService.get_account(db, LedgerAccountType.CAPITAL_CASH, None, currency)
        if not account:
            return 0
        return LedgerService.compute_balance(db, account)

    @staticmethod
    def create_entry(
        db: Session,
        account: LedgerAccount,
        direction: LedgerEntryDirection,
        amount_cents: int,
        related_type: LedgerEntryRelatedType,
        related_id: uuid.UUID,
        idempotency_key: str,
        claim_id: Optional[int] = None,
        status: LedgerEntryStatus = LedgerEntryStatus.PENDING,
    ) -> LedgerEntry:
        if amount_cents <= 0:
            raise LedgerError(f"Amount must be positive, got {amount_cents}")
        
        existing = db.query(LedgerEntry).filter(LedgerEntry.idempotency_key == idempotency_key).first()
        if existing:
            logger.warning(f"Duplicate ledger entry attempted: {idempotency_key}")
            raise DuplicateEntryError(f"Ledger entry already exists: {idempotency_key}")
        
        entry = LedgerEntry(
            account_id=account.id,
            direction=direction.value,
            amount_cents=amount_cents,
            related_type=related_type.value,
            related_id=related_id,
            claim_id=claim_id,
            status=status.value,
            idempotency_key=idempotency_key,
        )
        db.add(entry)
        logger.info(f"Created ledger entry: account={account.account_type}, direction={direction.value}, amount={amount_cents}, key={idempotency_key}")
        return entry

    @staticmethod
    def reserve_funds(
        db: Session,
        payment_intent: PaymentIntent,
        amount_cents: int,
    ) -> Tuple[LedgerEntry, LedgerEntry]:
        cash_account = LedgerService.get_account(db, LedgerAccountType.CAPITAL_CASH)
        if not cash_account:
            raise LedgerError("CAPITAL_CASH account not found")
        
        clearing_account = LedgerService.get_account(db, LedgerAccountType.PAYMENT_CLEARING)
        if not clearing_account:
            raise LedgerError("PAYMENT_CLEARING account not found")
        
        available = LedgerService.compute_balance(db, cash_account)
        if available < amount_cents:
            raise InsufficientFundsError(f"Insufficient funds: available={available}, required={amount_cents}")
        
        debit_key = f"payment:{payment_intent.id}:reserve:debit"
        credit_key = f"payment:{payment_intent.id}:reserve:credit"
        
        debit_entry = LedgerService.create_entry(
            db=db,
            account=cash_account,
            direction=LedgerEntryDirection.DEBIT,
            amount_cents=amount_cents,
            related_type=LedgerEntryRelatedType.PAYMENT_INTENT,
            related_id=payment_intent.id,
            claim_id=payment_intent.claim_id,
            idempotency_key=debit_key,
            status=LedgerEntryStatus.PENDING,
        )
        
        credit_entry = LedgerService.create_entry(
            db=db,
            account=clearing_account,
            direction=LedgerEntryDirection.CREDIT,
            amount_cents=amount_cents,
            related_type=LedgerEntryRelatedType.PAYMENT_INTENT,
            related_id=payment_intent.id,
            claim_id=payment_intent.claim_id,
            idempotency_key=credit_key,
            status=LedgerEntryStatus.PENDING,
        )
        
        logger.info(f"Reserved {amount_cents} cents for payment_intent {payment_intent.id}")
        return debit_entry, credit_entry

    @staticmethod
    def confirm_payment(
        db: Session,
        payment_intent: PaymentIntent,
    ) -> Tuple[LedgerEntry, LedgerEntry]:
        reserve_entries = db.query(LedgerEntry).filter(
            LedgerEntry.related_id == payment_intent.id,
            LedgerEntry.related_type == LedgerEntryRelatedType.PAYMENT_INTENT.value,
            LedgerEntry.status == LedgerEntryStatus.PENDING.value,
        ).all()
        
        for entry in reserve_entries:
            entry.status = LedgerEntryStatus.POSTED.value
        
        clearing_account = LedgerService.get_account(db, LedgerAccountType.PAYMENT_CLEARING)
        if not clearing_account:
            raise LedgerError("PAYMENT_CLEARING account not found")
        
        payable_account = LedgerService.get_or_create_account(
            db, LedgerAccountType.PRACTICE_PAYABLE, payment_intent.practice_id
        )
        
        debit_key = f"payment:{payment_intent.id}:settle:debit"
        credit_key = f"payment:{payment_intent.id}:settle:credit"
        
        debit_entry = LedgerService.create_entry(
            db=db,
            account=clearing_account,
            direction=LedgerEntryDirection.DEBIT,
            amount_cents=payment_intent.amount_cents,
            related_type=LedgerEntryRelatedType.PAYMENT_INTENT,
            related_id=payment_intent.id,
            claim_id=payment_intent.claim_id,
            idempotency_key=debit_key,
            status=LedgerEntryStatus.POSTED,
        )
        
        credit_entry = LedgerService.create_entry(
            db=db,
            account=payable_account,
            direction=LedgerEntryDirection.CREDIT,
            amount_cents=payment_intent.amount_cents,
            related_type=LedgerEntryRelatedType.PAYMENT_INTENT,
            related_id=payment_intent.id,
            claim_id=payment_intent.claim_id,
            idempotency_key=credit_key,
            status=LedgerEntryStatus.POSTED,
        )
        
        logger.info(f"Confirmed payment {payment_intent.id}, settled {payment_intent.amount_cents} cents to practice {payment_intent.practice_id}")
        return debit_entry, credit_entry

    @staticmethod
    def release_reservation(
        db: Session,
        payment_intent: PaymentIntent,
    ) -> Tuple[LedgerEntry, LedgerEntry]:
        reserve_entries = db.query(LedgerEntry).filter(
            LedgerEntry.related_id == payment_intent.id,
            LedgerEntry.related_type == LedgerEntryRelatedType.PAYMENT_INTENT.value,
            LedgerEntry.status == LedgerEntryStatus.PENDING.value,
        ).all()
        
        for entry in reserve_entries:
            entry.status = LedgerEntryStatus.REVERSED.value
        
        cash_account = LedgerService.get_account(db, LedgerAccountType.CAPITAL_CASH)
        if not cash_account:
            raise LedgerError("CAPITAL_CASH account not found")
        
        clearing_account = LedgerService.get_account(db, LedgerAccountType.PAYMENT_CLEARING)
        if not clearing_account:
            raise LedgerError("PAYMENT_CLEARING account not found")
        
        debit_key = f"payment:{payment_intent.id}:release:debit"
        credit_key = f"payment:{payment_intent.id}:release:credit"
        
        debit_entry = LedgerService.create_entry(
            db=db,
            account=clearing_account,
            direction=LedgerEntryDirection.DEBIT,
            amount_cents=payment_intent.amount_cents,
            related_type=LedgerEntryRelatedType.PAYMENT_INTENT,
            related_id=payment_intent.id,
            claim_id=payment_intent.claim_id,
            idempotency_key=debit_key,
            status=LedgerEntryStatus.POSTED,
        )
        
        credit_entry = LedgerService.create_entry(
            db=db,
            account=cash_account,
            direction=LedgerEntryDirection.CREDIT,
            amount_cents=payment_intent.amount_cents,
            related_type=LedgerEntryRelatedType.PAYMENT_INTENT,
            related_id=payment_intent.id,
            claim_id=payment_intent.claim_id,
            idempotency_key=credit_key,
            status=LedgerEntryStatus.POSTED,
        )
        
        logger.info(f"Released reservation for payment {payment_intent.id}, returned {payment_intent.amount_cents} cents to capital")
        return debit_entry, credit_entry

    @staticmethod
    def get_ledger_summary(db: Session, currency: str = "USD") -> dict:
        cash_account = LedgerService.get_account(db, LedgerAccountType.CAPITAL_CASH, None, currency)
        clearing_account = LedgerService.get_account(db, LedgerAccountType.PAYMENT_CLEARING, None, currency)
        
        cash_balance = LedgerService.compute_balance(db, cash_account) if cash_account else 0
        clearing_balance = LedgerService.compute_balance(db, clearing_account) if clearing_account else 0
        
        total_payable = db.query(
            func.coalesce(
                func.sum(
                    func.case(
                        (LedgerEntry.direction == LedgerEntryDirection.CREDIT.value, LedgerEntry.amount_cents),
                        else_=-LedgerEntry.amount_cents
                    )
                ),
                0
            )
        ).join(LedgerAccount).filter(
            LedgerAccount.account_type == LedgerAccountType.PRACTICE_PAYABLE.value,
            LedgerEntry.status != LedgerEntryStatus.REVERSED.value,
        ).scalar() or 0
        
        return {
            "currency": currency,
            "capital_cash_cents": cash_balance,
            "payment_clearing_cents": clearing_balance,
            "total_practice_payable_cents": total_payable,
        }
