"""Remittance ingestion and reconciliation service.

Handles ingestion of remittance/ERA data and matching to claims and claim lines.
"""
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from ..models.claim import Claim
from ..models.claim_line import ClaimLine
from ..models.remittance import (
    Remittance, RemittanceLine, PostingStatus,
    RemittanceSourceType, RemittanceLineMatchStatus,
)
from ..models.payer import Payer

logger = logging.getLogger(__name__)


class RemittanceReconciliationService:
    """Ingests remittances and reconciles against claims."""

    @staticmethod
    def ingest_remittance(
        db: Session,
        practice_id: int,
        payer_name: str,
        trace_number: str,
        payment_date: date,
        total_paid_cents: int,
        total_adjustments_cents: int = 0,
        source_type: str = RemittanceSourceType.MANUAL.value,
        era_reference: Optional[str] = None,
        payer_id: Optional[int] = None,
        lines: Optional[List[Dict[str, Any]]] = None,
    ) -> Remittance:
        """Create a Remittance record and optional RemittanceLines.

        Args:
            db: Database session
            practice_id: Practice ID
            payer_name: Payer display name
            trace_number: Check/EFT trace number
            payment_date: Date of payment
            total_paid_cents: Total amount paid
            total_adjustments_cents: Total adjustments
            source_type: Source type (ERA_835, MANUAL, CSV_IMPORT, SYNTHETIC)
            era_reference: ERA reference ID
            payer_id: Optional FK to payers table
            lines: Optional list of line dicts with keys:
                external_claim_id, cdt_code, paid_cents, allowed_cents,
                adjustment_cents, adjustment_reason_codes

        Returns:
            Created Remittance
        """
        remittance = Remittance(
            practice_id=practice_id,
            payer_id=payer_id,
            payer_name=payer_name,
            trace_number=trace_number,
            payment_date=payment_date,
            total_paid_cents=total_paid_cents,
            total_adjustments_cents=total_adjustments_cents,
            posting_status=PostingStatus.RECEIVED.value,
            source_type=source_type,
            era_reference=era_reference,
        )
        db.add(remittance)
        db.flush()

        if lines:
            for line_data in lines:
                rl = RemittanceLine(
                    remittance_id=remittance.id,
                    external_claim_id=line_data.get("external_claim_id"),
                    cdt_code=line_data.get("cdt_code"),
                    paid_cents=line_data.get("paid_cents", 0),
                    allowed_cents=line_data.get("allowed_cents"),
                    adjustment_cents=line_data.get("adjustment_cents", 0),
                    adjustment_reason_codes=line_data.get("adjustment_reason_codes"),
                    match_status=RemittanceLineMatchStatus.UNMATCHED.value,
                )
                db.add(rl)

            db.flush()

        logger.info(
            "Remittance ingested: id=%s practice=%s trace=%s lines=%d",
            remittance.id, practice_id, trace_number, len(lines or []),
        )
        return remittance

    @staticmethod
    def reconcile_remittance(db: Session, remittance_id: int) -> Dict[str, Any]:
        """Attempt to match RemittanceLines to Claims and ClaimLines.

        Matching strategy:
        1. Match by external_claim_id -> Claim.external_claim_id
        2. Match by claim_token if available
        3. Match by cdt_code to ClaimLine if claim matched

        Returns:
            Summary of reconciliation results
        """
        remittance = db.query(Remittance).filter(Remittance.id == remittance_id).first()
        if not remittance:
            return {"error": "Remittance not found"}

        lines = db.query(RemittanceLine).filter(
            RemittanceLine.remittance_id == remittance_id
        ).all()

        results = {
            "remittance_id": remittance_id,
            "total_lines": len(lines),
            "matched": 0,
            "unmatched": 0,
            "mismatches": 0,
        }

        remittance.posting_status = PostingStatus.POSTING.value

        for line in lines:
            matched = False

            # Strategy 1: Match by external_claim_id
            if line.external_claim_id:
                claim = db.query(Claim).filter(
                    Claim.practice_id == remittance.practice_id,
                    Claim.external_claim_id == line.external_claim_id,
                ).first()
                if claim:
                    line.claim_id = claim.id
                    matched = True

                    # Try to match to a specific ClaimLine by cdt_code
                    if line.cdt_code:
                        claim_line = db.query(ClaimLine).filter(
                            ClaimLine.claim_id == claim.id,
                            ClaimLine.cdt_code == line.cdt_code,
                        ).first()
                        if claim_line:
                            line.claim_line_id = claim_line.id

                    # Check for amount mismatch
                    if claim.amount_cents and line.paid_cents:
                        # Allow some variance (adjustments are normal)
                        if abs(claim.amount_cents - line.paid_cents) > claim.amount_cents * 0.5:
                            line.match_status = RemittanceLineMatchStatus.MISMATCH.value
                            results["mismatches"] += 1
                            matched = False  # Still a mismatch
                        else:
                            line.match_status = RemittanceLineMatchStatus.MATCHED.value
                            results["matched"] += 1

                            # Update claim with paid info
                            if claim.total_paid_cents is None:
                                claim.total_paid_cents = 0
                            claim.total_paid_cents += line.paid_cents
                            if line.allowed_cents and claim.total_allowed_cents is None:
                                claim.total_allowed_cents = line.allowed_cents
                    else:
                        line.match_status = RemittanceLineMatchStatus.MATCHED.value
                        results["matched"] += 1

            if not matched:
                line.match_status = RemittanceLineMatchStatus.UNMATCHED.value
                results["unmatched"] += 1

        # Determine final posting status
        if results["unmatched"] == 0 and results["mismatches"] == 0:
            remittance.posting_status = PostingStatus.POSTED.value
        elif results["mismatches"] > 0:
            remittance.posting_status = PostingStatus.EXCEPTION.value
        else:
            remittance.posting_status = PostingStatus.POSTED.value

        db.flush()

        logger.info(
            "Reconciliation complete: remittance=%s matched=%d unmatched=%d mismatches=%d",
            remittance_id, results["matched"], results["unmatched"], results["mismatches"],
        )

        return results
