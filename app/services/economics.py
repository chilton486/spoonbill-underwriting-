import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_

from ..models.ledger import (
    LedgerAccount, LedgerAccountType, LedgerEntry,
    LedgerEntryDirection, LedgerEntryStatus,
)
from ..models.payment import PaymentIntent, PaymentIntentStatus
from ..models.claim import Claim, ClaimStatus
from ..models.practice import Practice

logger = logging.getLogger(__name__)


class EconomicsService:
    @staticmethod
    def get_liquidity_summary(db: Session, currency: str = "USD") -> dict:
        cash_account = db.query(LedgerAccount).filter(
            LedgerAccount.account_type == LedgerAccountType.CAPITAL_CASH.value,
            LedgerAccount.practice_id.is_(None),
            LedgerAccount.currency == currency,
        ).first()

        clearing_account = db.query(LedgerAccount).filter(
            LedgerAccount.account_type == LedgerAccountType.PAYMENT_CLEARING.value,
            LedgerAccount.practice_id.is_(None),
            LedgerAccount.currency == currency,
        ).first()

        def balance(account):
            if not account:
                return 0
            return db.query(
                func.coalesce(func.sum(case(
                    (LedgerEntry.direction == LedgerEntryDirection.CREDIT.value, LedgerEntry.amount_cents),
                    else_=-LedgerEntry.amount_cents,
                )), 0)
            ).filter(
                LedgerEntry.account_id == account.id,
                LedgerEntry.status != LedgerEntryStatus.REVERSED.value,
            ).scalar() or 0

        available_cash = balance(cash_account)
        in_clearing = balance(clearing_account)

        reserved = db.query(
            func.coalesce(func.sum(PaymentIntent.amount_cents), 0)
        ).filter(
            PaymentIntent.status == PaymentIntentStatus.QUEUED.value,
            PaymentIntent.currency == currency,
        ).scalar() or 0

        in_flight = db.query(
            func.coalesce(func.sum(PaymentIntent.amount_cents), 0)
        ).filter(
            PaymentIntent.status == PaymentIntentStatus.SENT.value,
            PaymentIntent.currency == currency,
        ).scalar() or 0

        settled = db.query(
            func.coalesce(func.sum(PaymentIntent.amount_cents), 0)
        ).filter(
            PaymentIntent.status == PaymentIntentStatus.CONFIRMED.value,
            PaymentIntent.currency == currency,
        ).scalar() or 0

        total_payable = db.query(
            func.coalesce(func.sum(case(
                (LedgerEntry.direction == LedgerEntryDirection.CREDIT.value, LedgerEntry.amount_cents),
                else_=-LedgerEntry.amount_cents,
            )), 0)
        ).join(LedgerAccount).filter(
            LedgerAccount.account_type == LedgerAccountType.PRACTICE_PAYABLE.value,
            LedgerEntry.status != LedgerEntryStatus.REVERSED.value,
        ).scalar() or 0

        return {
            "currency": currency,
            "available_cash_cents": available_cash,
            "reserved_cents": reserved,
            "in_flight_cents": in_flight,
            "settled_cents": settled,
            "in_clearing_cents": in_clearing,
            "total_practice_payable_cents": total_payable,
        }

    @staticmethod
    def get_exposure(db: Session) -> dict:
        rows = db.query(
            PaymentIntent.practice_id,
            Practice.name,
            func.count(PaymentIntent.id).label("count"),
            func.sum(PaymentIntent.amount_cents).label("total_cents"),
        ).join(Practice, PaymentIntent.practice_id == Practice.id).filter(
            PaymentIntent.status.in_([
                PaymentIntentStatus.QUEUED.value,
                PaymentIntentStatus.SENT.value,
                PaymentIntentStatus.CONFIRMED.value,
            ])
        ).group_by(PaymentIntent.practice_id, Practice.name).all()

        by_practice = []
        for row in rows:
            by_practice.append({
                "practice_id": row.practice_id,
                "practice_name": row.name,
                "payment_count": row.count,
                "total_funded_cents": row.total_cents or 0,
            })

        now = datetime.utcnow()
        buckets = [
            ("0-30d", now - timedelta(days=30), now),
            ("31-60d", now - timedelta(days=60), now - timedelta(days=30)),
            ("61-90d", now - timedelta(days=90), now - timedelta(days=60)),
            ("90d+", None, now - timedelta(days=90)),
        ]

        aging = []
        for label, start, end in buckets:
            q = db.query(
                func.count(Claim.id),
                func.coalesce(func.sum(Claim.amount_cents), 0),
            ).filter(
                Claim.status.in_([
                    ClaimStatus.APPROVED.value,
                    ClaimStatus.PAID.value,
                    ClaimStatus.COLLECTING.value,
                ])
            )
            if start:
                q = q.filter(Claim.created_at >= start)
            q = q.filter(Claim.created_at < end)
            count, total = q.first()
            aging.append({
                "bucket": label,
                "claim_count": count or 0,
                "total_cents": total or 0,
            })

        top_payers = db.query(
            Claim.payer,
            func.count(Claim.id).label("count"),
            func.sum(Claim.amount_cents).label("total_cents"),
        ).filter(
            Claim.status.in_([
                ClaimStatus.APPROVED.value,
                ClaimStatus.PAID.value,
                ClaimStatus.COLLECTING.value,
            ])
        ).group_by(Claim.payer).order_by(func.sum(Claim.amount_cents).desc()).limit(10).all()

        concentration = [
            {"payer": r.payer, "claim_count": r.count, "total_cents": r.total_cents or 0}
            for r in top_payers
        ]

        return {
            "by_practice": sorted(by_practice, key=lambda x: x["total_funded_cents"], reverse=True),
            "aging_buckets": aging,
            "concentration": concentration,
        }

    @staticmethod
    def get_payment_intents_board(
        db: Session,
        status_filter: Optional[str] = None,
        practice_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        q = db.query(PaymentIntent).join(Practice, PaymentIntent.practice_id == Practice.id)

        if status_filter:
            q = q.filter(PaymentIntent.status == status_filter)
        if practice_id:
            q = q.filter(PaymentIntent.practice_id == practice_id)

        total = q.count()

        items = q.order_by(PaymentIntent.created_at.desc()).offset(offset).limit(limit).all()

        status_counts = dict(
            db.query(PaymentIntent.status, func.count(PaymentIntent.id))
            .group_by(PaymentIntent.status).all()
        )

        results = []
        for pi in items:
            results.append({
                "id": str(pi.id),
                "claim_id": pi.claim_id,
                "practice_id": pi.practice_id,
                "practice_name": pi.practice.name if pi.practice else None,
                "amount_cents": pi.amount_cents,
                "currency": pi.currency,
                "status": pi.status,
                "provider": pi.provider,
                "failure_code": pi.failure_code,
                "failure_message": pi.failure_message,
                "created_at": pi.created_at.isoformat(),
                "updated_at": pi.updated_at.isoformat(),
            })

        return {
            "items": results,
            "total": total,
            "status_counts": {
                "QUEUED": status_counts.get(PaymentIntentStatus.QUEUED.value, 0),
                "SENT": status_counts.get(PaymentIntentStatus.SENT.value, 0),
                "CONFIRMED": status_counts.get(PaymentIntentStatus.CONFIRMED.value, 0),
                "FAILED": status_counts.get(PaymentIntentStatus.FAILED.value, 0),
            },
        }

    @staticmethod
    def get_practice_exposure(db: Session, practice_id: int) -> dict:
        practice = db.query(Practice).filter(Practice.id == practice_id).first()
        if not practice:
            return {}

        funded_outstanding = db.query(
            func.coalesce(func.sum(PaymentIntent.amount_cents), 0)
        ).filter(
            PaymentIntent.practice_id == practice_id,
            PaymentIntent.status.in_([
                PaymentIntentStatus.QUEUED.value,
                PaymentIntentStatus.SENT.value,
            ]),
        ).scalar() or 0

        total_confirmed = db.query(
            func.coalesce(func.sum(PaymentIntent.amount_cents), 0)
        ).filter(
            PaymentIntent.practice_id == practice_id,
            PaymentIntent.status == PaymentIntentStatus.CONFIRMED.value,
        ).scalar() or 0

        active_claims = db.query(func.count(Claim.id)).filter(
            Claim.practice_id == practice_id,
            Claim.status.in_([
                ClaimStatus.APPROVED.value,
                ClaimStatus.PAID.value,
                ClaimStatus.COLLECTING.value,
            ]),
        ).scalar() or 0

        exceptions = db.query(func.count(Claim.id)).filter(
            Claim.practice_id == practice_id,
            Claim.status == ClaimStatus.PAYMENT_EXCEPTION.value,
        ).scalar() or 0

        return {
            "practice_id": practice_id,
            "practice_name": practice.name,
            "funding_limit_cents": practice.funding_limit_cents,
            "funded_outstanding_cents": funded_outstanding,
            "total_confirmed_cents": total_confirmed,
            "active_claim_count": active_claims,
            "exception_count": exceptions,
            "utilization_pct": round(
                funded_outstanding / practice.funding_limit_cents * 100, 1
            ) if practice.funding_limit_cents and practice.funding_limit_cents > 0 else 0,
        }
