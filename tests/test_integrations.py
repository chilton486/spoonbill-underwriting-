import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from app.schemas.integration import ExternalClaim, ExternalClaimLine, IngestionSummary
from app.integrations.csv_parser import parse_claims_csv, parse_lines_csv, build_external_claims
from app.integrations.open_dental.provider import OpenDentalProvider, OpenDentalNotConfigured
from app.models.integration import IntegrationProvider, IntegrationStatus, SyncRunStatus


class TestExternalClaimSchema:
    def test_valid_claim(self):
        claim = ExternalClaim(
            external_claim_id="OD-1001",
            payer="Delta Dental",
            total_billed_cents=45000,
            procedure_date=date(2026, 1, 15),
        )
        assert claim.external_claim_id == "OD-1001"
        assert claim.payer == "Delta Dental"
        assert claim.total_billed_cents == 45000

    def test_claim_with_lines(self):
        claim = ExternalClaim(
            external_claim_id="OD-1002",
            payer="MetLife",
            total_billed_cents=120000,
            lines=[
                ExternalClaimLine(
                    external_line_id="LN-1",
                    cdt_code="D2740",
                    line_amount_cents=120000,
                ),
            ],
        )
        assert len(claim.lines) == 1
        assert claim.lines[0].cdt_code == "D2740"

    def test_claim_payer_cannot_be_empty(self):
        with pytest.raises(ValueError):
            ExternalClaim(
                external_claim_id="OD-1003",
                payer="",
                total_billed_cents=10000,
            )

    def test_claim_amount_must_be_positive(self):
        with pytest.raises(ValueError):
            ExternalClaim(
                external_claim_id="OD-1004",
                payer="Cigna",
                total_billed_cents=0,
            )

    def test_line_amount_must_be_positive(self):
        with pytest.raises(ValueError):
            ExternalClaimLine(
                external_line_id="LN-1",
                cdt_code="D0120",
                line_amount_cents=-100,
            )


class TestCSVParser:
    def test_parse_valid_claims_csv(self):
        csv_content = (
            "external_claim_id,payer,total_billed_cents,procedure_date\n"
            "OD-1001,Delta Dental,45000,2026-01-15\n"
            "OD-1002,MetLife,120000,2026-01-18\n"
        )
        rows = parse_claims_csv(csv_content)
        assert len(rows) == 2
        assert rows[0]["external_claim_id"] == "OD-1001"
        assert rows[1]["payer"] == "MetLife"

    def test_parse_claims_csv_missing_required_column(self):
        csv_content = "external_claim_id,total_billed_cents\nOD-1001,45000\n"
        with pytest.raises(ValueError, match="payer"):
            parse_claims_csv(csv_content)

    def test_parse_valid_lines_csv(self):
        csv_content = (
            "external_claim_id,external_line_id,cdt_code,line_amount_cents\n"
            "OD-1001,LN-1,D0120,5000\n"
        )
        rows = parse_lines_csv(csv_content)
        assert len(rows) == 1
        assert rows[0]["cdt_code"] == "D0120"

    def test_parse_lines_csv_missing_required_column(self):
        csv_content = "external_claim_id,external_line_id,line_amount_cents\nOD-1001,LN-1,5000\n"
        with pytest.raises(ValueError, match="cdt_code"):
            parse_lines_csv(csv_content)

    def test_build_external_claims_without_lines(self):
        claim_rows = [
            {"external_claim_id": "OD-1001", "payer": "Delta Dental", "total_billed_cents": "45000", "procedure_date": "2026-01-15"},
        ]
        claims = build_external_claims(claim_rows)
        assert len(claims) == 1
        assert claims[0].external_claim_id == "OD-1001"
        assert claims[0].total_billed_cents == 45000
        assert len(claims[0].lines) == 0

    def test_build_external_claims_with_lines(self):
        claim_rows = [
            {"external_claim_id": "OD-1001", "payer": "Delta Dental", "total_billed_cents": "45000"},
        ]
        line_rows = [
            {"external_claim_id": "OD-1001", "external_line_id": "LN-1", "cdt_code": "D0120", "line_amount_cents": "5000"},
            {"external_claim_id": "OD-1001", "external_line_id": "LN-2", "cdt_code": "D1110", "line_amount_cents": "40000"},
        ]
        claims = build_external_claims(claim_rows, line_rows)
        assert len(claims) == 1
        assert len(claims[0].lines) == 2
        assert claims[0].lines[0].cdt_code == "D0120"
        assert claims[0].lines[1].cdt_code == "D1110"

    def test_build_external_claims_lines_matched_by_claim_id(self):
        claim_rows = [
            {"external_claim_id": "OD-1001", "payer": "Delta", "total_billed_cents": "10000"},
            {"external_claim_id": "OD-1002", "payer": "MetLife", "total_billed_cents": "20000"},
        ]
        line_rows = [
            {"external_claim_id": "OD-1001", "external_line_id": "LN-1", "cdt_code": "D0120", "line_amount_cents": "10000"},
            {"external_claim_id": "OD-1002", "external_line_id": "LN-2", "cdt_code": "D2740", "line_amount_cents": "20000"},
        ]
        claims = build_external_claims(claim_rows, line_rows)
        assert len(claims) == 2
        assert len(claims[0].lines) == 1
        assert claims[0].lines[0].external_line_id == "LN-1"
        assert len(claims[1].lines) == 1
        assert claims[1].lines[0].external_line_id == "LN-2"


