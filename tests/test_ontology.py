"""Tests for Dental Financial Ontology (Phases 1-8)."""
import json
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.practice import Practice
from app.models.claim import Claim, ClaimStatus
from app.models.payment import PaymentIntent, PaymentIntentStatus, PaymentProvider
from app.models.user import User, UserRole
from app.models.ontology import OntologyObject, OntologyObjectType, OntologyLink, OntologyLinkType, KPIObservation
from app.services.ontology import OntologyBuilder
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
        yield session
    finally:
        session.rollback()
        for tbl in (KPIObservation, OntologyLink, OntologyObject):
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

        context = OntologyBuilder.get_practice_context(db, practice.id)

        assert context["version"] == "ontology-v1"
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

        context = OntologyBuilder.get_practice_context(db, practice.id)
        totals = context["snapshot"]["totals"]

        assert totals["total_claims"] == 3
        assert totals["total_billed_cents"] == 100000

    def test_context_payer_mix(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental", amount=70000)
        _create_claim(db, practice.id, payer="Cigna", amount=30000)

        context = OntologyBuilder.get_practice_context(db, practice.id)
        payer_mix = context["snapshot"]["payer_mix"]

        assert len(payer_mix) == 2
        assert payer_mix[0]["payer"] == "Delta Dental"
        assert payer_mix[0]["share"] == 0.7

    def test_context_denial_rate(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, amount=50000, status=ClaimStatus.APPROVED.value)
        _create_claim(db, practice.id, amount=50000, status=ClaimStatus.DECLINED.value)

        context = OntologyBuilder.get_practice_context(db, practice.id)
        denials = context["snapshot"]["denials"]

        assert denials["denial_rate"] == 0.5
        assert denials["declined_count"] == 1

    def test_context_utilization(self, db):
        practice = _create_practice(db, limit=100_000)
        c = _create_claim(db, practice.id, amount=50000, status=ClaimStatus.PAID.value)
        _create_payment(db, c.id, practice.id, 50000)

        context = OntologyBuilder.get_practice_context(db, practice.id)
        funding = context["snapshot"]["funding"]

        assert funding["utilization"] == 0.5

    def test_risk_flag_payer_concentration(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Monopoly Dental", amount=90000)
        _create_claim(db, practice.id, payer="Other", amount=10000)

        context = OntologyBuilder.get_practice_context(db, practice.id)
        flags = context["snapshot"]["risk_flags"]

        flag_names = [f["flag"] for f in flags]
        assert "PAYER_CONCENTRATION" in flag_names

    def test_risk_flag_high_denial(self, db):
        practice = _create_practice(db)
        for _ in range(8):
            _create_claim(db, practice.id, status=ClaimStatus.APPROVED.value)
        for _ in range(3):
            _create_claim(db, practice.id, status=ClaimStatus.DECLINED.value)

        context = OntologyBuilder.get_practice_context(db, practice.id)
        flags = context["snapshot"]["risk_flags"]

        flag_names = [f["flag"] for f in flags]
        assert "HIGH_DENIAL_RATE" in flag_names

    def test_missing_data_reported(self, db):
        practice = _create_practice(db, limit=None)
        _create_claim(db, practice.id)

        context = OntologyBuilder.get_practice_context(db, practice.id)
        missing = context["snapshot"]["missing_data"]

        assert any("funded_utilization" in m for m in missing)

    def test_practice_isolation(self, db):
        p1 = _create_practice(db, name="Practice A")
        p2 = _create_practice(db, name="Practice B")
        _create_claim(db, p1.id, payer="P1 Payer", amount=50000)
        _create_claim(db, p2.id, payer="P2 Payer", amount=30000)

        ctx1 = OntologyBuilder.get_practice_context(db, p1.id)
        ctx2 = OntologyBuilder.get_practice_context(db, p2.id)

        assert ctx1["snapshot"]["totals"]["total_claims"] == 1
        assert ctx2["snapshot"]["totals"]["total_claims"] == 1
        assert ctx1["snapshot"]["payer_mix"][0]["payer"] == "P1 Payer"
        assert ctx2["snapshot"]["payer_mix"][0]["payer"] == "P2 Payer"


class TestOntologyBuilder:

    def test_build_creates_objects(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Delta Dental", codes="D0120")

        result = OntologyBuilder.build_practice_ontology(db, practice.id)

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

        OntologyBuilder.build_practice_ontology(db, practice.id)
        count1 = db.query(OntologyObject).filter(OntologyObject.practice_id == practice.id).count()

        OntologyBuilder.build_practice_ontology(db, practice.id)
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


class TestIntegration:

    def test_seeded_practice_returns_valid_context(self, db):
        practice = db.query(Practice).first()
        if not practice:
            pytest.skip("No practice in database")

        context = OntologyBuilder.get_practice_context(db, practice.id)

        assert context["version"] == "ontology-v1"
        assert context["practice"]["id"] == practice.id
        assert context["snapshot"]["totals"]["total_claims"] >= 0
        assert isinstance(context["snapshot"]["payer_mix"], list)
        assert isinstance(context["snapshot"]["risk_flags"], list)
        assert isinstance(context["snapshot"]["missing_data"], list)
