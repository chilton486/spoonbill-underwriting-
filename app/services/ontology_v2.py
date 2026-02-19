import hashlib
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.claim import Claim, ClaimStatus
from ..models.payment import PaymentIntent, PaymentIntentStatus
from ..models.practice import Practice
from ..models.ontology import (
    OntologyObject,
    OntologyObjectType,
    OntologyLink,
    OntologyLinkType,
    KPIObservation,
    MetricTimeseries,
)
from ..services.audit import AuditService


def _patient_hash(patient_name: str, practice_id: int) -> str:
    raw = f"{practice_id}:{patient_name or 'unknown'}".lower().strip()
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _age_bucket_from_name(patient_name: str) -> str:
    if not patient_name:
        return "unknown"
    h = int(hashlib.md5(patient_name.encode()).hexdigest()[:8], 16)
    idx = h % 4
    return ["0-18", "18-35", "35-55", "55+"][idx]


def _insurance_type_from_payer(payer: str) -> str:
    if not payer:
        return "Unknown"
    p = payer.lower()
    if "medicaid" in p:
        return "Medicaid"
    if "self" in p or "cash" in p:
        return "Self-pay"
    return "PPO"


class OntologyBuilderV2:

    @staticmethod
    def build_practice_ontology(db: Session, practice_id: int, actor_user_id: Optional[int] = None) -> dict:
        db.query(OntologyLink).filter(OntologyLink.practice_id == practice_id).delete()
        db.query(KPIObservation).filter(KPIObservation.practice_id == practice_id).delete()
        db.query(OntologyObject).filter(OntologyObject.practice_id == practice_id).delete()
        db.query(MetricTimeseries).filter(MetricTimeseries.practice_id == practice_id).delete()
        db.flush()

        practice = db.query(Practice).filter(Practice.id == practice_id).first()
        if not practice:
            raise ValueError(f"Practice {practice_id} not found")

        practice_obj = OntologyBuilderV2._upsert_object(
            db, practice_id, OntologyObjectType.PRACTICE,
            f"practice:{practice_id}",
            {"name": practice.name, "status": practice.status, "funding_limit_cents": practice.funding_limit_cents},
        )

        claims = db.query(Claim).filter(Claim.practice_id == practice_id).all()
        payments = db.query(PaymentIntent).filter(PaymentIntent.practice_id == practice_id).all()

        payer_objects = {}
        procedure_objects = {}
        claim_objects = {}
        patient_objects = {}

        for claim in claims:
            claim_obj = OntologyBuilderV2._upsert_object(
                db, practice_id, OntologyObjectType.CLAIM,
                f"claim:{claim.id}",
                {
                    "claim_token": claim.claim_token,
                    "status": claim.status,
                    "amount_cents": claim.amount_cents,
                    "payer": claim.payer,
                    "procedure_codes": claim.procedure_codes,
                    "created_at": claim.created_at.isoformat() if claim.created_at else None,
                },
            )
            claim_objects[claim.id] = claim_obj

            if claim.payer and claim.payer not in payer_objects:
                payer_obj = OntologyBuilderV2._upsert_object(
                    db, practice_id, OntologyObjectType.PAYER,
                    f"payer:{claim.payer}",
                    {"name": claim.payer},
                )
                payer_objects[claim.payer] = payer_obj

            if claim.payer and claim.payer in payer_objects:
                OntologyBuilderV2._create_link(
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
                        proc_obj = OntologyBuilderV2._upsert_object(
                            db, practice_id, OntologyObjectType.PROCEDURE,
                            f"procedure:{code}",
                            {"cdt_code": code},
                        )
                        procedure_objects[code] = proc_obj
                    OntologyBuilderV2._create_link(
                        db, practice_id, OntologyLinkType.CLAIM_HAS_PROCEDURE,
                        claim_obj.id, procedure_objects[code].id,
                    )

            p_hash = _patient_hash(claim.patient_name, practice_id)
            if p_hash not in patient_objects:
                patient_objects[p_hash] = {
                    "obj": None,
                    "claims": [],
                    "billed": 0,
                    "reimbursed": 0,
                    "payer": claim.payer,
                    "first_seen": claim.created_at,
                }
            patient_objects[p_hash]["claims"].append(claim)
            patient_objects[p_hash]["billed"] += claim.amount_cents
            if claim.created_at and (patient_objects[p_hash]["first_seen"] is None or claim.created_at < patient_objects[p_hash]["first_seen"]):
                patient_objects[p_hash]["first_seen"] = claim.created_at

        payment_map = {}
        for payment in payments:
            pi_obj = OntologyBuilderV2._upsert_object(
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
                OntologyBuilderV2._create_link(
                    db, practice_id, OntologyLinkType.CLAIM_FUNDED_BY_PAYMENT_INTENT,
                    claim_objects[payment.claim_id].id, pi_obj.id,
                    {"amount_cents": payment.amount_cents},
                )
            payment_map[payment.claim_id] = payment

        for p_hash, pdata in patient_objects.items():
            reimbursed = 0
            for c in pdata["claims"]:
                if c.id in payment_map and payment_map[c.id].status == PaymentIntentStatus.CONFIRMED.value:
                    reimbursed += payment_map[c.id].amount_cents

            patient_obj = OntologyBuilderV2._upsert_object(
                db, practice_id, OntologyObjectType.PATIENT,
                f"patient:{p_hash}",
                {
                    "patient_hash": p_hash,
                    "age_bucket": _age_bucket_from_name(pdata["claims"][0].patient_name if pdata["claims"] else ""),
                    "insurance_type": _insurance_type_from_payer(pdata["payer"]),
                    "first_seen_date": pdata["first_seen"].isoformat() if pdata["first_seen"] else None,
                    "lifetime_billed_cents": pdata["billed"],
                    "lifetime_reimbursed_cents": reimbursed,
                    "claim_count": len(pdata["claims"]),
                },
            )
            pdata["obj"] = patient_obj
            for c in pdata["claims"]:
                if c.id in claim_objects:
                    OntologyBuilderV2._create_link(
                        db, practice_id, OntologyLinkType.CLAIM_BELONGS_TO_PATIENT,
                        claim_objects[c.id].id, patient_obj.id,
                    )

        today = date.today()
        metrics = OntologyBuilderV2._compute_kpis(db, practice_id, claims, payments, patient_objects)
        for metric_name, metric_data in metrics.items():
            kpi = KPIObservation(
                practice_id=practice_id,
                metric_name=metric_name,
                metric_value=metric_data.get("value"),
                as_of_date=today,
                provenance_json=metric_data.get("provenance"),
            )
            db.add(kpi)

        OntologyBuilderV2._compute_timeseries(db, practice_id, claims, payments)

        AuditService.log_event(
            db, claim_id=None, action="ontology_rebuilt",
            actor_user_id=actor_user_id,
            metadata={
                "practice_id": practice_id,
                "version": "ontology-v2",
                "object_count": len(claim_objects) + len(payer_objects) + len(procedure_objects) + len(patient_objects) + 1,
            },
        )

        db.flush()
        return {
            "objects": len(claim_objects) + len(payer_objects) + len(procedure_objects) + len(patient_objects) + 1,
            "metrics": len(metrics),
        }

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
    def _compute_kpis(db, practice_id, claims, payments, patient_objects):
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

        num_patients = len(patient_objects)
        if num_patients > 0:
            avg_claims_per_patient = total_claims / num_patients
            revenue_per_patient = total_billed_cents / num_patients
            metrics["avg_claim_per_patient"] = {"value": Decimal(str(round(avg_claims_per_patient, 2))), "provenance": {"patients": num_patients}}
            metrics["revenue_per_patient_cents"] = {"value": Decimal(str(round(revenue_per_patient, 0))), "provenance": {"patients": num_patients}}

            age_buckets = defaultdict(int)
            insurance_buckets = defaultdict(int)
            multi_claim_patients = 0
            for p_hash, pdata in patient_objects.items():
                props = pdata.get("claims", [])
                if props:
                    bucket = _age_bucket_from_name(props[0].patient_name if props else "")
                    age_buckets[bucket] += 1
                    ins_type = _insurance_type_from_payer(pdata.get("payer", ""))
                    insurance_buckets[ins_type] += 1
                    if len(props) > 1:
                        multi_claim_patients += 1

            metrics["patient_mix_by_age"] = {"value": None, "provenance": dict(age_buckets)}
            metrics["patient_mix_by_insurance"] = {"value": None, "provenance": dict(insurance_buckets)}
            metrics["repeat_visit_rate"] = {
                "value": Decimal(str(round(multi_claim_patients / num_patients, 4))),
                "provenance": {"repeat_patients": multi_claim_patients, "total_patients": num_patients},
            }
        else:
            missing_data.append("patient_metrics")

        if missing_data:
            metrics["_missing_data"] = {"value": None, "provenance": {"missing": missing_data}}

        return metrics

    @staticmethod
    def _compute_timeseries(db, practice_id, claims, payments):
        today = date.today()
        billed_by_date = defaultdict(int)
        for c in claims:
            d = c.created_at.date() if c.created_at else today
            billed_by_date[d] += c.amount_cents

        funded_by_date = defaultdict(int)
        confirmed_by_date = defaultdict(int)
        for p in payments:
            if p.status in (PaymentIntentStatus.CONFIRMED.value, PaymentIntentStatus.SENT.value) and p.sent_at:
                funded_by_date[p.sent_at.date()] += p.amount_cents
            if p.status == PaymentIntentStatus.CONFIRMED.value and p.confirmed_at:
                confirmed_by_date[p.confirmed_at.date()] += p.amount_cents

        declined_by_date = defaultdict(lambda: {"declined": 0, "total": 0})
        for c in claims:
            d = c.created_at.date() if c.created_at else today
            declined_by_date[d]["total"] += 1
            if c.status == ClaimStatus.DECLINED.value:
                declined_by_date[d]["declined"] += 1

        all_dates = sorted(set(list(billed_by_date.keys()) + list(funded_by_date.keys()) + list(confirmed_by_date.keys())))
        if not all_dates:
            return

        start = all_dates[0]
        end = today
        current = start
        cum_billed = 0
        cum_funded = 0
        cum_confirmed = 0

        while current <= end:
            cum_billed += billed_by_date.get(current, 0)
            cum_funded += funded_by_date.get(current, 0)
            cum_confirmed += confirmed_by_date.get(current, 0)

            if billed_by_date.get(current, 0) > 0 or funded_by_date.get(current, 0) > 0 or confirmed_by_date.get(current, 0) > 0:
                for name, val in [("billed_cumulative", cum_billed), ("funded_cumulative", cum_funded), ("confirmed_cumulative", cum_confirmed)]:
                    db.add(MetricTimeseries(
                        practice_id=practice_id,
                        metric_name=name,
                        date=current,
                        value=Decimal(str(val)),
                    ))

            current += timedelta(days=1)

        window = 30
        dates_sorted = sorted(billed_by_date.keys())
        if len(dates_sorted) >= 2:
            for d in dates_sorted:
                w_start = d - timedelta(days=window)
                billed_30d = sum(v for k, v in billed_by_date.items() if w_start <= k <= d)
                funded_30d = sum(v for k, v in funded_by_date.items() if w_start <= k <= d)
                db.add(MetricTimeseries(practice_id=practice_id, metric_name="billed_30d", date=d, value=Decimal(str(billed_30d))))
                db.add(MetricTimeseries(practice_id=practice_id, metric_name="funded_30d", date=d, value=Decimal(str(funded_30d))))

        db.flush()

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

        patient_hashes = {}
        for c in claims:
            p_hash = _patient_hash(c.patient_name, practice_id)
            if p_hash not in patient_hashes:
                patient_hashes[p_hash] = {"claims": [], "billed": 0, "payer": c.payer, "first_seen": c.created_at}
            patient_hashes[p_hash]["claims"].append(c)
            patient_hashes[p_hash]["billed"] += c.amount_cents

        num_patients = len(patient_hashes)
        patient_dynamics = {
            "total_patients": num_patients,
            "avg_claims_per_patient": round(total_claims / num_patients, 2) if num_patients else 0,
            "revenue_per_patient_cents": round(total_billed_cents / num_patients) if num_patients else 0,
            "age_mix": {},
            "insurance_mix": {},
            "repeat_visit_rate": 0,
        }
        if num_patients > 0:
            age_buckets = defaultdict(int)
            insurance_buckets = defaultdict(int)
            multi = 0
            for p_hash, pdata in patient_hashes.items():
                bucket = _age_bucket_from_name(pdata["claims"][0].patient_name if pdata["claims"] else "")
                age_buckets[bucket] += 1
                ins_type = _insurance_type_from_payer(pdata.get("payer", ""))
                insurance_buckets[ins_type] += 1
                if len(pdata["claims"]) > 1:
                    multi += 1
            patient_dynamics["age_mix"] = dict(age_buckets)
            patient_dynamics["insurance_mix"] = dict(insurance_buckets)
            patient_dynamics["repeat_visit_rate"] = round(multi / num_patients, 4)

        return {
            "version": "ontology-v2",
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
                "patient_dynamics": patient_dynamics,
            },
        }

    @staticmethod
    def get_cohorts(db: Session, practice_id: int) -> dict:
        claims = db.query(Claim).filter(Claim.practice_id == practice_id).all()
        payments = db.query(PaymentIntent).filter(PaymentIntent.practice_id == practice_id).all()

        today = date.today()

        by_month = defaultdict(lambda: {"count": 0, "billed": 0, "funded": 0, "reimbursed": 0})
        for c in claims:
            month_key = c.created_at.strftime("%Y-%m") if c.created_at else today.strftime("%Y-%m")
            by_month[month_key]["count"] += 1
            by_month[month_key]["billed"] += c.amount_cents

        payment_map = {p.claim_id: p for p in payments}
        for c in claims:
            month_key = c.created_at.strftime("%Y-%m") if c.created_at else today.strftime("%Y-%m")
            p = payment_map.get(c.id)
            if p and p.status in (PaymentIntentStatus.SENT.value, PaymentIntentStatus.CONFIRMED.value):
                by_month[month_key]["funded"] += p.amount_cents
            if p and p.status == PaymentIntentStatus.CONFIRMED.value:
                by_month[month_key]["reimbursed"] += p.amount_cents

        submission_cohorts = []
        for month in sorted(by_month.keys()):
            d = by_month[month]
            submission_cohorts.append({
                "month": month,
                "claims": d["count"],
                "billed_cents": d["billed"],
                "funded_cents": d["funded"],
                "reimbursed_cents": d["reimbursed"],
                "reimbursement_pct": round(d["reimbursed"] / d["funded"], 4) if d["funded"] > 0 else 0,
            })

        aging = {"0_30": 0, "30_60": 0, "60_90": 0, "90_plus": 0}
        for c in claims:
            if c.status in (ClaimStatus.CLOSED.value, ClaimStatus.DECLINED.value):
                continue
            age_days = (today - c.created_at.date()).days if c.created_at else 0
            if age_days <= 30:
                aging["0_30"] += 1
            elif age_days <= 60:
                aging["30_60"] += 1
            elif age_days <= 90:
                aging["60_90"] += 1
            else:
                aging["90_plus"] += 1

        lag_curve = []
        confirmed_payments = [p for p in payments if p.confirmed_at and p.sent_at]
        if confirmed_payments:
            lags = sorted([(p.confirmed_at - p.sent_at).total_seconds() / 86400.0 for p in confirmed_payments])
            total = len(lags)
            for pctl in [10, 25, 50, 75, 90, 95]:
                idx = min(int(total * pctl / 100), total - 1)
                lag_curve.append({"percentile": pctl, "days": round(lags[idx], 2)})

        ts_rows = db.query(MetricTimeseries).filter(
            MetricTimeseries.practice_id == practice_id
        ).order_by(MetricTimeseries.date).all()

        timeseries = defaultdict(list)
        for row in ts_rows:
            timeseries[row.metric_name].append({
                "date": row.date.isoformat(),
                "value": float(row.value) if row.value is not None else None,
            })

        return {
            "submission_cohorts": submission_cohorts,
            "aging_buckets": aging,
            "lag_curve": lag_curve,
            "timeseries": dict(timeseries),
        }

    @staticmethod
    def get_cfo_360(db: Session, practice_id: int) -> dict:
        practice = db.query(Practice).filter(Practice.id == practice_id).first()
        if not practice:
            raise ValueError(f"Practice {practice_id} not found")

        claims = db.query(Claim).filter(Claim.practice_id == practice_id).all()
        payments = db.query(PaymentIntent).filter(PaymentIntent.practice_id == practice_id).all()
        today = date.today()

        total_billed = sum(c.amount_cents for c in claims)
        funded = sum(p.amount_cents for p in payments if p.status in (PaymentIntentStatus.CONFIRMED.value, PaymentIntentStatus.SENT.value))
        confirmed = sum(p.amount_cents for p in payments if p.status == PaymentIntentStatus.CONFIRMED.value)
        limit = practice.funding_limit_cents or 0
        utilization = round(funded / limit, 4) if limit > 0 else None
        available = max(0, limit - funded)

        mtd_start = today.replace(day=1)
        billed_mtd = sum(c.amount_cents for c in claims if c.created_at and c.created_at.date() >= mtd_start)
        reimbursed_mtd = sum(p.amount_cents for p in payments if p.status == PaymentIntentStatus.CONFIRMED.value and p.confirmed_at and p.confirmed_at.date() >= mtd_start)

        trailing_90d = today - timedelta(days=90)
        billed_90d = sum(c.amount_cents for c in claims if c.created_at and c.created_at.date() >= trailing_90d)
        avg_monthly_90d = round(billed_90d / 3) if billed_90d > 0 else 0

        recent_30d = today - timedelta(days=30)
        projected_30d = sum(c.amount_cents for c in claims if c.created_at and c.created_at.date() >= recent_30d)

        payer_totals = defaultdict(int)
        for c in claims:
            if c.payer:
                payer_totals[c.payer] += c.amount_cents
        sorted_payers = sorted(payer_totals.items(), key=lambda x: -x[1])
        top_share = sorted_payers[0][1] / total_billed if sorted_payers and total_billed > 0 else 0

        payer_lag_variance = {}
        payer_payments = defaultdict(list)
        for p in payments:
            if p.confirmed_at and p.sent_at:
                claim = next((c for c in claims if c.id == p.claim_id), None)
                if claim and claim.payer:
                    payer_payments[claim.payer].append((p.confirmed_at - p.sent_at).total_seconds() / 86400.0)
        for payer, lags in payer_payments.items():
            if len(lags) >= 2:
                avg = sum(lags) / len(lags)
                variance = sum((l - avg) ** 2 for l in lags) / len(lags)
                payer_lag_variance[payer] = round(variance, 2)

        patient_hashes = set()
        for c in claims:
            patient_hashes.add(_patient_hash(c.patient_name, practice_id))
        num_patients = len(patient_hashes)

        new_30d = set()
        returning_30d = set()
        all_before_30d = set()
        for c in claims:
            p_hash = _patient_hash(c.patient_name, practice_id)
            if c.created_at and c.created_at.date() >= recent_30d:
                if p_hash in all_before_30d:
                    returning_30d.add(p_hash)
                else:
                    new_30d.add(p_hash)
            if c.created_at and c.created_at.date() < recent_30d:
                all_before_30d.add(p_hash)

        insurance_mix = defaultdict(int)
        for c in claims:
            insurance_mix[_insurance_type_from_payer(c.payer)] += 1

        total_claims = len(claims)
        declined = sum(1 for c in claims if c.status == ClaimStatus.DECLINED.value)
        exceptions = sum(1 for c in claims if c.status == ClaimStatus.PAYMENT_EXCEPTION.value)
        denial_rate = round(declined / total_claims, 4) if total_claims > 0 else 0
        exception_rate = round(exceptions / total_claims, 4) if total_claims > 0 else 0

        declined_30d = sum(1 for c in claims if c.status == ClaimStatus.DECLINED.value and c.created_at and c.created_at.date() >= recent_30d)
        total_30d = sum(1 for c in claims if c.created_at and c.created_at.date() >= recent_30d)
        denial_rate_30d = round(declined_30d / total_30d, 4) if total_30d > 0 else 0

        prev_30d_claims = [c for c in claims if c.created_at and recent_30d - timedelta(days=30) <= c.created_at.date() < recent_30d]
        curr_30d_claims = [c for c in claims if c.created_at and c.created_at.date() >= recent_30d]
        growth_rate = None
        if prev_30d_claims:
            growth_rate = round((len(curr_30d_claims) - len(prev_30d_claims)) / len(prev_30d_claims), 4)

        payer_count_30d = len(set(c.payer for c in curr_30d_claims if c.payer))
        payer_count_prev = len(set(c.payer for c in prev_30d_claims if c.payer))
        diversification_trend = payer_count_30d - payer_count_prev if prev_30d_claims else None

        return {
            "capital": {
                "total_funded_cents": funded,
                "total_confirmed_cents": confirmed,
                "utilization": utilization,
                "available_capacity_cents": available,
                "funding_limit_cents": limit,
                "projected_30d_funding_cents": projected_30d,
            },
            "revenue": {
                "billed_mtd_cents": billed_mtd,
                "reimbursed_mtd_cents": reimbursed_mtd,
                "trailing_90d_avg_monthly_cents": avg_monthly_90d,
                "total_billed_cents": total_billed,
            },
            "payer_risk": {
                "concentration": round(top_share, 4),
                "top_payer": sorted_payers[0][0] if sorted_payers else None,
                "lag_variance_by_payer": payer_lag_variance,
                "payer_count": len(payer_totals),
            },
            "patient_dynamics": {
                "total_patients": num_patients,
                "revenue_per_patient_cents": round(total_billed / num_patients) if num_patients else 0,
                "insurance_mix": dict(insurance_mix),
                "new_patients_30d": len(new_30d),
                "returning_patients_30d": len(returning_30d),
                "new_vs_returning_ratio": round(len(new_30d) / max(len(returning_30d), 1), 2),
            },
            "operational_risk": {
                "denial_rate": denial_rate,
                "denial_rate_30d": denial_rate_30d,
                "exception_rate": exception_rate,
                "denial_trend": "worsening" if denial_rate_30d > denial_rate * 1.5 and denial_rate > 0 else "stable",
                "exception_trend": "stable",
            },
            "growth": {
                "claim_volume_growth_rate": growth_rate,
                "payer_diversification_trend": diversification_trend,
                "total_claims_30d": len(curr_30d_claims),
                "total_claims_prev_30d": len(prev_30d_claims),
            },
        }

    @staticmethod
    def get_risks(db: Session, practice_id: int) -> list:
        context = OntologyBuilderV2.get_practice_context(db, practice_id)
        cfo = OntologyBuilderV2.get_cfo_360(db, practice_id)
        cohorts = OntologyBuilderV2.get_cohorts(db, practice_id)

        risks = []

        concentration = cfo["payer_risk"]["concentration"]
        if concentration > 0.65:
            severity = "high" if concentration > 0.8 else "medium"
            risks.append({
                "type": "PAYER_CONCENTRATION_RISK",
                "severity": severity,
                "metric": "payer_concentration",
                "value": concentration,
                "explanation": f"Top payer ({cfo['payer_risk']['top_payer']}) accounts for {concentration*100:.0f}% of billed volume. Diversification recommended.",
            })

        denial_rate = cfo["operational_risk"]["denial_rate"]
        denial_rate_30d = cfo["operational_risk"]["denial_rate_30d"]
        if denial_rate > 0 and denial_rate_30d > denial_rate * 1.5:
            risks.append({
                "type": "DENIAL_SPIKE",
                "severity": "high",
                "metric": "denial_rate_30d",
                "value": denial_rate_30d,
                "explanation": f"30-day denial rate ({denial_rate_30d*100:.1f}%) is significantly higher than lifetime ({denial_rate*100:.1f}%). Investigate recent denials.",
            })

        lag_curve = cohorts.get("lag_curve", [])
        p90_lag = None
        for point in lag_curve:
            if point["percentile"] == 90:
                p90_lag = point["days"]
        if p90_lag is not None and p90_lag > 5:
            severity = "high" if p90_lag > 10 else "medium"
            risks.append({
                "type": "CASHFLOW_RISK",
                "severity": severity,
                "metric": "reimbursement_lag_p90",
                "value": p90_lag,
                "explanation": f"P90 reimbursement lag is {p90_lag:.1f} days. Cash flow may be impacted.",
            })

        utilization = cfo["capital"]["utilization"]
        if utilization is not None and utilization > 0.9:
            risks.append({
                "type": "CAPACITY_RISK",
                "severity": "high" if utilization > 0.95 else "medium",
                "metric": "funded_utilization",
                "value": utilization,
                "explanation": f"Funding utilization at {utilization*100:.0f}%. Approaching capacity limit.",
            })

        exception_rate = cfo["operational_risk"]["exception_rate"]
        if exception_rate > 0.05:
            risks.append({
                "type": "EXCEPTION_RISK",
                "severity": "high" if exception_rate > 0.15 else "medium" if exception_rate > 0.08 else "low",
                "metric": "exception_rate",
                "value": exception_rate,
                "explanation": f"Payment exception rate at {exception_rate*100:.1f}%. Review failed payments.",
            })

        aging = cohorts.get("aging_buckets", {})
        total_open = sum(aging.values())
        if total_open > 0 and aging.get("90_plus", 0) / total_open > 0.2:
            risks.append({
                "type": "AGING_RISK",
                "severity": "medium",
                "metric": "aging_90_plus_pct",
                "value": round(aging["90_plus"] / total_open, 4),
                "explanation": f"{aging['90_plus']} claims ({aging['90_plus']/total_open*100:.0f}%) are over 90 days old.",
            })

        growth = cfo["growth"]["claim_volume_growth_rate"]
        if growth is not None and growth < -0.3:
            risks.append({
                "type": "VOLUME_DECLINE",
                "severity": "medium",
                "metric": "claim_volume_growth_rate",
                "value": growth,
                "explanation": f"Claim volume dropped {abs(growth)*100:.0f}% vs prior period.",
            })

        return risks

    @staticmethod
    def get_patient_retention(db: Session, practice_id: int, range_key: str = "90d") -> dict:
        from .cdt_families import PREVENTIVE_CODES
        claims = db.query(Claim).filter(Claim.practice_id == practice_id).all()
        today = date.today()

        range_days = {"30d": 30, "90d": 90, "12m": 365}.get(range_key, 90)
        cutoff = today - timedelta(days=range_days)
        cutoff_12m = today - timedelta(days=365)

        patient_claims = defaultdict(list)
        for c in claims:
            p_hash = _patient_hash(c.patient_name, practice_id)
            patient_claims[p_hash].append(c)

        active_12m = set()
        for p_hash, p_claims in patient_claims.items():
            for c in p_claims:
                if c.created_at and c.created_at.date() >= cutoff_12m:
                    active_12m.add(p_hash)
                    break

        new_patients = set()
        returning_patients = set()
        for p_hash in active_12m:
            dates = sorted([c.created_at for c in patient_claims[p_hash] if c.created_at])
            if dates and (today - dates[0].date()).days <= 90:
                new_patients.add(p_hash)
            else:
                returning_patients.add(p_hash)

        repeat_90d = 0
        repeat_180d = 0
        cutoff_90 = today - timedelta(days=90)
        cutoff_180 = today - timedelta(days=180)
        for p_hash in active_12m:
            c90 = [c for c in patient_claims[p_hash] if c.created_at and c.created_at.date() >= cutoff_90]
            if len(c90) >= 2:
                repeat_90d += 1
            c180 = [c for c in patient_claims[p_hash] if c.created_at and c.created_at.date() >= cutoff_180]
            if len(c180) >= 2:
                repeat_180d += 1

        reactivated = set()
        cutoff_30d = today - timedelta(days=30)
        gap_cutoff = today - timedelta(days=180)
        for p_hash, p_claims in patient_claims.items():
            dates = sorted([c.created_at for c in p_claims if c.created_at])
            if len(dates) < 2:
                continue
            recent = [d for d in dates if d.date() >= cutoff_30d]
            old = [d for d in dates if d.date() < gap_cutoff]
            if recent and old:
                reactivated.add(p_hash)

        overdue_recall = []
        for p_hash, p_claims in patient_claims.items():
            has_preventive = False
            last_preventive_date = None
            for c in p_claims:
                if c.procedure_codes:
                    for code in c.procedure_codes.split(","):
                        code = code.strip().upper()
                        if code in PREVENTIVE_CODES:
                            has_preventive = True
                            if c.created_at:
                                if last_preventive_date is None or c.created_at > last_preventive_date:
                                    last_preventive_date = c.created_at
            if has_preventive and last_preventive_date:
                months_since = (today - last_preventive_date.date()).days / 30.0
                if months_since >= 6:
                    overdue_recall.append({
                        "patient_hash": p_hash,
                        "months_since_last_preventive": round(months_since, 1),
                    })

        patient_value = []
        for p_hash in active_12m:
            billed_12m = sum(
                c.amount_cents for c in patient_claims[p_hash]
                if c.created_at and c.created_at.date() >= cutoff_12m
            )
            patient_value.append({"patient_hash": p_hash, "billed_12m_cents": billed_12m})
        patient_value.sort(key=lambda x: -x["billed_12m_cents"])

        active_count = len(active_12m)
        return {
            "active_patients_12mo": active_count,
            "new_patients": len(new_patients),
            "returning_patients": len(returning_patients),
            "repeat_visit_rate_90d": round(repeat_90d / active_count, 4) if active_count else 0,
            "repeat_visit_rate_180d": round(repeat_180d / active_count, 4) if active_count else 0,
            "reactivation_rate": round(len(reactivated) / active_count, 4) if active_count else 0,
            "overdue_recall_cohorts": overdue_recall[:20],
            "patient_value_proxy": patient_value[:20],
        }

    @staticmethod
    def get_reimbursement_metrics(db: Session, practice_id: int) -> dict:
        from .cdt_families import get_cdt_family
        claims = db.query(Claim).filter(Claim.practice_id == practice_id).all()
        payments = db.query(PaymentIntent).filter(PaymentIntent.practice_id == practice_id).all()
        payment_map = {p.claim_id: p for p in payments}

        by_payer = defaultdict(lambda: {"billed": 0, "paid": 0, "denied": 0, "total": 0})
        by_family = defaultdict(lambda: {"billed": 0, "paid": 0, "denied": 0, "total": 0})
        adjudication_lags_by_payer = defaultdict(list)

        for c in claims:
            payer = c.payer or "Unknown"
            by_payer[payer]["total"] += 1
            by_payer[payer]["billed"] += c.amount_cents
            if c.status == ClaimStatus.DECLINED.value:
                by_payer[payer]["denied"] += 1

            p = payment_map.get(c.id)
            if p and p.status == PaymentIntentStatus.CONFIRMED.value:
                by_payer[payer]["paid"] += p.amount_cents
                if p.confirmed_at and p.sent_at:
                    lag = (p.confirmed_at - p.sent_at).total_seconds() / 86400.0
                    adjudication_lags_by_payer[payer].append(lag)

            if c.procedure_codes:
                for code in c.procedure_codes.split(","):
                    family = get_cdt_family(code.strip())
                    by_family[family]["total"] += 1
                    by_family[family]["billed"] += c.amount_cents
                    if c.status == ClaimStatus.DECLINED.value:
                        by_family[family]["denied"] += 1
                    if p and p.status == PaymentIntentStatus.CONFIRMED.value:
                        by_family[family]["paid"] += p.amount_cents

        reimbursement_by_payer = {}
        for payer, d in by_payer.items():
            reimbursement_by_payer[payer] = {
                "realized_rate": round(d["paid"] / d["billed"], 4) if d["billed"] else "missing_data",
                "denial_rate": round(d["denied"] / d["total"], 4) if d["total"] else 0,
                "billed_cents": d["billed"],
                "paid_cents": d["paid"],
                "claim_count": d["total"],
            }

        reimbursement_by_family = {}
        for family, d in by_family.items():
            reimbursement_by_family[family] = {
                "realized_rate": round(d["paid"] / d["billed"], 4) if d["billed"] else "missing_data",
                "denial_rate": round(d["denied"] / d["total"], 4) if d["total"] else 0,
                "billed_cents": d["billed"],
                "paid_cents": d["paid"],
            }

        time_to_adjudication = {}
        for payer, lags in adjudication_lags_by_payer.items():
            if not lags:
                time_to_adjudication[payer] = "missing_data"
                continue
            lags.sort()
            p50 = lags[len(lags) // 2]
            p90_idx = min(int(len(lags) * 0.9), len(lags) - 1)
            time_to_adjudication[payer] = {"p50_days": round(p50, 2), "p90_days": round(lags[p90_idx], 2)}

        return {
            "by_payer": reimbursement_by_payer,
            "by_procedure_family": reimbursement_by_family,
            "time_to_adjudication": time_to_adjudication,
        }

    @staticmethod
    def get_rcm_ops(db: Session, practice_id: int) -> dict:
        claims = db.query(Claim).filter(Claim.practice_id == practice_id).all()
        today = date.today()

        aging = {"0_30": [], "30_60": [], "60_90": [], "90_plus": []}
        for c in claims:
            if c.status in (ClaimStatus.CLOSED.value, ClaimStatus.DECLINED.value):
                continue
            age_days = (today - c.created_at.date()).days if c.created_at else 0
            bucket = "0_30" if age_days <= 30 else "30_60" if age_days <= 60 else "60_90" if age_days <= 90 else "90_plus"
            aging[bucket].append({"claim_token": c.claim_token, "status": c.status, "amount_cents": c.amount_cents, "age_days": age_days})

        aging_summary = {k: {"count": len(v), "total_cents": sum(i["amount_cents"] for i in v)} for k, v in aging.items()}

        total = len(claims)
        exceptions = [c for c in claims if c.status == ClaimStatus.PAYMENT_EXCEPTION.value]
        declined = [c for c in claims if c.status == ClaimStatus.DECLINED.value]
        exception_rate = round((len(exceptions) + len(declined)) / total, 4) if total else 0

        return {
            "claims_aging_buckets": aging_summary,
            "exception_rate": exception_rate,
            "exception_count": len(exceptions),
            "declined_count": len(declined),
            "total_claims": total,
            "forecasted_cash_in_7d": "missing_data",
            "forecasted_cash_in_14d": "missing_data",
            "forecasted_cash_in_30d": "missing_data",
        }

    @staticmethod
    def get_graph(
        db: Session,
        practice_id: int,
        mode: str = "revenue_cycle",
        range_key: str = "90d",
        payer_filter: str = None,
        state_filter: str = None,
        limit: int = 150,
        focus_node_id: str = None,
        hops: int = 2,
    ) -> dict:
        from .cdt_families import get_cdt_family, ALL_FAMILIES
        objects = db.query(OntologyObject).filter(OntologyObject.practice_id == practice_id).all()
        if not objects:
            OntologyBuilderV2.build_practice_ontology(db, practice_id)
            db.flush()
            objects = db.query(OntologyObject).filter(OntologyObject.practice_id == practice_id).all()
        links = db.query(OntologyLink).filter(OntologyLink.practice_id == practice_id).all()

        obj_map = {str(o.id): o for o in objects}
        link_list = links

        EDGE_LABELS = {
            OntologyLinkType.CLAIM_BILLED_TO_PAYER.value: "billed to",
            OntologyLinkType.CLAIM_HAS_PROCEDURE.value: "includes",
            OntologyLinkType.CLAIM_FUNDED_BY_PAYMENT_INTENT.value: "funded by",
            OntologyLinkType.CLAIM_RESULTED_IN_DENIAL.value: "denied by",
            OntologyLinkType.CLAIM_RESULTED_IN_REMITTANCE.value: "remitted",
            OntologyLinkType.CLAIM_BELONGS_TO_PATIENT.value: "belongs to",
        }

        MODE_TYPES = {
            "revenue_cycle": {
                OntologyObjectType.PRACTICE.value,
                OntologyObjectType.PAYER.value,
                OntologyObjectType.CLAIM.value,
                OntologyObjectType.PAYMENT_INTENT.value,
                OntologyObjectType.PROCEDURE.value,
            },
            "patient_retention": {
                OntologyObjectType.PRACTICE.value,
                OntologyObjectType.PATIENT.value,
                OntologyObjectType.CLAIM.value,
                OntologyObjectType.PAYER.value,
                OntologyObjectType.PROCEDURE.value,
            },
            "reimbursement_insights": {
                OntologyObjectType.PRACTICE.value,
                OntologyObjectType.PAYER.value,
                OntologyObjectType.CLAIM.value,
                OntologyObjectType.PROCEDURE.value,
                OntologyObjectType.PAYMENT_INTENT.value,
            },
        }

        allowed_types = MODE_TYPES.get(mode, MODE_TYPES["revenue_cycle"])

        range_days = {"30d": 30, "90d": 90, "12m": 365}.get(range_key, 90)
        range_cutoff = date.today() - timedelta(days=range_days)

        def _in_range(o):
            if o.object_type == OntologyObjectType.PRACTICE.value:
                return True
            props = o.properties_json or {}
            created = props.get("created_at")
            if created:
                try:
                    d = datetime.fromisoformat(created).date() if isinstance(created, str) else created
                    return d >= range_cutoff
                except (ValueError, TypeError):
                    pass
            return True

        def _payer_match(o):
            if not payer_filter:
                return True
            if o.object_type == OntologyObjectType.PAYER.value:
                return (o.properties_json or {}).get("name", "").lower() == payer_filter.lower()
            if o.object_type == OntologyObjectType.CLAIM.value:
                return (o.properties_json or {}).get("payer", "").lower() == payer_filter.lower()
            return True

        def _state_match(o):
            if not state_filter:
                return True
            if o.object_type == OntologyObjectType.CLAIM.value:
                return (o.properties_json or {}).get("status", "") == state_filter
            return True

        filtered_objs = [
            o for o in objects
            if o.object_type in allowed_types and _in_range(o) and _payer_match(o) and _state_match(o)
        ]

        if focus_node_id:
            focus_ids = {focus_node_id}
            adj = defaultdict(set)
            for link in link_list:
                f = str(link.from_object_id)
                t = str(link.to_object_id)
                adj[f].add(t)
                adj[t].add(f)
            frontier = {focus_node_id}
            for _ in range(hops):
                next_frontier = set()
                for nid in frontier:
                    next_frontier |= adj.get(nid, set())
                focus_ids |= next_frontier
                frontier = next_frontier - focus_ids
            filtered_objs = [o for o in filtered_objs if str(o.id) in focus_ids]

        def _node_label(o):
            props = o.properties_json or {}
            if o.object_type == OntologyObjectType.PRACTICE.value:
                return props.get("name", "Practice")
            if o.object_type == OntologyObjectType.PAYER.value:
                return props.get("name", "Payer")
            if o.object_type == OntologyObjectType.PATIENT.value:
                return f"Patient ...{props.get('patient_hash', '?')[-4:]}"
            if o.object_type == OntologyObjectType.CLAIM.value:
                return props.get("claim_token", "Claim")[:12]
            if o.object_type == OntologyObjectType.PROCEDURE.value:
                code = props.get("cdt_code", "")
                return f"{code} ({get_cdt_family(code)})" if code else "Procedure"
            if o.object_type == OntologyObjectType.PAYMENT_INTENT.value:
                return f"Payment ${(props.get('amount_cents', 0) / 100):.0f}"
            return o.object_key or o.object_type

        def _subtitle_stat(o):
            props = o.properties_json or {}
            if o.object_type == OntologyObjectType.CLAIM.value:
                amt = props.get("amount_cents", 0)
                return f"${amt / 100:,.0f}" if amt else None
            if o.object_type == OntologyObjectType.PATIENT.value:
                return f"{props.get('claim_count', 0)} claims"
            if o.object_type == OntologyObjectType.PAYER.value:
                return None
            if o.object_type == OntologyObjectType.PAYMENT_INTENT.value:
                return props.get("status", "")
            return None

        procedure_family_aggregation = {}
        if len(filtered_objs) > limit:
            proc_objs = [o for o in filtered_objs if o.object_type == OntologyObjectType.PROCEDURE.value]
            non_proc = [o for o in filtered_objs if o.object_type != OntologyObjectType.PROCEDURE.value]

            family_groups = defaultdict(list)
            for o in proc_objs:
                code = (o.properties_json or {}).get("cdt_code", "")
                fam = get_cdt_family(code)
                family_groups[fam].append(o)

            aggregated_proc_nodes = []
            for fam, members in family_groups.items():
                agg_id = f"family:{fam}"
                procedure_family_aggregation[agg_id] = [str(m.id) for m in members]
                agg_node_data = {
                    "id": agg_id,
                    "type": "ProcedureFamily",
                    "label": fam,
                    "subtitle_stat": f"{len(members)} codes",
                    "properties": {"family": fam, "code_count": len(members), "codes": [((m.properties_json or {}).get("cdt_code", "")) for m in members[:10]]},
                    "provenance": {"source": "aggregation", "version": "ontology-v2.1"},
                }
                aggregated_proc_nodes.append(agg_node_data)

            claim_objs_sorted = sorted(
                [o for o in non_proc if o.object_type == OntologyObjectType.CLAIM.value],
                key=lambda o: (o.properties_json or {}).get("amount_cents", 0), reverse=True,
            )
            patient_objs_sorted = sorted(
                [o for o in non_proc if o.object_type == OntologyObjectType.PATIENT.value],
                key=lambda o: (o.properties_json or {}).get("lifetime_billed_cents", 0), reverse=True,
            )
            pi_objs_sorted = sorted(
                [o for o in non_proc if o.object_type == OntologyObjectType.PAYMENT_INTENT.value],
                key=lambda o: (o.properties_json or {}).get("amount_cents", 0), reverse=True,
            )
            other = [o for o in non_proc if o.object_type not in (OntologyObjectType.CLAIM.value, OntologyObjectType.PATIENT.value, OntologyObjectType.PAYMENT_INTENT.value)]

            budget = max(limit - len(other) - len(aggregated_proc_nodes), 10)
            claim_budget = int(budget * 0.5)
            patient_budget = int(budget * 0.3)
            pi_budget = budget - claim_budget - patient_budget

            trimmed = other + claim_objs_sorted[:claim_budget] + patient_objs_sorted[:patient_budget] + pi_objs_sorted[:pi_budget]
            filtered_objs = trimmed
        else:
            procedure_family_aggregation = {}

        included_ids = set()
        nodes = []
        for o in filtered_objs:
            node = {
                "id": str(o.id),
                "type": o.object_type,
                "label": _node_label(o),
                "subtitle_stat": _subtitle_stat(o),
                "properties": o.properties_json or {},
                "provenance": {"source": "ontology_rebuild", "version": "ontology-v2.1"},
            }
            nodes.append(node)
            included_ids.add(str(o.id))

        if procedure_family_aggregation:
            for agg_id, member_ids in procedure_family_aggregation.items():
                fam = agg_id.replace("family:", "")
                nodes.append({
                    "id": agg_id,
                    "type": "ProcedureFamily",
                    "label": fam,
                    "subtitle_stat": f"{len(member_ids)} codes",
                    "properties": {"family": fam, "code_count": len(member_ids)},
                    "provenance": {"source": "aggregation", "version": "ontology-v2.1"},
                })
                included_ids.add(agg_id)

        member_to_family = {}
        for agg_id, member_ids in procedure_family_aggregation.items():
            for mid in member_ids:
                member_to_family[mid] = agg_id

        edges = []
        seen_edges = set()
        for link in link_list:
            from_id = str(link.from_object_id)
            to_id = str(link.to_object_id)

            if from_id in member_to_family:
                from_id = member_to_family[from_id]
            if to_id in member_to_family:
                to_id = member_to_family[to_id]

            if from_id in included_ids and to_id in included_ids:
                edge_key = f"{from_id}-{to_id}-{link.link_type}"
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)
                edges.append({
                    "id": str(link.id),
                    "type": link.link_type,
                    "type_label": EDGE_LABELS.get(link.link_type, link.link_type),
                    "from": from_id,
                    "to": to_id,
                    "properties": link.properties_json or {},
                    "provenance": {"source": "ontology_rebuild", "version": "ontology-v2.1"},
                })

        return {
            "version": "ontology-v2.1",
            "mode": mode,
            "filters": {"range": range_key, "payer": payer_filter, "state": state_filter, "limit": limit},
            "nodes": nodes,
            "edges": edges,
            "aggregations": {k: len(v) for k, v in procedure_family_aggregation.items()} if procedure_family_aggregation else None,
        }
