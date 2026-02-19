import json
import logging
from typing import List, Optional, Tuple

from ...schemas.integration import ExternalClaim, ExternalClaimLine

logger = logging.getLogger(__name__)


class OpenDentalNotConfigured(Exception):
    pass


class OpenDentalProvider:
    def __init__(self, config_json: Optional[str] = None, secrets_ref: Optional[str] = None):
        self.config = json.loads(config_json) if config_json else {}
        self.secrets_ref = secrets_ref
        self.base_url = self.config.get("base_url", "")
        self.developer_key = self.config.get("developer_key", "")
        self.customer_key = self.config.get("customer_key", "")

    def is_configured(self) -> bool:
        return bool(self.base_url and self.developer_key and self.customer_key)

    def fetch_updated_claims(
        self, cursor: Optional[str] = None
    ) -> Tuple[List[ExternalClaim], Optional[str]]:
        if not self.is_configured():
            raise OpenDentalNotConfigured(
                "Open Dental API credentials not configured. "
                "Set base_url, developer_key, and customer_key in IntegrationConnection.config_json. "
                "Use CSV upload as fallback."
            )

        raise NotImplementedError(
            "Open Dental Cloud API integration pending. "
            "Endpoint scaffolding ready — implement when API docs and credentials are available. "
            "Use CSV upload path for pilot."
        )

    def _map_od_claim(self, raw: dict) -> ExternalClaim:
        lines = []
        for proc in raw.get("procedures", []):
            lines.append(
                ExternalClaimLine(
                    external_line_id=str(proc.get("ProcNum", "")),
                    cdt_code=proc.get("CodeNum", ""),
                    description=proc.get("Descript", ""),
                    line_amount_cents=int(float(proc.get("ProcFee", 0)) * 100),
                    tooth_number=proc.get("ToothNum"),
                    surface=proc.get("Surf"),
                )
            )

        total_cents = int(float(raw.get("ClaimFee", 0)) * 100)
        if total_cents <= 0 and lines:
            total_cents = sum(l.line_amount_cents for l in lines)

        return ExternalClaim(
            external_claim_id=str(raw.get("ClaimNum", "")),
            external_patient_id=str(raw.get("PatNum", "")),
            payer=raw.get("CarrierName", raw.get("InsPayAmt", "Unknown")),
            total_billed_cents=total_cents,
            procedure_date=raw.get("DateService"),
            submitted_date=raw.get("DateSent"),
            procedure_codes=",".join(l.cdt_code for l in lines) if lines else None,
            lines=lines,
        )
