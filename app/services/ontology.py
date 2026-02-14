import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.claim import Claim, ClaimStatus
from ..models.payment import PaymentIntent, PaymentIntentStatus
from ..models.ledger import LedgerEntry, LedgerEntryStatus, LedgerEntryDirection
from ..models.practice import Practice
from ..models.ontology import (
    OntologyObject,
    OntologyObjectType,
    OntologyLink,
    OntologyLinkType,
    KPIObservation,
)
from ..services.audit import AuditService


class OntologyBuilder:

    @staticmethod
    def build_practice_ontology(db: Session, practice_id: int, actor_user_id: Optional[int] = None) -> dict:
        db.query(OntologyLink).filter(OntologyLink.practice_id == practice_id).delete()
        db.query(KPIObservation).filter(KPIObservation.practice_id == practice_id).delete()
        db.query(OntologyObject).filter(OntologyObject.practice_id == practice_id).delete()
        db.flush()

        practice = db.query(Practice).filter(Practice.id == practice_id).first()
        if not practice:
            raise ValueError(f"Practice {practice_id} not found")

        object_map = {}

        practice_obj = OntologyBuilder._upsert_object(
            db, practice_id, OntologyObjectType.PRACTICE,
            f"practice:{practice_id}",
            {"name": practice.name, "status": practice.status, "funding_limit_cents": practice.funding_limit_cents},
        )
        object_map["practice"] = practice_obj

        claims = db.query(Claim).filter(Claim.practice_id == practice_id).all()

        payer_objects = {}
        procedure_objects = {}
        claim_objects = {}

        for claim in claims:
            claim_obj = OntologyBuilder._upsert_object(
                db, practice_id, OntologyObjectType.CLAIM,
                f"claim:{claim.id}",
                {
                    "claim_token": claim.claim_token,
                    "status": claim.status,
                    "amount_cents": claim.amount_cents,
                    "payer": claim.payer,
                    "patient_name": claim.patient_name,
                    "procedure_codes": claim.procedure_codes,
                    "created_at": claim.created_at.isoformat() if claim.created_at else None,
                },
            )
            claim_objects[claim.id] = claim_obj

            if claim.payer and claim.payer not in payer_objects:
                payer_obj = OntologyBuilder._upsert_object(
                    db, practice_id, OntologyObjectType.PAYER,
                    f"payer:{claim.payer}",
                    {"name": claim.payer},
                )
                payer_objects[claim.payer] = payer_obj

            if claim.payer and claim.payer in payer_objects:
                OntologyBuilder._create_link(
                    db, practice_id, OntologyLinkType.CLAIM_BILLED_TO_PAYER,
                    claim_obj.id, payer_objects[claim.payer].id,
                    {"amount_cents": claim.amount_cents},
                )

            if claim.procedure_codes:
                for code in claim.procedure_codes.split(","):
                    code = code.strip()
                    if not code:
                        continue
                    if code not in procedure_objects:
                        proc_obj = OntologyBuilder._upsert_object(
                            db, practice_id, OntologyObjectType.PROCEDURE,
                            f"procedure:{code}",
                            {"cdt_code": code},
                        )
                        procedure_objects[code] = proc_obj
                    OntologyBuilder._create_link(
                        db, practice_id, OntologyLinkType.CLAIM_HAS_PROCEDURE,
                        claim_obj.id, procedure_objects[code].id,
                    )

        payments = db.query(PaymentIntent).filter(PaymentIntent.practice_id == practice_id).all()
        for payment in payments:
            pi_obj = OntologyBuilder._upsert_object(
                db, practice_id, OntologyObjectType.PAYMENT_INTENT,
                f"payment_intent:{payment.id}",
                {
                    "status": payment.status,
                    "amount_cents": payment.amount_cents,
                    "provider": payment.provider,
                    "confirmed_at": payment.confirmed_at.isoformat() if payment.confirmed_at else None,
                    "failure_code": payment.failure_code,
                },
            )
            if payment.claim_id in claim_objects:
                OntologyBuilder._create_link(
                    db, practice_id, OntologyLinkType.CLAIM_FUNDED_BY_PAYMENT_INTENT,
                    claim_objects[payment.claim_id].id, pi_obj.id,
                    {"amount_cents": payment.amount_cents},
                )

        today = date.today()
        metrics = OntologyBuilder._compute_kpis(db, practice_id, claims, payments)
        for metric_name, metric_data in metrics.items():
            kpi = KPIObservation(
                practice_id=practice_id,
                metric_name=metric_name,
                metric_value=metric_data.get("value"),
                as_of_date=today,
                provenance_json=metric_data.get("provenance"),
            )
            db.add(kpi)

        AuditService.log_event(
            db, claim_id=None, action="ontology_rebuilt",
            actor_user_id=actor_user_id,
            metadata={"practice_id": practice_id, "object_count": len(claim_objects) + len(payer_objects) + len(procedure_objects) + 1},
        )

        db.flush()
        return {"objects": len(claim_objects) + len(payer_objects) + len(procedure_objects) + 1, "metrics": len(metrics)}

    @staticmethod
    def _upsert_object(db, practice_id, object_type, object_key, properties):
        obj = OntologyObject(
            practice_id=practice_id,
            object_type=object_type.value if isinstance(object_type, OntologyObjectType) else object_type,
            object_key=object_key,
            properties_json=properties,
        )
        db.add(obj)
        db.flush()
        return obj

    @staticmethod
    def _create_link(db, practice_id, link_type, from_id, to_id, properties=None):
        link = OntologyLink(
            practice_id=practice_id,
            link_type=link_type.value if isinstance(link_type, OntologyLinkType) else link_type,
            from_object_id=from_id,
            to_object_id=to_id,
            properties_json=properties,
        )
        db.add(link)
        db.flush()
        return link

    @staticmethod
    def _compute_kpis(db, practice_id, claims, payments):
        metrics = {}
        total_claims = len(claims)
        missing_data = []

        total_billed_cents = sum(c.amount_cents for c in claims)

        payer_totals = {}
        for c in claims:
            if c.payer:
                payer_totals[c.payer] = payer_totals.get(c.payer, 0) + c.amount_cents

        if payer_totals and total_billed_cents > 0:
            payer_mix = []
            for payer, amount in sorted(payer_totals.items(), key=lambda x: -x[1]):
                payer_mix.append({"payer": payer, "amount_cents": amount, "share": round(amount / total_billed_cents, 4)})
            metrics["payer_mix"] = {"value": None, "provenance": {"payer_mix": payer_mix[:10]}}

            top_payer_share = payer_mix[0]["share"] if payer_mix else 0
            metrics["payer_concentration"] = {"value": Decimal(str(top_payer_share)), "provenance": {"top_payer": payer_mix[0]["payer"] if payer_mix else None}}
        else:
            missing_data.append("payer_mix")

        procedure_counts = {}
        for c in claims:
            if c.procedure_codes:
                for code in c.procedure_codes.split(","):
                    code = code.strip()
                    if code:
                        procedure_counts[code] = procedure_counts.get(code, 0) + 1

        if procedure_counts and total_claims > 0:
            proc_mix = []
            for code, count in sorted(procedure_counts.items(), key=lambda x: -x[1]):
                proc_mix.append({"cdt_code": code, "count": count, "share": round(count / total_claims, 4)})
            metrics["procedure_mix"] = {"value": None, "provenance": {"procedure_mix": proc_mix[:10]}}
        else:
            missing_data.append("procedure_mix")

        declined_claims = [c for c in claims if c.status == ClaimStatus.DECLINED.value]
        if total_claims > 0:
            denial_rate = len(declined_claims) / total_claims
            metrics["denial_rate"] = {
                "value": Decimal(str(round(denial_rate, 4))),
                "provenance": {"declined": len(declined_claims), "total": total_claims},
            }
        else:
            missing_data.append("denial_rate")

        funded_cents = sum(p.amount_cents for p in payments if p.status in (PaymentIntentStatus.CONFIRMED.value, PaymentIntentStatus.SENT.value))
        metrics["total_funded_cents"] = {"value": Decimal(str(funded_cents)), "provenance": {"payment_count": len(payments)}}

        from ..models.practice import Practice
        practice = db.query(Practice).filter(Practice.id == practice_id).first()
        if practice and practice.funding_limit_cents and practice.funding_limit_cents > 0:
            utilization = funded_cents / practice.funding_limit_cents
            metrics["funded_utilization"] = {
                "value": Decimal(str(round(utilization, 4))),
                "provenance": {"funded_cents": funded_cents, "limit_cents": practice.funding_limit_cents},
            }
        else:
            missing_data.append("funded_utilization")

        exception_claims = [c for c in claims if c.status == ClaimStatus.PAYMENT_EXCEPTION.value]
        if total_claims > 0:
            exception_rate = len(exception_claims) / total_claims
            metrics["exception_rate"] = {
                "value": Decimal(str(round(exception_rate, 4))),
                "provenance": {"exceptions": len(exception_claims), "total": total_claims},
            }
        else:
            missing_data.append("exception_rate")

        confirmed_payments = [p for p in payments if p.confirmed_at and p.sent_at]
        if confirmed_payments:
            lags = [(p.confirmed_at - p.sent_at).total_seconds() / 86400.0 for p in confirmed_payments]
            lags.sort()
            avg_lag = sum(lags) / len(lags)
            p50 = lags[len(lags) // 2]
            p90_idx = min(int(len(lags) * 0.9), len(lags) - 1)
            p90 = lags[p90_idx]
            metrics["reimbursement_lag_proxy"] = {
                "value": Decimal(str(round(avg_lag, 2))),
                "provenance": {"avg_days": round(avg_lag, 2), "p50_days": round(p50, 2), "p90_days": round(p90, 2), "sample_size": len(confirmed_payments)},
            }
        else:
            missing_data.append("reimbursement_lag_proxy")

        metrics["total_billed_cents"] = {"value": Decimal(str(total_billed_cents)), "provenance": {"claim_count": total_claims}}
        metrics["total_claims"] = {"value": Decimal(str(total_claims)), "provenance": {}}

        if missing_data:
            metrics["_missing_data"] = {"value": None, "provenance": {"missing": missing_data}}

        return metrics

    @staticmethod
    def get_practice_context(db: Session, practice_id: int) -> dict:
        practice = db.query(Practice).filter(Practice.id == practice_id).first()
        if not practice:
            raise ValueError(f"Practice {practice_id} not found")

        claims = db.query(Claim).filter(Claim.practice_id == practice_id).all()
        payments = db.query(PaymentIntent).filter(PaymentIntent.practice_id == practice_id).all()

        total_claims = len(claims)
        total_billed_cents = sum(c.amount_cents for c in claims)
        funded_cents = sum(p.amount_cents for p in payments if p.status in (PaymentIntentStatus.CONFIRMED.value, PaymentIntentStatus.SENT.value))
        confirmed_cents = sum(p.amount_cents for p in payments if p.status == PaymentIntentStatus.CONFIRMED.value)

        status_counts = {}
        for s in ClaimStatus:
            status_counts[s.value] = 0
        for c in claims:
            status_counts[c.status] = status_counts.get(c.status, 0) + 1

        payer_totals = {}
        for c in claims:
            if c.payer:
                payer_totals[c.payer] = payer_totals.get(c.payer, 0) + c.amount_cents

        payer_mix = []
        if total_billed_cents > 0:
            for payer, amount in sorted(payer_totals.items(), key=lambda x: -x[1])[:5]:
                payer_mix.append({"payer": payer, "billed_cents": amount, "share": round(amount / total_billed_cents, 4)})

        procedure_counts = {}
        for c in claims:
            if c.procedure_codes:
                for code in c.procedure_codes.split(","):
                    code = code.strip()
                    if code:
                        procedure_counts[code] = procedure_counts.get(code, 0) + 1
        proc_mix = []
        if total_claims > 0:
            for code, count in sorted(procedure_counts.items(), key=lambda x: -x[1])[:5]:
                proc_mix.append({"cdt_code": code, "count": count, "share": round(count / total_claims, 4)})

        confirmed_payments = [p for p in payments if p.confirmed_at and p.sent_at]
        cohorts = {"avg_lag_days": None, "p50_lag_days": None, "p90_lag_days": None, "sample_size": len(confirmed_payments)}
        if confirmed_payments:
            lags = sorted([(p.confirmed_at - p.sent_at).total_seconds() / 86400.0 for p in confirmed_payments])
            cohorts["avg_lag_days"] = round(sum(lags) / len(lags), 2)
            cohorts["p50_lag_days"] = round(lags[len(lags) // 2], 2)
            p90_idx = min(int(len(lags) * 0.9), len(lags) - 1)
            cohorts["p90_lag_days"] = round(lags[p90_idx], 2)

        declined = status_counts.get(ClaimStatus.DECLINED.value, 0)
        denial_rate = round(declined / total_claims, 4) if total_claims > 0 else 0
        exceptions = status_counts.get(ClaimStatus.PAYMENT_EXCEPTION.value, 0)
        exception_rate = round(exceptions / total_claims, 4) if total_claims > 0 else 0

        utilization = None
        if practice.funding_limit_cents and practice.funding_limit_cents > 0:
            utilization = round(funded_cents / practice.funding_limit_cents, 4)

        risk_flags = []
        missing_data = []

        if payer_mix and payer_mix[0]["share"] > 0.6:
            risk_flags.append({"flag": "PAYER_CONCENTRATION", "metric": "payer_concentration", "value": payer_mix[0]["share"], "threshold": 0.6, "detail": f"Top payer ({payer_mix[0]['payer']}) represents {payer_mix[0]['share']*100:.0f}% of billed volume"})
        if denial_rate > 0.1:
            risk_flags.append({"flag": "HIGH_DENIAL_RATE", "metric": "denial_rate", "value": denial_rate, "threshold": 0.1, "detail": f"Denial rate is {denial_rate*100:.1f}%"})
        if utilization is not None and utilization > 0.85:
            risk_flags.append({"flag": "HIGH_UTILIZATION", "metric": "funded_utilization", "value": utilization, "threshold": 0.85, "detail": f"Funding utilization is {utilization*100:.0f}%"})
        if exception_rate > 0.05:
            risk_flags.append({"flag": "HIGH_EXCEPTION_RATE", "metric": "exception_rate", "value": exception_rate, "threshold": 0.05, "detail": f"Exception rate is {exception_rate*100:.1f}%"})

        if not payer_mix:
            missing_data.append("payer_mix")
        if not proc_mix:
            missing_data.append("procedure_mix")
        if not confirmed_payments:
            missing_data.append("reimbursement_lag")
        if utilization is None:
            missing_data.append("funded_utilization (no funding limit set)")

        return {
            "version": "ontology-v1",
            "practice": {
                "id": practice.id,
                "name": practice.name,
                "status": practice.status,
                "funding_limit_cents": practice.funding_limit_cents,
            },
            "snapshot": {
                "totals": {
                    "total_claims": total_claims,
                    "total_billed_cents": total_billed_cents,
                    "status_counts": status_counts,
                },
                "funding": {
                    "total_funded_cents": funded_cents,
                    "total_confirmed_cents": confirmed_cents,
                    "funding_limit_cents": practice.funding_limit_cents,
                    "utilization": utilization,
                },
                "payer_mix": payer_mix,
                "procedure_mix": proc_mix,
                "cohorts": cohorts,
                "denials": {
                    "denial_rate": denial_rate,
                    "declined_count": declined,
                    "exception_rate": exception_rate,
                    "exception_count": exceptions,
                },
                "risk_flags": risk_flags,
                "missing_data": missing_data,
            },
        }
