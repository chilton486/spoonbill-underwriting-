import csv
import io
import logging
from typing import List, Dict

from ..schemas.integration import ExternalClaim, ExternalClaimLine

logger = logging.getLogger(__name__)

REQUIRED_CLAIM_FIELDS = {"external_claim_id", "payer", "total_billed_cents"}
REQUIRED_LINE_FIELDS = {"external_claim_id", "external_line_id", "cdt_code", "line_amount_cents"}


def parse_claims_csv(content: str) -> List[Dict]:
    reader = csv.DictReader(io.StringIO(content))
    fieldnames = set(reader.fieldnames or [])
    missing = REQUIRED_CLAIM_FIELDS - fieldnames
    if missing:
        raise ValueError(f"Claims CSV missing required columns: {', '.join(sorted(missing))}")
    return list(reader)


def parse_lines_csv(content: str) -> List[Dict]:
    reader = csv.DictReader(io.StringIO(content))
    fieldnames = set(reader.fieldnames or [])
    missing = REQUIRED_LINE_FIELDS - fieldnames
    if missing:
        raise ValueError(f"Claim lines CSV missing required columns: {', '.join(sorted(missing))}")
    return list(reader)


def build_external_claims(
    claim_rows: List[Dict],
    line_rows: List[Dict] = None,
) -> List[ExternalClaim]:
    lines_by_claim: Dict[str, List[ExternalClaimLine]] = {}
    if line_rows:
        for row in line_rows:
            claim_id = row["external_claim_id"].strip()
            line = ExternalClaimLine(
                external_line_id=row["external_line_id"].strip(),
                cdt_code=row["cdt_code"].strip(),
                description=row.get("description", "").strip() or None,
                line_amount_cents=int(row["line_amount_cents"]),
                tooth_number=row.get("tooth_number", "").strip() or None,
                surface=row.get("surface", "").strip() or None,
            )
            lines_by_claim.setdefault(claim_id, []).append(line)

    claims = []
    for row in claim_rows:
        ext_id = row["external_claim_id"].strip()
        claim = ExternalClaim(
            external_claim_id=ext_id,
            external_patient_id=row.get("external_patient_id", "").strip() or None,
            payer=row["payer"].strip(),
            total_billed_cents=int(row["total_billed_cents"]),
            procedure_date=row.get("procedure_date", "").strip() or None,
            submitted_date=row.get("submitted_date", "").strip() or None,
            procedure_codes=row.get("procedure_codes", "").strip() or None,
            lines=lines_by_claim.get(ext_id, []),
        )
        claims.append(claim)

    return claims
