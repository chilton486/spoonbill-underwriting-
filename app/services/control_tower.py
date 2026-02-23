import logging
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models.payment import PaymentIntent, PaymentIntentStatus
from ..models.claim import Claim, ClaimStatus
from ..models.practice import Practice
from ..models.ledger import (
    LedgerAccount, LedgerAccountType, LedgerEntry,
    LedgerEntryDirection, LedgerEntryStatus,
)

logger = logging.getLogger(__name__)


class ControlTowerService:
    @staticmethod
    def get_control_tower(db: Session, currency: str = "USD") -> Dict[str, Any]:
        now = datetime.utcnow()

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

        def ledger_balance(account):
            if not account:
                return 0
            from sqlalchemy import case
            return db.query(
                func.coalesce(func.sum(case(
                    (LedgerEntry.direction == LedgerEntryDirection.CREDIT.value, LedgerEntry.amount_cents),
                    else_=-LedgerEntry.amount_cents,
                )), 0)
            ).filter(
                LedgerEntry.account_id == account.id,
                LedgerEntry.status != LedgerEntryStatus.REVERSED.value,
            ).scalar() or 0

        cash_balance = ledger_balance(cash_account)
        clearing_balance = ledger_balance(clearing_account)

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

        liquidity_by_facility = [
            {
                "facility": "Primary Operating",
                "cash_cents": cash_balance,
                "reserved_cents": reserved,
                "inflight_cents": in_flight,
                "settled_cents": settled,
                "as_of": now.isoformat(),
            },
            {
                "facility": "Clearing",
                "cash_cents": clearing_balance,
                "reserved_cents": 0,
                "inflight_cents": 0,
                "settled_cents": 0,
                "as_of": now.isoformat(),
            },
        ]

        approved_not_sent = db.query(
            func.coalesce(func.sum(Claim.amount_cents), 0)
        ).filter(
            Claim.status == ClaimStatus.APPROVED.value,
        ).scalar() or 0

        sent_not_confirmed = in_flight

        exception_amount = db.query(
            func.coalesce(func.sum(Claim.amount_cents), 0)
        ).filter(
            Claim.status == ClaimStatus.PAYMENT_EXCEPTION.value,
        ).scalar() or 0

        commitments = {
            "approved_not_sent_cents": approved_not_sent,
            "sent_not_confirmed_cents": sent_not_confirmed,
            "exception_amount_cents": exception_amount,
        }

        last_entry = db.query(func.max(LedgerEntry.created_at)).scalar()
        staleness_seconds = int((now - last_entry).total_seconds()) if last_entry else None

        freshness = {
            "updated_at": last_entry.isoformat() if last_entry else None,
            "staleness_seconds": staleness_seconds,
        }

        top_practices = db.query(
            Practice.id,
            Practice.name,
            func.coalesce(func.sum(PaymentIntent.amount_cents), 0).label("total_cents"),
        ).join(PaymentIntent, PaymentIntent.practice_id == Practice.id).filter(
            PaymentIntent.status.in_([
                PaymentIntentStatus.QUEUED.value,
                PaymentIntentStatus.SENT.value,
                PaymentIntentStatus.CONFIRMED.value,
            ]),
        ).group_by(Practice.id, Practice.name).order_by(
            func.sum(PaymentIntent.amount_cents).desc()
        ).limit(5).all()

        top_payers = db.query(
            Claim.payer,
            func.count(Claim.id).label("count"),
            func.coalesce(func.sum(Claim.amount_cents), 0).label("total_cents"),
        ).filter(
            Claim.status.in_([
                ClaimStatus.APPROVED.value,
                ClaimStatus.PAID.value,
                ClaimStatus.COLLECTING.value,
            ]),
        ).group_by(Claim.payer).order_by(
            func.sum(Claim.amount_cents).desc()
        ).limit(5).all()

        top_concentrations = {
            "practices": [
                {"practice_id": r.id, "practice_name": r.name, "total_cents": r.total_cents}
                for r in top_practices
            ],
            "payers": [
                {"payer": r.payer, "claim_count": r.count, "total_cents": r.total_cents}
                for r in top_payers
            ],
        }

        alerts = ControlTowerService._compute_alerts(
            db, cash_balance, reserved, in_flight, exception_amount, staleness_seconds
        )

        available_for_funding = cash_balance - reserved
        can_fund = available_for_funding > 0

        return {
            "currency": currency,
            "liquidity_by_facility": liquidity_by_facility,
            "commitments": commitments,
            "freshness": freshness,
            "top_concentrations": top_concentrations,
            "alerts": alerts,
            "can_fund_now": {
                "value": can_fund,
                "available_cents": available_for_funding,
                "reason": None if can_fund else "Insufficient available cash after reservations",
            },
            "computed_at": now.isoformat(),
        }

    @staticmethod
    def _compute_alerts(
        db: Session,
        cash: int,
        reserved: int,
        in_flight: int,
        exception_amount: int,
        staleness_seconds,
    ) -> List[Dict[str, Any]]:
        alerts = []

        if cash - reserved <= 0:
            alerts.append({
                "severity": "critical",
                "title": "No available cash for new funding",
                "detail": f"Cash ${cash/100:,.2f} minus reserved ${reserved/100:,.2f} = ${(cash-reserved)/100:,.2f}",
                "drilldown": "/economics",
            })

        exception_count = db.query(func.count(Claim.id)).filter(
            Claim.status == ClaimStatus.PAYMENT_EXCEPTION.value,
        ).scalar() or 0

        if exception_count > 0:
            alerts.append({
                "severity": "high" if exception_count >= 3 else "medium",
                "title": f"{exception_count} payment exception(s) requiring attention",
                "detail": f"Total exception amount: ${exception_amount/100:,.2f}",
                "drilldown": "/exceptions",
            })

        failed_count = db.query(func.count(PaymentIntent.id)).filter(
            PaymentIntent.status == PaymentIntentStatus.FAILED.value,
        ).scalar() or 0

        if failed_count > 0:
            alerts.append({
                "severity": "high",
                "title": f"{failed_count} failed payment intent(s)",
                "detail": "Review and retry or resolve failed payments",
                "drilldown": "/payments",
            })

        if staleness_seconds is not None and staleness_seconds > 3600:
            alerts.append({
                "severity": "low",
                "title": "Ledger data may be stale",
                "detail": f"Last entry was {staleness_seconds // 60} minutes ago",
                "drilldown": "/economics",
            })

        return alerts
