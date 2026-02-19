import logging
from typing import List

from sqlalchemy.orm import Session

from ..models.claim import Claim, ClaimStatus
from ..schemas.integration import ExternalClaim, IngestionSummary
from ..services.audit import AuditService

logger = logging.getLogger(__name__)


def ingest_external_claims(
    db: Session,
    practice_id: int,
    external_claims: List[ExternalClaim],
    source: str = "OPEN_DENTAL",
    actor_user_id: int = None,
) -> IngestionSummary:
    created = 0
    updated = 0
    skipped = 0
    errors: List[str] = []

    for ext in external_claims:
        try:
            existing = db.query(Claim).filter(
                Claim.practice_id == practice_id,
                Claim.external_claim_id == ext.external_claim_id,
            ).first()

            procedure_codes = ext.procedure_codes
            if not procedure_codes and ext.lines:
                procedure_codes = ",".join(line.cdt_code for line in ext.lines)

            if existing:
                changed = False
                if existing.payer != ext.payer:
                    changed = True
                    existing.payer = ext.payer
                if existing.amount_cents != ext.total_billed_cents:
                    changed = True
                    existing.amount_cents = ext.total_billed_cents
                if ext.procedure_date and existing.procedure_date != ext.procedure_date:
                    changed = True
                    existing.procedure_date = ext.procedure_date
                if procedure_codes and existing.procedure_codes != procedure_codes:
                    changed = True
                    existing.procedure_codes = procedure_codes
                if existing.external_source != source:
                    changed = True
                    existing.external_source = source

                if changed:
                    AuditService.log_event(
                        db,
                        claim_id=existing.id,
                        action="CLAIM_UPDATED_VIA_SYNC",
                        actor_user_id=actor_user_id,
                        metadata={
                            "external_claim_id": ext.external_claim_id,
                            "source": source,
                        },
                    )
                    updated += 1
                else:
                    skipped += 1
            else:
                claim = Claim(
                    practice_id=practice_id,
                    payer=ext.payer,
                    amount_cents=ext.total_billed_cents,
                    procedure_date=ext.procedure_date,
                    external_claim_id=ext.external_claim_id,
                    external_source=source,
                    procedure_codes=procedure_codes,
                    claim_token=Claim.generate_claim_token(),
                    status=ClaimStatus.NEW.value,
                )
                db.add(claim)
                db.flush()

                AuditService.log_event(
                    db,
                    claim_id=claim.id,
                    action="CLAIM_IMPORTED",
                    to_status=ClaimStatus.NEW.value,
                    actor_user_id=actor_user_id,
                    metadata={
                        "external_claim_id": ext.external_claim_id,
                        "source": source,
                    },
                )
                created += 1

        except Exception as e:
            logger.error("Failed to ingest claim %s: %s", ext.external_claim_id, str(e))
            errors.append(f"{ext.external_claim_id}: {str(e)}")

    return IngestionSummary(
        total_received=len(external_claims),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )
