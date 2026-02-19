"""Tests for Dental Financial Ontology (Phases 1-8)."""
import json
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.practice import Practice
from app.models.claim import Claim, ClaimStatus
from app.models.payment import PaymentIntent, PaymentIntentStatus, PaymentProvider
from app.models.user import User, UserRole
from app.models.ontology import OntologyObject, OntologyObjectType, OntologyLink, OntologyLinkType, KPIObservation, MetricTimeseries
from app.services.ontology_v2 import OntologyBuilderV2
from app.services.ontology_brief import _template_generate, _validate_brief


DATABASE_URL = "postgresql://spoonbill:spoonbill_dev@localhost:5432/spoonbill"

engine = create_engine(DATABASE_URL)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db(setup_db):
    session = TestSession()
    try:
        for table_name in ['practices', 'claims']:
            session.execute(text(f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), COALESCE((SELECT MAX(id) FROM {table_name}), 0) + 1, false)"))
        session.commit()
        yield session
    finally:
        session.rollback()
        for tbl in (MetricTimeseries, KPIObservation, OntologyLink, OntologyObject):
            session.query(tbl).delete()
        session.commit()
        session.close()


def _create_practice(db, name="Test Practice", limit=100_000_00):
    p = Practice(name=name, status="ACTIVE", funding_limit_cents=limit)
    db.add(p)
    db.flush()
    return p


def _create_claim(db, practice_id, payer="Delta Dental", amount=50000, status=ClaimStatus.APPROVED.value, codes="D0120,D1110"):
    c = Claim(
        practice_id=practice_id,
        patient_name="Test Patient",
        payer=payer,
        amount_cents=amount,
        status=status,
        claim_token=Claim.generate_claim_token(),
        fingerprint=f"test-{practice_id}-{Claim.generate_claim_token()}",
        procedure_codes=codes,
    )
    db.add(c)
    db.flush()
    return c


def _create_payment(db, claim_id, practice_id, amount, status=PaymentIntentStatus.CONFIRMED.value):
    pi = PaymentIntent(
        claim_id=claim_id,
        practice_id=practice_id,
        amount_cents=amount,
        currency="USD",
        status=status,
        idempotency_key=f"test-{claim_id}-{Claim.generate_claim_token()}",
        provider=PaymentProvider.SIMULATED.value,
        sent_at=datetime.utcnow() - timedelta(hours=24),
        confirmed_at=datetime.utcnow() if status == PaymentIntentStatus.CONFIRMED.value else None,
    )
    db.add(pi)
    db.flush()
    return pi


class TestOntologyContextSchema:

    def test_context_has_required_keys(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental", amount=50000)
        _create_claim(db, practice.id, payer="Cigna", amount=30000)

        context = OntologyBuilderV2.get_practice_context(db, practice.id)

        assert context["version"] == "ontology-v2"
        assert "practice" in context
        assert "snapshot" in context

        snapshot = context["snapshot"]
        assert "totals" in snapshot
        assert "funding" in snapshot
        assert "payer_mix" in snapshot
        assert "procedure_mix" in snapshot
        assert "cohorts" in snapshot
        assert "denials" in snapshot
        assert "risk_flags" in snapshot
        assert "missing_data" in snapshot

    def test_context_totals_correct(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, amount=50000)
        _create_claim(db, practice.id, amount=30000)
        _create_claim(db, practice.id, amount=20000, status=ClaimStatus.DECLINED.value)

        context = OntologyBuilderV2.get_practice_context(db, practice.id)
        totals = context["snapshot"]["totals"]

        assert totals["total_claims"] == 3
        assert totals["total_billed_cents"] == 100000

    def test_context_payer_mix(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental", amount=70000)
        _create_claim(db, practice.id, payer="Cigna", amount=30000)

        context = OntologyBuilderV2.get_practice_context(db, practice.id)
        payer_mix = context["snapshot"]["payer_mix"]

        assert len(payer_mix) == 2
        assert payer_mix[0]["payer"] == "Delta Dental"
        assert payer_mix[0]["share"] == 0.7

    def test_context_denial_rate(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, amount=50000, status=ClaimStatus.APPROVED.value)
        _create_claim(db, practice.id, amount=50000, status=ClaimStatus.DECLINED.value)

        context = OntologyBuilderV2.get_practice_context(db, practice.id)
        denials = context["snapshot"]["denials"]

        assert denials["denial_rate"] == 0.5
        assert denials["declined_count"] == 1

    def test_context_utilization(self, db):
        practice = _create_practice(db, limit=100_000)
        c = _create_claim(db, practice.id, amount=50000, status=ClaimStatus.PAID.value)
        _create_payment(db, c.id, practice.id, 50000)

        context = OntologyBuilderV2.get_practice_context(db, practice.id)
        funding = context["snapshot"]["funding"]

        assert funding["utilization"] == 0.5

    def test_risk_flag_payer_concentration(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Monopoly Dental", amount=90000)
        _create_claim(db, practice.id, payer="Other", amount=10000)

        context = OntologyBuilderV2.get_practice_context(db, practice.id)
        flags = context["snapshot"]["risk_flags"]

        flag_names = [f["flag"] for f in flags]
        assert "PAYER_CONCENTRATION" in flag_names

    def test_risk_flag_high_denial(self, db):
        practice = _create_practice(db)
        for _ in range(8):
            _create_claim(db, practice.id, status=ClaimStatus.APPROVED.value)
        for _ in range(3):
            _create_claim(db, practice.id, status=ClaimStatus.DECLINED.value)

        context = OntologyBuilderV2.get_practice_context(db, practice.id)
        flags = context["snapshot"]["risk_flags"]

        flag_names = [f["flag"] for f in flags]
        assert "HIGH_DENIAL_RATE" in flag_names

    def test_missing_data_reported(self, db):
        practice = _create_practice(db, limit=None)
        _create_claim(db, practice.id)

        context = OntologyBuilderV2.get_practice_context(db, practice.id)
        missing = context["snapshot"]["missing_data"]

        assert any("funded_utilization" in m for m in missing)

    def test_practice_isolation(self, db):
        p1 = _create_practice(db, name="Practice A")
        p2 = _create_practice(db, name="Practice B")
        _create_claim(db, p1.id, payer="P1 Payer", amount=50000)
        _create_claim(db, p2.id, payer="P2 Payer", amount=30000)

        ctx1 = OntologyBuilderV2.get_practice_context(db, p1.id)
        ctx2 = OntologyBuilderV2.get_practice_context(db, p2.id)

        assert ctx1["snapshot"]["totals"]["total_claims"] == 1
        assert ctx2["snapshot"]["totals"]["total_claims"] == 1
        assert ctx1["snapshot"]["payer_mix"][0]["payer"] == "P1 Payer"
        assert ctx2["snapshot"]["payer_mix"][0]["payer"] == "P2 Payer"


class TestOntologyBuilder:

    def test_build_creates_objects(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental", codes="D0120")

        result = OntologyBuilderV2.build_practice_ontology(db, practice.id)

        assert result["objects"] > 0
        assert result["metrics"] > 0

        objects = db.query(OntologyObject).filter(OntologyObject.practice_id == practice.id).all()
        assert len(objects) >= 3

        links = db.query(OntologyLink).filter(OntologyLink.practice_id == practice.id).all()
        assert len(links) >= 1

        kpis = db.query(KPIObservation).filter(KPIObservation.practice_id == practice.id).all()
        assert len(kpis) > 0

    def test_build_idempotent(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        count1 = db.query(OntologyObject).filter(OntologyObject.practice_id == practice.id).count()

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        count2 = db.query(OntologyObject).filter(OntologyObject.practice_id == practice.id).count()

        assert count1 == count2


class TestBriefSchema:

    def test_template_brief_has_required_keys(self):
        context = {
            "version": "ontology-v1",
            "practice": {"id": 1, "name": "Test", "status": "ACTIVE", "funding_limit_cents": 100000},
            "snapshot": {
                "totals": {"total_claims": 10, "total_billed_cents": 500000},
                "funding": {"total_funded_cents": 300000, "total_confirmed_cents": 200000, "funding_limit_cents": 100000, "utilization": 0.3},
                "payer_mix": [{"payer": "Delta", "billed_cents": 300000, "share": 0.6}],
                "procedure_mix": [{"cdt_code": "D0120", "count": 5, "share": 0.5}],
                "cohorts": {"avg_lag_days": 2.5, "p50_lag_days": 2.0, "p90_lag_days": 5.0, "sample_size": 5},
                "denials": {"denial_rate": 0.1, "declined_count": 1, "exception_rate": 0.0, "exception_count": 0},
                "risk_flags": [],
                "missing_data": [],
            },
        }

        brief = _template_generate(context)

        assert _validate_brief(brief)
        assert "summary" in brief
        assert isinstance(brief["key_drivers"], list)
        assert isinstance(brief["risks"], list)
        assert isinstance(brief["recommended_actions"], list)
        assert isinstance(brief["missing_data"], list)

    def test_template_brief_recommends_adjust_limit_when_high_utilization(self):
        context = {
            "version": "ontology-v1",
            "practice": {"id": 1, "name": "Test", "status": "ACTIVE", "funding_limit_cents": 100000},
            "snapshot": {
                "totals": {"total_claims": 10, "total_billed_cents": 500000},
                "funding": {"total_funded_cents": 90000, "total_confirmed_cents": 90000, "funding_limit_cents": 100000, "utilization": 0.9},
                "payer_mix": [{"payer": "Delta", "billed_cents": 500000, "share": 1.0}],
                "procedure_mix": [],
                "cohorts": {"avg_lag_days": None, "p50_lag_days": None, "p90_lag_days": None, "sample_size": 0},
                "denials": {"denial_rate": 0.0, "declined_count": 0, "exception_rate": 0.0, "exception_count": 0},
                "risk_flags": [{"flag": "HIGH_UTILIZATION", "metric": "funded_utilization", "value": 0.9, "threshold": 0.85, "detail": "High utilization"}],
                "missing_data": [],
            },
        }

        brief = _template_generate(context)
        actions = [a["action"] for a in brief["recommended_actions"]]
        assert "ADJUST_LIMIT" in actions

    def test_validate_brief_rejects_invalid(self):
        assert not _validate_brief({})
        assert not _validate_brief({"summary": "test"})
        assert not _validate_brief("not a dict")


class TestPatientOntology:

    def test_build_creates_patient_objects(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental")
        _create_claim(db, practice.id, payer="Cigna")

        OntologyBuilderV2.build_practice_ontology(db, practice.id)

        patients = db.query(OntologyObject).filter(
            OntologyObject.practice_id == practice.id,
            OntologyObject.object_type == OntologyObjectType.PATIENT.value,
        ).all()
        assert len(patients) >= 1

        for p in patients:
            props = p.properties_json
            assert "patient_hash" in props
            assert "age_bucket" in props
            assert "insurance_type" in props
            assert "claim_count" in props
            assert props["claim_count"] >= 1

    def test_patient_links_created(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)

        links = db.query(OntologyLink).filter(
            OntologyLink.practice_id == practice.id,
            OntologyLink.link_type == OntologyLinkType.CLAIM_BELONGS_TO_PATIENT.value,
        ).all()
        assert len(links) >= 1

    def test_patient_dynamics_in_context(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental", amount=50000)
        _create_claim(db, practice.id, payer="Cigna", amount=30000)

        context = OntologyBuilderV2.get_practice_context(db, practice.id)
        pd = context["snapshot"]["patient_dynamics"]

        assert "total_patients" in pd
        assert pd["total_patients"] >= 1
        assert "revenue_per_patient_cents" in pd
        assert "repeat_visit_rate" in pd
        assert "age_mix" in pd
        assert "insurance_mix" in pd


class TestCFO360:

    def test_cfo_schema(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental", amount=50000)
        c = _create_claim(db, practice.id, payer="Cigna", amount=30000, status=ClaimStatus.PAID.value)
        _create_payment(db, c.id, practice.id, 30000)

        cfo = OntologyBuilderV2.get_cfo_360(db, practice.id)

        assert "capital" in cfo
        assert "revenue" in cfo
        assert "payer_risk" in cfo
        assert "patient_dynamics" in cfo
        assert "operational_risk" in cfo
        assert "growth" in cfo

    def test_cfo_capital_values(self, db):
        practice = _create_practice(db, limit=200_000)
        c = _create_claim(db, practice.id, amount=100_000, status=ClaimStatus.PAID.value)
        _create_payment(db, c.id, practice.id, 100_000)

        cfo = OntologyBuilderV2.get_cfo_360(db, practice.id)
        capital = cfo["capital"]

        assert capital["total_funded_cents"] == 100_000
        assert capital["funding_limit_cents"] == 200_000
        assert capital["available_capacity_cents"] == 100_000
        assert capital["utilization"] == 0.5

    def test_cfo_payer_risk(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Monopoly Dental", amount=90000)
        _create_claim(db, practice.id, payer="Other", amount=10000)

        cfo = OntologyBuilderV2.get_cfo_360(db, practice.id)
        assert cfo["payer_risk"]["concentration"] == 0.9
        assert cfo["payer_risk"]["top_payer"] == "Monopoly Dental"


class TestRiskEngine:

    def test_payer_concentration_risk(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Monopoly Dental", amount=80000)
        _create_claim(db, practice.id, payer="Other", amount=20000)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        risks = OntologyBuilderV2.get_risks(db, practice.id)

        types = [r["type"] for r in risks]
        assert "PAYER_CONCENTRATION_RISK" in types

    def test_no_risks_for_healthy_practice(self, db):
        practice = _create_practice(db, limit=1_000_000_00)
        _create_claim(db, practice.id, payer="Delta", amount=25000)
        _create_claim(db, practice.id, payer="Cigna", amount=25000)
        _create_claim(db, practice.id, payer="MetLife", amount=25000)
        _create_claim(db, practice.id, payer="Aetna", amount=25000)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        risks = OntologyBuilderV2.get_risks(db, practice.id)

        high_risks = [r for r in risks if r["severity"] == "high"]
        assert len(high_risks) == 0

    def test_risk_has_required_fields(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Monopoly", amount=90000)
        _create_claim(db, practice.id, payer="Other", amount=10000)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        risks = OntologyBuilderV2.get_risks(db, practice.id)

        for r in risks:
            assert "type" in r
            assert "severity" in r
            assert r["severity"] in ("low", "medium", "high")
            assert "metric" in r
            assert "value" in r
            assert "explanation" in r


class TestGraphExplorer:

    def test_graph_has_nodes_and_edges(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental", codes="D0120")

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        graph = OntologyBuilderV2.get_graph(db, practice.id)

        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) >= 3
        assert len(graph["edges"]) >= 1

    def test_graph_node_types(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental", codes="D0120")

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        graph = OntologyBuilderV2.get_graph(db, practice.id)

        node_types = {n["type"] for n in graph["nodes"]}
        assert "Practice" in node_types
        assert "Payer" in node_types

    def test_graph_node_has_properties(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental")

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        graph = OntologyBuilderV2.get_graph(db, practice.id)

        for node in graph["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "label" in node
            assert "properties" in node


class TestCohortMath:

    def test_cohorts_schema(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, amount=50000)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        cohorts = OntologyBuilderV2.get_cohorts(db, practice.id)

        assert "submission_cohorts" in cohorts
        assert "aging_buckets" in cohorts
        assert "lag_curve" in cohorts
        assert "timeseries" in cohorts

    def test_aging_buckets(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, amount=50000, status=ClaimStatus.APPROVED.value)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        cohorts = OntologyBuilderV2.get_cohorts(db, practice.id)
        aging = cohorts["aging_buckets"]

        assert "0_30" in aging
        assert "30_60" in aging
        assert "60_90" in aging
        assert "90_plus" in aging
        total = aging["0_30"] + aging["30_60"] + aging["60_90"] + aging["90_plus"]
        assert total >= 1

    def test_submission_cohorts(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, amount=50000)
        _create_claim(db, practice.id, amount=30000)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        cohorts = OntologyBuilderV2.get_cohorts(db, practice.id)

        assert len(cohorts["submission_cohorts"]) >= 1
        for sc in cohorts["submission_cohorts"]:
            assert "month" in sc
            assert "claims" in sc
            assert "billed_cents" in sc

    def test_timeseries_populated(self, db):
        practice = _create_practice(db)
        c = _create_claim(db, practice.id, amount=50000, status=ClaimStatus.PAID.value)
        _create_payment(db, c.id, practice.id, 50000)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        cohorts = OntologyBuilderV2.get_cohorts(db, practice.id)

        assert isinstance(cohorts["timeseries"], dict)


class TestIntegration:

    def test_seeded_practice_returns_valid_context(self, db):
        practice = db.query(Practice).first()
        if not practice:
            pytest.skip("No practice in database")

        context = OntologyBuilderV2.get_practice_context(db, practice.id)

        assert context["version"] == "ontology-v2"
        assert context["practice"]["id"] == practice.id
        assert context["snapshot"]["totals"]["total_claims"] >= 0
        assert isinstance(context["snapshot"]["payer_mix"], list)
        assert isinstance(context["snapshot"]["risk_flags"], list)
        assert isinstance(context["snapshot"]["missing_data"], list)
        assert "patient_dynamics" in context["snapshot"]


class TestMigrationState:

    def test_get_migration_state_returns_expected_keys(self):
        from app.database import engine
        from app.utils.migrations import get_migration_state
        state = get_migration_state(engine)
        assert "current_revision" in state
        assert "head_revision" in state
        assert "migration_pending" in state
        assert isinstance(state["migration_pending"], bool)

    def test_get_head_revision_returns_string(self):
        from app.utils.migrations import _get_head_revision
        head = _get_head_revision()
        assert isinstance(head, str)
        assert head != "unknown"

    def test_run_migrations_skips_when_disabled(self, capsys):
        from unittest.mock import MagicMock
        from app.utils.migrations import run_migrations_if_enabled
        mock_engine = MagicMock()
        run_migrations_if_enabled(mock_engine)
        mock_engine.raw_connection.assert_not_called()


class TestCORSConfig:

    def test_get_cors_origins_defaults(self):
        from app.config import Settings
        s = Settings(cors_allowed_origins=None)
        origins = s.get_cors_origins()
        assert "http://localhost:5173" in origins
        assert "http://localhost:5174" in origins
        assert "http://localhost:5175" in origins
        assert "http://localhost:3000" in origins

    def test_get_cors_origins_strips_whitespace(self):
        from app.config import Settings
        s = Settings(cors_allowed_origins=" https://portal.example.com , https://console.example.com ")
        origins = s.get_cors_origins()
        assert "https://portal.example.com" in origins
        assert "https://console.example.com" in origins

    def test_get_cors_origins_strips_trailing_slash(self):
        from app.config import Settings
        s = Settings(cors_allowed_origins="https://portal.example.com/")
        origins = s.get_cors_origins()
        assert "https://portal.example.com" in origins
        assert "https://portal.example.com/" not in origins

    def test_get_cors_origins_deduplicates(self):
        from app.config import Settings
        s = Settings(cors_allowed_origins="http://localhost:5173,http://localhost:5173")
        origins = s.get_cors_origins()
        assert origins.count("http://localhost:5173") == 1

    def test_diag_endpoint_returns_cors_config(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get("/diag")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert isinstance(data["cors_allow_origins"], list)
        assert data["cors_allow_methods"] == ["*"]
        assert data["cors_allow_headers"] == ["*"]
        assert data["cors_allow_credentials"] is False
        assert "current_revision" in data
        assert "head_revision" in data
        assert "migration_pending" in data
        assert isinstance(data["migration_pending"], bool)
        assert "run_migrations_on_startup_enabled" in data
        assert isinstance(data["run_migrations_on_startup_enabled"], bool)

    def test_options_preflight_returns_200(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.options(
            "/practices/1/ontology/context",
            headers={
                "Origin": "http://localhost:5174",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization,Content-Type",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5174"


class TestCDTFamilyMapping:

    def test_known_preventive_code(self):
        from app.services.cdt_families import get_cdt_family
        assert get_cdt_family("D0120") == "Preventive"
        assert get_cdt_family("D1110") == "Preventive"

    def test_known_restorative_code(self):
        from app.services.cdt_families import get_cdt_family
        assert get_cdt_family("D2140") == "Restorative"
        assert get_cdt_family("D2750") == "Restorative"

    def test_known_endodontics_code(self):
        from app.services.cdt_families import get_cdt_family
        assert get_cdt_family("D3310") == "Endodontics"

    def test_known_periodontics_code(self):
        from app.services.cdt_families import get_cdt_family
        assert get_cdt_family("D4341") == "Periodontics"

    def test_known_oral_surgery_code(self):
        from app.services.cdt_families import get_cdt_family
        assert get_cdt_family("D7140") == "Oral Surgery"

    def test_known_orthodontics_code(self):
        from app.services.cdt_families import get_cdt_family
        assert get_cdt_family("D8010") == "Orthodontics"

    def test_unknown_code_returns_other(self):
        from app.services.cdt_families import get_cdt_family
        assert get_cdt_family("D9999") == "Other"
        assert get_cdt_family("XXXXX") == "Other"

    def test_range_fallback(self):
        from app.services.cdt_families import get_cdt_family
        result = get_cdt_family("D0199")
        assert result in ("Preventive", "Other")

    def test_family_counts(self):
        from app.services.cdt_families import get_family_counts
        codes = ["D0120", "D0120", "D2140", "D7140", "UNKNOWN"]
        counts = get_family_counts(codes)
        assert counts["Preventive"] == 2
        assert counts["Restorative"] == 1
        assert counts["Oral Surgery"] == 1
        assert counts["Other"] == 1


class TestPatientRetention:

    def test_retention_schema(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental", amount=50000)
        _create_claim(db, practice.id, payer="Cigna", amount=30000)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        retention = OntologyBuilderV2.get_patient_retention(db, practice.id)

        assert "active_patients_12mo" in retention
        assert "new_patients" in retention
        assert "returning_patients" in retention
        assert "repeat_visit_rate_90d" in retention
        assert "repeat_visit_rate_180d" in retention
        assert "reactivation_rate" in retention

    def test_retention_counts_patients(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta", amount=50000)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        retention = OntologyBuilderV2.get_patient_retention(db, practice.id)

        assert retention["active_patients_12mo"] >= 1


class TestReimbursementMetrics:

    def test_reimbursement_schema(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta", amount=50000)
        _create_claim(db, practice.id, payer="Delta", amount=30000, status=ClaimStatus.DECLINED.value)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        reimb = OntologyBuilderV2.get_reimbursement_metrics(db, practice.id)

        assert "by_payer" in reimb
        assert "by_procedure_family" in reimb
        assert "time_to_adjudication" in reimb

    def test_reimbursement_by_payer(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta", amount=50000)
        _create_claim(db, practice.id, payer="Delta", amount=30000, status=ClaimStatus.DECLINED.value)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        reimb = OntologyBuilderV2.get_reimbursement_metrics(db, practice.id)

        assert "Delta" in reimb["by_payer"]
        delta = reimb["by_payer"]["Delta"]
        assert "denial_rate" in delta
        assert "billed_cents" in delta


class TestRcmOps:

    def test_rcm_schema(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, amount=50000)
        _create_claim(db, practice.id, amount=30000, status=ClaimStatus.DECLINED.value)
        _create_claim(db, practice.id, amount=20000, status=ClaimStatus.PAYMENT_EXCEPTION.value)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        rcm = OntologyBuilderV2.get_rcm_ops(db, practice.id)

        assert "claims_aging_buckets" in rcm
        assert "exception_rate" in rcm
        assert "exception_count" in rcm
        assert "declined_count" in rcm
        assert "total_claims" in rcm

    def test_rcm_counts(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, amount=50000)
        _create_claim(db, practice.id, amount=30000, status=ClaimStatus.PAYMENT_EXCEPTION.value)

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        rcm = OntologyBuilderV2.get_rcm_ops(db, practice.id)

        assert rcm["total_claims"] == 2
        assert rcm["exception_count"] == 1


class TestGraphVNext:

    def test_graph_with_mode(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta", amount=50000, codes="D0120,D2140")

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        graph = OntologyBuilderV2.get_graph(db, practice.id, mode="revenue_cycle")

        assert "version" in graph
        assert "mode" in graph
        assert graph["mode"] == "revenue_cycle"
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) > 0

    def test_graph_nodes_have_labels(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta", codes="D0120")

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        graph = OntologyBuilderV2.get_graph(db, practice.id)

        for node in graph["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "label" in node
            assert "properties" in node

    def test_graph_edges_have_type_labels(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta", codes="D0120")

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        graph = OntologyBuilderV2.get_graph(db, practice.id)

        for edge in graph["edges"]:
            assert "from" in edge
            assert "to" in edge
            assert "type" in edge
            assert "type_label" in edge

    def test_graph_patient_retention_mode(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta", codes="D0120")

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        graph = OntologyBuilderV2.get_graph(db, practice.id, mode="patient_retention")

        assert graph["mode"] == "patient_retention"
        node_types = {n["type"] for n in graph["nodes"]}
        assert "Patient" in node_types or len(graph["nodes"]) == 0

    def test_graph_density_control(self, db):
        practice = _create_practice(db)
        for i in range(10):
            _create_claim(db, practice.id, payer=f"Payer{i}", amount=10000, codes="D0120,D2140,D3310")

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        graph = OntologyBuilderV2.get_graph(db, practice.id, limit=50)

        assert len(graph["nodes"]) <= 60

    def test_graph_payer_filter(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta", amount=50000, codes="D0120")
        _create_claim(db, practice.id, payer="Cigna", amount=30000, codes="D2140")

        OntologyBuilderV2.build_practice_ontology(db, practice.id)
        graph = OntologyBuilderV2.get_graph(db, practice.id, payer_filter="Delta")

        payer_nodes = [n for n in graph["nodes"] if n["type"] == "Payer"]
        if payer_nodes:
            payer_names = [n["label"] for n in payer_nodes]
            assert "Delta" in payer_names