class TestOpenDentalProvider:
    def test_not_configured_raises(self):
        provider = OpenDentalProvider()
        assert not provider.is_configured()
        with pytest.raises(OpenDentalNotConfigured):
            provider.fetch_updated_claims()

    def test_configured_but_not_implemented(self):
        import json
        config = json.dumps({
            "base_url": "https://api.opendental.com",
            "developer_key": "test-dev-key",
            "customer_key": "test-cust-key",
        })
        provider = OpenDentalProvider(config_json=config)
        assert provider.is_configured()
        with pytest.raises(NotImplementedError):
            provider.fetch_updated_claims()

    def test_map_od_claim(self):
        provider = OpenDentalProvider()
        raw = {
            "ClaimNum": "12345",
            "PatNum": "67890",
            "CarrierName": "Delta Dental",
            "ClaimFee": "450.00",
            "DateService": "2026-01-15",
            "DateSent": "2026-01-16",
            "procedures": [
                {"ProcNum": "1", "CodeNum": "D0120", "Descript": "Eval", "ProcFee": "50.00"},
                {"ProcNum": "2", "CodeNum": "D1110", "Descript": "Cleaning", "ProcFee": "400.00"},
            ],
        }
        claim = provider._map_od_claim(raw)
        assert claim.external_claim_id == "12345"
        assert claim.external_patient_id == "67890"
        assert claim.payer == "Delta Dental"
        assert claim.total_billed_cents == 45000
        assert len(claim.lines) == 2


class TestIngestionIdempotency:
    def test_ingest_creates_new_claims(self):
        from app.services.ingestion import ingest_external_claims
        from app.models.claim import Claim, ClaimStatus

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        claims = [
            ExternalClaim(
                external_claim_id="OD-1001",
                payer="Delta Dental",
                total_billed_cents=45000,
                procedure_date=date(2026, 1, 15),
            ),
        ]

        summary = ingest_external_claims(mock_db, practice_id=1, external_claims=claims)
        assert summary.total_received == 1
        assert summary.created == 1
        assert summary.updated == 0
        assert summary.skipped == 0

    def test_ingest_updates_existing_claim(self):
        from app.services.ingestion import ingest_external_claims
        from app.models.claim import Claim, ClaimStatus

        existing_claim = MagicMock()
        existing_claim.id = 1
        existing_claim.payer = "Old Payer"
        existing_claim.amount_cents = 10000
        existing_claim.procedure_date = date(2026, 1, 1)
        existing_claim.procedure_codes = None
        existing_claim.external_source = None

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_claim

        claims = [
            ExternalClaim(
                external_claim_id="OD-1001",
                payer="New Payer",
                total_billed_cents=50000,
                procedure_date=date(2026, 1, 15),
            ),
        ]

        summary = ingest_external_claims(mock_db, practice_id=1, external_claims=claims)
        assert summary.total_received == 1
        assert summary.created == 0
        assert summary.updated == 1
        assert existing_claim.payer == "New Payer"
        assert existing_claim.amount_cents == 50000

    def test_ingest_skips_unchanged_claim(self):
        from app.services.ingestion import ingest_external_claims

        existing_claim = MagicMock()
        existing_claim.id = 1
        existing_claim.payer = "Delta Dental"
        existing_claim.amount_cents = 45000
        existing_claim.procedure_date = date(2026, 1, 15)
        existing_claim.procedure_codes = None
        existing_claim.external_source = "OPEN_DENTAL"

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = existing_claim

        claims = [
            ExternalClaim(
                external_claim_id="OD-1001",
                payer="Delta Dental",
                total_billed_cents=45000,
                procedure_date=date(2026, 1, 15),
            ),
        ]

        summary = ingest_external_claims(mock_db, practice_id=1, external_claims=claims)
        assert summary.total_received == 1
        assert summary.created == 0
        assert summary.updated == 0
        assert summary.skipped == 1

    def test_ingest_handles_errors_gracefully(self):
        from app.services.ingestion import ingest_external_claims

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = Exception("DB error")

        claims = [
            ExternalClaim(
                external_claim_id="OD-1001",
                payer="Delta",
                total_billed_cents=10000,
            ),
        ]

        summary = ingest_external_claims(mock_db, practice_id=1, external_claims=claims)
        assert summary.total_received == 1
        assert summary.errors == ["OD-1001: DB error"]


class TestIntegrationEnums:
    def test_provider_values(self):
        assert IntegrationProvider.OPEN_DENTAL.value == "OPEN_DENTAL"

    def test_status_values(self):
        assert IntegrationStatus.ACTIVE.value == "ACTIVE"
        assert IntegrationStatus.INACTIVE.value == "INACTIVE"
        assert IntegrationStatus.ERROR.value == "ERROR"

    def test_sync_run_status_values(self):
        assert SyncRunStatus.RUNNING.value == "RUNNING"
        assert SyncRunStatus.SUCCEEDED.value == "SUCCEEDED"
        assert SyncRunStatus.FAILED.value == "FAILED"


class TestIngestionSummary:
    def test_summary_model(self):
        summary = IngestionSummary(
            total_received=5,
            created=3,
            updated=1,
            skipped=1,
        )
        assert summary.total_received == 5
        assert summary.created == 3
        assert summary.errors == []

    def test_summary_with_errors(self):
        summary = IngestionSummary(
            total_received=2,
            created=1,
            updated=0,
            skipped=0,
            errors=["OD-1002: validation error"],
        )
        assert len(summary.errors) == 1
