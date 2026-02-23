import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..models.payment import PaymentIntent, PaymentIntentStatus
from ..models.ops import ExternalBalanceSnapshot, ExternalPaymentConfirmation
from ..services.audit import AuditService

logger = logging.getLogger(__name__)


class ReconciliationService:
    @staticmethod
    def get_summary(db: Session) -> Dict[str, Any]:
        latest_snapshots = {}
        snapshots = db.query(ExternalBalanceSnapshot).order_by(
            desc(ExternalBalanceSnapshot.as_of)
        ).limit(50).all()

        for s in snapshots:
            if s.facility not in latest_snapshots:
                latest_snapshots[s.facility] = {
                    "facility": s.facility,
                    "external_balance_cents": s.balance_cents,
                    "as_of": s.as_of.isoformat(),
                    "source": s.source,
                }

        total_queued = db.query(
            func.coalesce(func.sum(PaymentIntent.amount_cents), 0)
        ).filter(
            PaymentIntent.status == PaymentIntentStatus.QUEUED.value,
        ).scalar() or 0

        total_sent = db.query(
            func.coalesce(func.sum(PaymentIntent.amount_cents), 0)
        ).filter(
            PaymentIntent.status == PaymentIntentStatus.SENT.value,
        ).scalar() or 0

        total_confirmed = db.query(
            func.coalesce(func.sum(PaymentIntent.amount_cents), 0)
        ).filter(
            PaymentIntent.status == PaymentIntentStatus.CONFIRMED.value,
        ).scalar() or 0

        unmatched_count = db.query(func.count(ExternalPaymentConfirmation.id)).filter(
            ExternalPaymentConfirmation.resolved == "false",
        ).scalar() or 0

        return {
            "ledger_totals": {
                "queued_cents": total_queued,
                "sent_cents": total_sent,
                "confirmed_cents": total_confirmed,
            },
            "external_balances": list(latest_snapshots.values()),
            "unmatched_confirmations": unmatched_count,
            "computed_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def get_payment_intent_reconciliation(
        db: Session,
        status_filter: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        q = db.query(PaymentIntent)
        if status_filter:
            q = q.filter(PaymentIntent.status == status_filter)

        intents = q.order_by(desc(PaymentIntent.updated_at)).limit(limit).all()

        confirmations_by_pi = {}
        if intents:
            pi_ids = [pi.id for pi in intents]
            confs = db.query(ExternalPaymentConfirmation).filter(
                ExternalPaymentConfirmation.payment_intent_id.in_(pi_ids),
            ).all()
            for c in confs:
                confirmations_by_pi.setdefault(str(c.payment_intent_id), []).append({
                    "id": c.id,
                    "rail_ref": c.rail_ref,
                    "status": c.status,
                    "confirmed_at": c.confirmed_at.isoformat() if c.confirmed_at else None,
                    "resolved": c.resolved,
                    "resolution_note": c.resolution_note,
                })

        items = []
        for pi in intents:
            pi_id_str = str(pi.id)
            ext_confs = confirmations_by_pi.get(pi_id_str, [])
            matched = len(ext_confs) > 0
            mismatch = False
            if matched:
                for ec in ext_confs:
                    if ec["status"] != pi.status and ec["resolved"] == "false":
                        mismatch = True
                        break

            items.append({
                "id": pi_id_str,
                "claim_id": pi.claim_id,
                "practice_id": pi.practice_id,
                "amount_cents": pi.amount_cents,
                "ledger_status": pi.status,
                "external_confirmations": ext_confs,
                "matched": matched,
                "mismatch": mismatch,
                "created_at": pi.created_at.isoformat(),
                "updated_at": pi.updated_at.isoformat(),
            })

        return {"items": items, "total": len(items)}

    @staticmethod
    def ingest_balance(
        db: Session,
        facility: str,
        balance_cents: int,
        as_of: str,
        source: str,
    ) -> Dict[str, Any]:
        snapshot = ExternalBalanceSnapshot(
            facility=facility,
            balance_cents=balance_cents,
            as_of=datetime.fromisoformat(as_of),
            source=source,
        )
        db.add(snapshot)
        db.commit()
        return {"id": snapshot.id, "facility": facility, "balance_cents": balance_cents}

    @staticmethod
    def ingest_payment_confirmation(
        db: Session,
        payment_intent_id: str,
        rail_ref: Optional[str],
        status: str,
        confirmed_at: Optional[str],
        raw_json: Optional[dict],
    ) -> Dict[str, Any]:
        import uuid
        conf = ExternalPaymentConfirmation(
            payment_intent_id=uuid.UUID(payment_intent_id),
            rail_ref=rail_ref,
            status=status,
            confirmed_at=datetime.fromisoformat(confirmed_at) if confirmed_at else None,
            raw_json=json.dumps(raw_json) if raw_json else None,
        )
        db.add(conf)
        db.commit()
        return {"id": conf.id, "payment_intent_id": payment_intent_id, "status": status}

    @staticmethod
    def resolve_mismatch(
        db: Session,
        confirmation_id: int,
        resolution_note: str,
        actor_user_id: int,
    ) -> Dict[str, Any]:
        conf = db.query(ExternalPaymentConfirmation).filter(
            ExternalPaymentConfirmation.id == confirmation_id,
        ).first()
        if not conf:
            return {"success": False, "error": "Confirmation not found"}

        conf.resolved = "true"
        conf.resolution_note = resolution_note

        AuditService.log_event(
            db=db,
            claim_id=None,
            action="RECONCILIATION_RESOLVED",
            actor_user_id=actor_user_id,
            metadata={
                "confirmation_id": confirmation_id,
                "payment_intent_id": str(conf.payment_intent_id),
                "resolution_note": resolution_note,
            },
        )
        db.commit()
        return {"success": True, "id": confirmation_id}
