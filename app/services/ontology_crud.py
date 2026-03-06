"""CRUD and query services for ontology objects.

Provides practice-scoped data access for Providers, Payers, PayerContracts,
ProcedureCodes, ClaimLines, FundingDecisions, Remittances, and RemittanceLines.
"""
import logging
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, desc, case
from sqlalchemy.orm import Session

from ..models.provider import Provider
from ..models.payer import Payer
from ..models.payer_contract import PayerContract
from ..models.procedure_code import ProcedureCode
from ..models.claim import Claim, ClaimStatus
from ..models.claim_line import ClaimLine
from ..models.funding_decision import FundingDecision, FundingDecisionType
from ..models.payment import PaymentIntent, PaymentIntentStatus
from ..models.remittance import Remittance, RemittanceLine, RemittanceLineMatchStatus
from ..models.fee_schedule import FeeScheduleItem
from ..models.practice import Practice

logger = logging.getLogger(__name__)


class ProviderService:
    @staticmethod
    def list_providers(db: Session, practice_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
        q = db.query(Provider).filter(Provider.practice_id == practice_id)
        if active_only:
            q = q.filter(Provider.is_active.is_(True))
        providers = q.order_by(Provider.full_name).all()
        return [
            {
                "id": p.id,
                "full_name": p.full_name,
                "npi": p.npi,
                "specialty": p.specialty,
                "role": p.role,
                "is_active": p.is_active,
            }
            for p in providers
        ]

    @staticmethod
    def get_provider(db: Session, provider_id: int, practice_id: int) -> Optional[Dict[str, Any]]:
        p = db.query(Provider).filter(
            Provider.id == provider_id, Provider.practice_id == practice_id
        ).first()
        if not p:
            return None
        return {
            "id": p.id,
            "practice_id": p.practice_id,
            "full_name": p.full_name,
            "npi": p.npi,
            "specialty": p.specialty,
            "role": p.role,
            "is_active": p.is_active,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }

    @staticmethod
    def create_provider(db: Session, practice_id: int, **kwargs) -> Provider:
        provider = Provider(practice_id=practice_id, **kwargs)
        db.add(provider)
        db.flush()
        return provider


class PayerService:
    @staticmethod
    def list_payers(db: Session) -> List[Dict[str, Any]]:
        payers = db.query(Payer).order_by(Payer.name).all()
        return [
            {
                "id": p.id,
                "payer_code": p.payer_code,
                "name": p.name,
                "plan_types": p.plan_types,
                "eft_capable": p.eft_capable,
                "era_capable": p.era_capable,
                "filing_limit_days": p.filing_limit_days,
            }
            for p in payers
        ]

    @staticmethod
    def get_or_create_payer(db: Session, payer_code: str, name: str, **kwargs) -> Payer:
        existing = db.query(Payer).filter(Payer.payer_code == payer_code).first()
        if existing:
            return existing
        payer = Payer(payer_code=payer_code, name=name, **kwargs)
        db.add(payer)
        db.flush()
        return payer


class PayerContractService:
    @staticmethod
    def list_contracts(db: Session, practice_id: int) -> List[Dict[str, Any]]:
        contracts = db.query(PayerContract).filter(
            PayerContract.practice_id == practice_id
        ).order_by(desc(PayerContract.created_at)).all()
        results = []
        for c in contracts:
            payer = db.query(Payer).filter(Payer.id == c.payer_id).first()
            results.append({
                "id": c.id,
                "payer_id": c.payer_id,
                "payer_name": payer.name if payer else None,
                "payer_code": payer.payer_code if payer else None,
                "effective_start_date": c.effective_start_date.isoformat() if c.effective_start_date else None,
                "effective_end_date": c.effective_end_date.isoformat() if c.effective_end_date else None,
                "network_status": c.network_status,
                "status": c.status,
                "timely_filing_limit_days": c.timely_filing_limit_days,
                "contract_notes": c.contract_notes,
            })
        return results


class ProcedureCodeService:
    @staticmethod
    def list_procedure_codes(db: Session, category: Optional[str] = None) -> List[Dict[str, Any]]:
        q = db.query(ProcedureCode)
        if category:
            q = q.filter(ProcedureCode.category == category)
        codes = q.order_by(ProcedureCode.cdt_code).all()
        return [
            {
                "id": pc.id,
                "cdt_code": pc.cdt_code,
                "short_description": pc.short_description,
                "category": pc.category,
                "common_denial_reasons": pc.common_denial_reasons,
                "risk_notes": pc.risk_notes,
            }
            for pc in codes
        ]

    @staticmethod
    def get_or_create(db: Session, cdt_code: str, short_description: str, category: str = "OTHER") -> ProcedureCode:
        existing = db.query(ProcedureCode).filter(ProcedureCode.cdt_code == cdt_code).first()
        if existing:
            return existing
        pc = ProcedureCode(cdt_code=cdt_code, short_description=short_description, category=category)
        db.add(pc)
        db.flush()
        return pc


class OntologyInsightsService:
    """Aggregation queries for practice-level ontology insights."""

    @staticmethod
    def get_practice_summary(db: Session, practice_id: int) -> Dict[str, Any]:
        practice = db.query(Practice).filter(Practice.id == practice_id).first()
        if not practice:
            return {}

        total_claims = db.query(func.count(Claim.id)).filter(Claim.practice_id == practice_id).scalar() or 0
        total_billed = db.query(func.coalesce(func.sum(Claim.amount_cents), 0)).filter(
            Claim.practice_id == practice_id
        ).scalar()

        total_funded = db.query(func.coalesce(func.sum(PaymentIntent.amount_cents), 0)).filter(
            PaymentIntent.practice_id == practice_id,
            PaymentIntent.status.in_([PaymentIntentStatus.SENT.value, PaymentIntentStatus.CONFIRMED.value]),
        ).scalar()

        provider_count = db.query(func.count(Provider.id)).filter(
            Provider.practice_id == practice_id, Provider.is_active.is_(True)
        ).scalar() or 0

        contract_count = db.query(func.count(PayerContract.id)).filter(
            PayerContract.practice_id == practice_id
        ).scalar() or 0

        status_counts = {}
        rows = db.query(Claim.status, func.count(Claim.id)).filter(
            Claim.practice_id == practice_id
        ).group_by(Claim.status).all()
        for status, count in rows:
            status_counts[status] = count

        # Payer mix
        payer_mix = []
        payer_rows = db.query(Claim.payer, func.sum(Claim.amount_cents), func.count(Claim.id)).filter(
            Claim.practice_id == practice_id
        ).group_by(Claim.payer).order_by(desc(func.sum(Claim.amount_cents))).limit(10).all()
        for payer_name, billed, count in payer_rows:
            payer_mix.append({
                "payer": payer_name,
                "billed_cents": int(billed) if billed else 0,
                "claim_count": count,
                "share": round(int(billed) / int(total_billed), 4) if total_billed and billed else 0,
            })

        return {
            "practice_id": practice_id,
            "practice_name": practice.name,
            "legal_name": practice.legal_name,
            "status": practice.status,
            "total_claims": total_claims,
            "total_billed_cents": int(total_billed),
            "total_funded_cents": int(total_funded),
            "funding_limit_cents": practice.funding_limit_cents,
            "utilization": round(int(total_funded) / practice.funding_limit_cents, 4) if practice.funding_limit_cents and practice.funding_limit_cents > 0 else None,
            "provider_count": provider_count,
            "contract_count": contract_count,
            "status_counts": status_counts,
            "payer_mix": payer_mix,
            "pms_type": practice.pms_type,
            "clearinghouse": practice.clearinghouse,
        }

    @staticmethod
    def get_payer_performance(db: Session, practice_id: int) -> Dict[str, Any]:
        """Payer performance summary: denial rates, cycle times, reimbursement."""
        claims = db.query(Claim).filter(Claim.practice_id == practice_id).all()
        payments = {
            pi.claim_id: pi
            for pi in db.query(PaymentIntent).filter(PaymentIntent.practice_id == practice_id).all()
        }

        payer_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_claims": 0,
            "denied_claims": 0,
            "total_billed_cents": 0,
            "total_paid_cents": 0,
            "cycle_times_days": [],
        })

        for claim in claims:
            payer = claim.payer or "Unknown"
            stats = payer_stats[payer]
            stats["total_claims"] += 1
            stats["total_billed_cents"] += claim.amount_cents or 0
            if claim.status == ClaimStatus.DECLINED.value:
                stats["denied_claims"] += 1
            pi = payments.get(claim.id)
            if pi and pi.status == PaymentIntentStatus.CONFIRMED.value:
                stats["total_paid_cents"] += pi.amount_cents or 0
                if pi.confirmed_at and pi.created_at:
                    days = (pi.confirmed_at - pi.created_at).total_seconds() / 86400
                    stats["cycle_times_days"].append(days)

        result = {}
        for payer_name, stats in payer_stats.items():
            ct = sorted(stats["cycle_times_days"])
            result[payer_name] = {
                "total_claims": stats["total_claims"],
                "denial_rate": round(stats["denied_claims"] / stats["total_claims"], 4) if stats["total_claims"] > 0 else 0,
                "total_billed_cents": stats["total_billed_cents"],
                "total_paid_cents": stats["total_paid_cents"],
                "realized_rate": round(stats["total_paid_cents"] / stats["total_billed_cents"], 4) if stats["total_billed_cents"] > 0 else None,
                "avg_cycle_days": round(sum(ct) / len(ct), 1) if ct else None,
                "p50_cycle_days": round(ct[len(ct) // 2], 1) if ct else None,
                "p90_cycle_days": round(ct[min(int(len(ct) * 0.9), len(ct) - 1)], 1) if ct else None,
            }

        return {"payers": result, "total_payers": len(result)}

    @staticmethod
    def get_provider_productivity(db: Session, practice_id: int) -> Dict[str, Any]:
        """Provider productivity: claim volume, procedure mix, reimbursement."""
        providers = db.query(Provider).filter(
            Provider.practice_id == practice_id
        ).all()

        result = []
        for provider in providers:
            lines = db.query(ClaimLine).filter(ClaimLine.provider_id == provider.id).all()
            claim_ids = set()
            procedure_counts: Dict[str, int] = defaultdict(int)
            total_billed = 0
            for line in lines:
                claim_ids.add(line.claim_id)
                if line.cdt_code:
                    procedure_counts[line.cdt_code] += 1
                total_billed += line.billed_fee_cents or 0

            # Also count claims directly attributed to provider
            direct_claims = db.query(Claim).filter(
                Claim.practice_id == practice_id,
                Claim.provider_id == provider.id
            ).all()
            for c in direct_claims:
                claim_ids.add(c.id)
                total_billed += c.amount_cents or 0

            top_procedures = sorted(procedure_counts.items(), key=lambda x: -x[1])[:5]

            result.append({
                "id": provider.id,
                "full_name": provider.full_name,
                "specialty": provider.specialty,
                "role": provider.role,
                "is_active": provider.is_active,
                "claim_count": len(claim_ids),
                "total_billed_cents": total_billed,
                "top_procedures": [{"code": code, "count": cnt} for code, cnt in top_procedures],
            })

        return {"providers": result}

    @staticmethod
    def get_procedure_risk_summary(db: Session, practice_id: int) -> Dict[str, Any]:
        """Procedure risk and denial trends by CDT code."""
        claims = db.query(Claim).filter(Claim.practice_id == practice_id).all()
        claim_ids = [c.id for c in claims]

        if not claim_ids:
            return {"procedures": {}, "categories": {}}

        lines = db.query(ClaimLine).filter(ClaimLine.claim_id.in_(claim_ids)).all()
        claim_status_map = {c.id: c.status for c in claims}

        code_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0, "denied": 0, "total_billed_cents": 0, "total_allowed_cents": 0
        })

        for line in lines:
            code = line.cdt_code or "UNKNOWN"
            stats = code_stats[code]
            stats["count"] += 1
            stats["total_billed_cents"] += line.billed_fee_cents or 0
            if line.allowed_fee_cents:
                stats["total_allowed_cents"] += line.allowed_fee_cents
            if claim_status_map.get(line.claim_id) == ClaimStatus.DECLINED.value:
                stats["denied"] += 1

        procedures = {}
        for code, stats in code_stats.items():
            pc = db.query(ProcedureCode).filter(ProcedureCode.cdt_code == code).first()
            procedures[code] = {
                "cdt_code": code,
                "description": pc.short_description if pc else None,
                "category": pc.category if pc else None,
                "count": stats["count"],
                "denial_rate": round(stats["denied"] / stats["count"], 4) if stats["count"] > 0 else 0,
                "total_billed_cents": stats["total_billed_cents"],
                "avg_billed_cents": round(stats["total_billed_cents"] / stats["count"]) if stats["count"] > 0 else 0,
                "risk_notes": pc.risk_notes if pc else None,
                "common_denial_reasons": pc.common_denial_reasons if pc else None,
            }

        # Category aggregation
        category_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"count": 0, "denied": 0, "billed_cents": 0})
        for code, data in procedures.items():
            cat = data.get("category") or "OTHER"
            category_stats[cat]["count"] += data["count"]
            category_stats[cat]["denied"] += round(data["denial_rate"] * data["count"])
            category_stats[cat]["billed_cents"] += data["total_billed_cents"]

        categories = {}
        for cat, stats in category_stats.items():
            categories[cat] = {
                "count": stats["count"],
                "denial_rate": round(stats["denied"] / stats["count"], 4) if stats["count"] > 0 else 0,
                "total_billed_cents": stats["billed_cents"],
            }

        return {"procedures": procedures, "categories": categories}

    @staticmethod
    def get_claim_cycle_times(db: Session, practice_id: int) -> Dict[str, Any]:
        """Claim cycle time analytics."""
        claims = db.query(Claim).filter(Claim.practice_id == practice_id).all()
        payments = {
            pi.claim_id: pi
            for pi in db.query(PaymentIntent).filter(PaymentIntent.practice_id == practice_id).all()
        }

        now = datetime.utcnow()
        aging_buckets = {"0_30": 0, "30_60": 0, "60_90": 0, "90_plus": 0}
        cycle_times = []
        open_claims = 0

        for claim in claims:
            age_days = (now - claim.created_at).days if claim.created_at else 0
            if claim.status not in (ClaimStatus.CLOSED.value, ClaimStatus.DECLINED.value):
                open_claims += 1
                if age_days <= 30:
                    aging_buckets["0_30"] += 1
                elif age_days <= 60:
                    aging_buckets["30_60"] += 1
                elif age_days <= 90:
                    aging_buckets["60_90"] += 1
                else:
                    aging_buckets["90_plus"] += 1

            pi = payments.get(claim.id)
            if pi and pi.confirmed_at and claim.created_at:
                days = (pi.confirmed_at - claim.created_at).total_seconds() / 86400
                cycle_times.append(days)

        sorted_ct = sorted(cycle_times)

        return {
            "open_claims": open_claims,
            "aging_buckets": aging_buckets,
            "avg_cycle_days": round(sum(sorted_ct) / len(sorted_ct), 1) if sorted_ct else None,
            "p50_cycle_days": round(sorted_ct[len(sorted_ct) // 2], 1) if sorted_ct else None,
            "p90_cycle_days": round(sorted_ct[min(int(len(sorted_ct) * 0.9), len(sorted_ct) - 1)], 1) if sorted_ct else None,
            "total_resolved": len(sorted_ct),
        }

    @staticmethod
    def get_reconciliation_summary(db: Session, practice_id: int) -> Dict[str, Any]:
        """Reconciliation summary: remittance match rates, unresolved issues."""
        remittances = db.query(Remittance).filter(
            Remittance.practice_id == practice_id
        ).order_by(desc(Remittance.created_at)).limit(50).all()

        total_remittances = len(remittances)
        total_paid = sum(r.total_paid_cents for r in remittances)
        total_adjustments = sum(r.total_adjustments_cents for r in remittances)

        remittance_ids = [r.id for r in remittances]
        lines = db.query(RemittanceLine).filter(
            RemittanceLine.remittance_id.in_(remittance_ids)
        ).all() if remittance_ids else []

        matched = sum(1 for l in lines if l.match_status == RemittanceLineMatchStatus.MATCHED.value)
        unmatched = sum(1 for l in lines if l.match_status == RemittanceLineMatchStatus.UNMATCHED.value)
        mismatches = sum(1 for l in lines if l.match_status == RemittanceLineMatchStatus.MISMATCH.value)

        recent = []
        for r in remittances[:10]:
            recent.append({
                "id": r.id,
                "payer_name": r.payer_name,
                "trace_number": r.trace_number,
                "payment_date": r.payment_date.isoformat() if r.payment_date else None,
                "total_paid_cents": r.total_paid_cents,
                "total_adjustments_cents": r.total_adjustments_cents,
                "posting_status": r.posting_status,
                "source_type": r.source_type,
            })

        return {
            "total_remittances": total_remittances,
            "total_paid_cents": total_paid,
            "total_adjustments_cents": total_adjustments,
            "total_lines": len(lines),
            "matched_lines": matched,
            "unmatched_lines": unmatched,
            "mismatch_lines": mismatches,
            "match_rate": round(matched / len(lines), 4) if lines else None,
            "recent_remittances": recent,
        }

    @staticmethod
    def get_funding_decisions_summary(db: Session, practice_id: int) -> Dict[str, Any]:
        """Funding decision summary for a practice."""
        claim_ids_q = db.query(Claim.id).filter(Claim.practice_id == practice_id).subquery()
        decisions = db.query(FundingDecision).filter(
            FundingDecision.claim_id.in_(claim_ids_q)
        ).order_by(desc(FundingDecision.created_at)).all()

        counts = defaultdict(int)
        risk_scores = []
        recent = []

        for fd in decisions:
            counts[fd.decision] += 1
            if fd.risk_score is not None:
                risk_scores.append(fd.risk_score)

        for fd in decisions[:10]:
            recent.append({
                "id": fd.id,
                "claim_id": fd.claim_id,
                "decision": fd.decision,
                "advance_rate": fd.advance_rate,
                "max_advance_amount_cents": fd.max_advance_amount_cents,
                "fee_rate": fd.fee_rate,
                "risk_score": fd.risk_score,
                "model_version": fd.model_version,
                "decisioned_at": fd.decisioned_at.isoformat() if fd.decisioned_at else None,
            })

        return {
            "total_decisions": len(decisions),
            "decision_counts": dict(counts),
            "avg_risk_score": round(sum(risk_scores) / len(risk_scores), 4) if risk_scores else None,
            "recent_decisions": recent,
        }
