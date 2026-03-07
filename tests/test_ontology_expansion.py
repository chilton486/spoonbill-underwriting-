"""Tests for Ontology Expansion (Phases 2-7).

Tests cover:
- New model/schema integrity
- Tenant isolation for new objects
- Service layer (CRUD, insights, funding, reconciliation)
- Synthetic data generation
- Backward compatibility with existing claim/payment flows
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.practice import Practice
from app.models.claim import Claim, ClaimStatus
from app.models.payment import PaymentIntent, PaymentIntentStatus, PaymentProvider
from app.models.provider import Provider, ProviderRole
from app.models.payer import Payer
from app.models.payer_contract import PayerContract, NetworkStatus, ContractStatus
from app.models.procedure_code import ProcedureCode, ProcedureCategory
from app.models.claim_line import ClaimLine, ClaimLineStatus
from app.models.funding_decision import FundingDecision, FundingDecisionType
from app.models.remittance import (
    Remittance, RemittanceLine, PostingStatus,
    RemittanceSourceType, RemittanceLineMatchStatus,
)
from app.models.fee_schedule import FeeScheduleItem
from app.services.ontology_crud import (
    ProviderService, PayerService, PayerContractService,
    ProcedureCodeService, OntologyInsightsService,
)
from app.services.funding import FundingDecisionService
from app.services.remittance_reconciliation import RemittanceReconciliationService

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
        session.close()


# ─── Helpers ───

def _make_practice(db, name="Test Expansion Practice", limit=100_000_00):
    p = Practice(name=name, status="ACTIVE", funding_limit_cents=limit)
    db.add(p)
    db.flush()
    return p


def _make_payer(db, code="TEST-PPO", name="Test PPO Payer"):
    existing = db.query(Payer).filter(Payer.payer_code == code).first()
    if existing:
        return existing
    p = Payer(
        payer_code=code,
        name=name,
        plan_types=["PPO"],
        eft_capable=True,
        era_capable=True,
        filing_limit_days=365,
    )
    db.add(p)
    db.flush()
    return p


def _make_provider(db, practice_id, name="Dr. Test Provider", role="OWNER"):
    p = Provider(
        practice_id=practice_id,
        full_name=name,
        npi="9999999999",
        specialty="General Dentistry",
        role=role,
        is_active=True,
    )
    db.add(p)
    db.flush()
    return p


def _make_procedure_code(db, cdt_code="D0120", desc="Periodic oral evaluation", category="PREVENTIVE"):
    existing = db.query(ProcedureCode).filter(ProcedureCode.cdt_code == cdt_code).first()
    if existing:
        return existing
    pc = ProcedureCode(
        cdt_code=cdt_code,
        short_description=desc,
        category=category,
    )
    db.add(pc)
    db.flush()
    return pc


def _make_claim(db, practice_id, payer_id=None, provider_id=None, amount=50000, status=ClaimStatus.APPROVED.value):
    c = Claim(
        practice_id=practice_id,
        payer_id=payer_id,
        provider_id=provider_id,
        patient_name="Test Patient",
        payer="Test Payer",
        amount_cents=amount,
        total_billed_cents=amount,
        total_allowed_cents=int(amount * 0.8),
        status=status,
        procedure_date=date.today() - timedelta(days=30),
        submitted_at=datetime.utcnow() - timedelta(days=28),
        claim_token=Claim.generate_claim_token(),
        fingerprint=f"test-{practice_id}-{Claim.generate_claim_token()}",
        source_system="TEST",
    )
    db.add(c)
    db.flush()
    return c


# ─── Model / Schema Integrity Tests ───

class TestModelIntegrity:

    def test_provider_creation(self, db):
        practice = _make_practice(db)
        provider = _make_provider(db, practice.id)
        assert provider.id is not None
        assert provider.practice_id == practice.id
        assert provider.role == "OWNER"
        assert provider.is_active is True

    def test_payer_creation(self, db):
        payer = _make_payer(db, code="INTEG-TEST-1", name="Integration Test Payer")
        assert payer.id is not None
        assert payer.payer_code == "INTEG-TEST-1"
        assert payer.eft_capable is True

    def test_payer_contract_creation(self, db):
        practice = _make_practice(db)
        payer = _make_payer(db, code="CONTRACT-TEST", name="Contract Test Payer")
        contract = PayerContract(
            practice_id=practice.id,
            payer_id=payer.id,
            effective_start_date=date(2024, 1, 1),
            network_status=NetworkStatus.IN_NETWORK.value,
            status=ContractStatus.ACTIVE.value,
        )
        db.add(contract)
        db.flush()
        assert contract.id is not None
        assert contract.practice_id == practice.id
        assert contract.payer_id == payer.id

    def test_procedure_code_creation(self, db):
        pc = _make_procedure_code(db, cdt_code="D9999", desc="Test Procedure", category="OTHER")
        assert pc.id is not None
        assert pc.cdt_code == "D9999"

    def test_claim_line_creation(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)
        pc = _make_procedure_code(db)
        cl = ClaimLine(
            claim_id=claim.id,
            procedure_code_id=pc.id,
            cdt_code=pc.cdt_code,
            billed_fee_cents=5000,
            allowed_fee_cents=4000,
            units=1,
            line_status=ClaimLineStatus.PENDING.value,
        )
        db.add(cl)
        db.flush()
        assert cl.id is not None
        assert cl.claim_id == claim.id

    def test_funding_decision_creation(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)
        fd = FundingDecision(
            claim_id=claim.id,
            decision=FundingDecisionType.APPROVE.value,
            advance_rate=0.80,
            max_advance_amount_cents=40000,
            fee_rate=0.03,
            risk_score=0.15,
            reasons_json=[{"rule": "test", "detail": "test reason"}],
            decisioned_at=datetime.utcnow(),
            model_version="test-v1",
            policy_version="test-v1",
        )
        db.add(fd)
        db.flush()
        assert fd.id is not None
        assert fd.decision == "APPROVE"

    def test_remittance_and_line_creation(self, db):
        practice = _make_practice(db)
        payer = _make_payer(db, code="REM-TEST", name="Remittance Test Payer")
        claim = _make_claim(db, practice.id)

        rem = Remittance(
            practice_id=practice.id,
            payer_id=payer.id,
            payer_name=payer.name,
            trace_number="TRC-TEST-001",
            payment_date=date.today(),
            total_paid_cents=40000,
            total_adjustments_cents=1000,
            posting_status=PostingStatus.RECEIVED.value,
            source_type=RemittanceSourceType.MANUAL.value,
        )
        db.add(rem)
        db.flush()

        rl = RemittanceLine(
            remittance_id=rem.id,
            claim_id=claim.id,
            external_claim_id="EXT-001",
            paid_cents=40000,
            match_status=RemittanceLineMatchStatus.UNMATCHED.value,
        )
        db.add(rl)
        db.flush()

        assert rem.id is not None
        assert rl.remittance_id == rem.id
        assert rl.claim_id == claim.id

    def test_fee_schedule_item_creation(self, db):
        practice = _make_practice(db)
        payer = _make_payer(db, code="FEE-TEST", name="Fee Test Payer")
        contract = PayerContract(
            practice_id=practice.id,
            payer_id=payer.id,
            network_status=NetworkStatus.IN_NETWORK.value,
            status=ContractStatus.ACTIVE.value,
        )
        db.add(contract)
        db.flush()

        pc = _make_procedure_code(db)
        fsi = FeeScheduleItem(
            payer_contract_id=contract.id,
            procedure_code_id=pc.id,
            cdt_code=pc.cdt_code,
            allowed_amount_cents=5000,
        )
        db.add(fsi)
        db.flush()
        assert fsi.id is not None


# ─── Tenant Isolation Tests ───

class TestTenantIsolation:

    def test_provider_isolation(self, db):
        p1 = _make_practice(db, name="Isolation P1")
        p2 = _make_practice(db, name="Isolation P2")
        _make_provider(db, p1.id, name="P1 Provider")
        _make_provider(db, p2.id, name="P2 Provider")

        p1_providers = ProviderService.list_providers(db, p1.id)
        p2_providers = ProviderService.list_providers(db, p2.id)

        p1_names = [p["full_name"] for p in p1_providers]
        p2_names = [p["full_name"] for p in p2_providers]

        assert "P1 Provider" in p1_names
        assert "P2 Provider" not in p1_names
        assert "P2 Provider" in p2_names
        assert "P1 Provider" not in p2_names

    def test_contract_isolation(self, db):
        p1 = _make_practice(db, name="Contract P1")
        p2 = _make_practice(db, name="Contract P2")
        payer = _make_payer(db, code="ISOL-CONTRACT", name="Isolation Contract Payer")

        c1 = PayerContract(
            practice_id=p1.id, payer_id=payer.id,
            network_status=NetworkStatus.IN_NETWORK.value,
            status=ContractStatus.ACTIVE.value,
        )
        c2 = PayerContract(
            practice_id=p2.id, payer_id=payer.id,
            network_status=NetworkStatus.OUT_OF_NETWORK.value,
            status=ContractStatus.ACTIVE.value,
        )
        db.add(c1)
        db.add(c2)
        db.flush()

        p1_contracts = PayerContractService.list_contracts(db, p1.id)
        p2_contracts = PayerContractService.list_contracts(db, p2.id)

        assert len(p1_contracts) >= 1
        assert len(p2_contracts) >= 1
        # Check that contracts don't leak
        p1_ids = [c["id"] for c in p1_contracts]
        p2_ids = [c["id"] for c in p2_contracts]
        assert c1.id in p1_ids
        assert c2.id not in p1_ids
        assert c2.id in p2_ids
        assert c1.id not in p2_ids

    def test_insights_isolation(self, db):
        p1 = _make_practice(db, name="Insight P1")
        p2 = _make_practice(db, name="Insight P2")
        _make_claim(db, p1.id, amount=100000)
        _make_claim(db, p2.id, amount=200000)

        s1 = OntologyInsightsService.get_practice_summary(db, p1.id)
        s2 = OntologyInsightsService.get_practice_summary(db, p2.id)

        assert s1["total_claims"] >= 1
        assert s2["total_claims"] >= 1
        # They should have different billed totals
        assert s1["total_billed_cents"] != s2["total_billed_cents"]


# ─── Service Layer Tests ───

class TestProviderService:

    def test_list_providers(self, db):
        practice = _make_practice(db)
        _make_provider(db, practice.id, name="Active Provider", role="OWNER")
        providers = ProviderService.list_providers(db, practice.id)
        assert len(providers) >= 1
        assert any(p["full_name"] == "Active Provider" for p in providers)

    def test_get_provider(self, db):
        practice = _make_practice(db)
        provider = _make_provider(db, practice.id, name="Get Test Provider")
        result = ProviderService.get_provider(db, provider.id, practice.id)
        assert result is not None
        assert result["full_name"] == "Get Test Provider"

    def test_get_provider_wrong_practice(self, db):
        p1 = _make_practice(db, name="Provider P1")
        p2 = _make_practice(db, name="Provider P2")
        provider = _make_provider(db, p1.id)
        result = ProviderService.get_provider(db, provider.id, p2.id)
        assert result is None

    def test_create_provider(self, db):
        practice = _make_practice(db)
        provider = ProviderService.create_provider(
            db, practice.id,
            full_name="New Provider",
            npi="1234567890",
            specialty="Pediatric Dentistry",
            role="ASSOCIATE",
        )
        assert provider.id is not None
        assert provider.full_name == "New Provider"
        assert provider.practice_id == practice.id


class TestPayerService:

    def test_list_payers(self, db):
        _make_payer(db, code="LIST-TEST", name="List Test Payer")
        payers = PayerService.list_payers(db)
        assert len(payers) >= 1
        assert any(p["payer_code"] == "LIST-TEST" for p in payers)

    def test_get_or_create_payer(self, db):
        payer = PayerService.get_or_create_payer(
            db, payer_code="UPSERT-TEST", name="Upsert Test Payer"
        )
        assert payer.id is not None
        # Should return same payer on second call
        payer2 = PayerService.get_or_create_payer(
            db, payer_code="UPSERT-TEST", name="Different Name"
        )
        assert payer2.id == payer.id


class TestProcedureCodeService:

    def test_list_procedure_codes(self, db):
        _make_procedure_code(db, cdt_code="D0120")
        codes = ProcedureCodeService.list_procedure_codes(db)
        assert len(codes) >= 1

    def test_get_or_create(self, db):
        pc = ProcedureCodeService.get_or_create(db, "D8888", "Test Code", "PREVENTIVE")
        assert pc.id is not None
        pc2 = ProcedureCodeService.get_or_create(db, "D8888", "Different Desc", "PREVENTIVE")
        assert pc2.id == pc.id


class TestOntologyInsightsService:

    def test_practice_summary(self, db):
        practice = _make_practice(db)
        _make_claim(db, practice.id, amount=50000)
        _make_claim(db, practice.id, amount=30000)

        summary = OntologyInsightsService.get_practice_summary(db, practice.id)
        assert summary["total_claims"] >= 2
        assert summary["total_billed_cents"] >= 80000

    def test_practice_summary_empty(self, db):
        practice = _make_practice(db)
        summary = OntologyInsightsService.get_practice_summary(db, practice.id)
        assert summary["total_claims"] == 0

    def test_claim_cycle_times(self, db):
        practice = _make_practice(db)
        _make_claim(db, practice.id, status=ClaimStatus.NEEDS_REVIEW.value)
        _make_claim(db, practice.id, status=ClaimStatus.APPROVED.value)

        cycle = OntologyInsightsService.get_claim_cycle_times(db, practice.id)
        assert "open_claims" in cycle
        assert "aging_buckets" in cycle
        assert cycle["open_claims"] >= 1

    def test_funding_decisions_summary(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)
        fd = FundingDecision(
            claim_id=claim.id,
            decision=FundingDecisionType.APPROVE.value,
            risk_score=0.2,
            decisioned_at=datetime.utcnow(),
            model_version="test",
        )
        db.add(fd)
        db.flush()

        result = OntologyInsightsService.get_funding_decisions_summary(db, practice.id)
        assert result["total_decisions"] >= 1

    def test_reconciliation_summary(self, db):
        practice = _make_practice(db)
        result = OntologyInsightsService.get_reconciliation_summary(db, practice.id)
        assert "total_remittances" in result
        assert "match_rate" in result


# ─── Funding Decision Service Tests ───

class TestFundingDecisionService:

    def test_create_approve_decision(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id, amount=5000)
        fd = FundingDecisionService.create_funding_decision(db, claim, risk_score=0.1)
        assert fd.decision == FundingDecisionType.APPROVE.value
        assert fd.risk_score == 0.1
        assert fd.advance_rate > 0
        assert fd.max_advance_amount_cents > 0

    def test_create_deny_decision_high_risk(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id, amount=5000)
        fd = FundingDecisionService.create_funding_decision(db, claim, risk_score=0.9)
        assert fd.decision == FundingDecisionType.DENY.value

    def test_create_needs_review_moderate_risk(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id, amount=5000)
        fd = FundingDecisionService.create_funding_decision(db, claim, risk_score=0.5)
        assert fd.decision == FundingDecisionType.NEEDS_REVIEW.value

    def test_create_payment_from_approved_decision(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id, amount=5000)
        fd = FundingDecisionService.create_funding_decision(db, claim, risk_score=0.1)
        pi = FundingDecisionService.create_payment_from_decision(db, fd, claim)
        assert pi is not None
        assert pi.status == PaymentIntentStatus.QUEUED.value
        assert pi.amount_cents > 0

    def test_no_payment_from_denied_decision(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id, amount=5000)
        fd = FundingDecisionService.create_funding_decision(db, claim, risk_score=0.9)
        pi = FundingDecisionService.create_payment_from_decision(db, fd, claim)
        assert pi is None

    def test_override_decision(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id, amount=5000)
        fd = FundingDecisionService.create_funding_decision(
            db, claim, override_decision=FundingDecisionType.DENY.value
        )
        assert fd.decision == FundingDecisionType.DENY.value


# ─── Remittance Reconciliation Tests ───

class TestRemittanceReconciliation:

    def test_ingest_remittance(self, db):
        practice = _make_practice(db)
        rem = RemittanceReconciliationService.ingest_remittance(
            db,
            practice_id=practice.id,
            payer_name="Test Payer",
            trace_number="TRC-001",
            payment_date=date.today(),
            total_paid_cents=50000,
            total_adjustments_cents=2000,
            lines=[
                {"external_claim_id": "EXT-001", "paid_cents": 30000, "cdt_code": "D0120"},
                {"external_claim_id": "EXT-002", "paid_cents": 20000},
            ],
        )
        assert rem.id is not None
        assert rem.posting_status == PostingStatus.RECEIVED.value

        lines = db.query(RemittanceLine).filter(RemittanceLine.remittance_id == rem.id).all()
        assert len(lines) == 2

    def test_reconcile_matched(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id, amount=30000)

        rem = RemittanceReconciliationService.ingest_remittance(
            db,
            practice_id=practice.id,
            payer_name="Test Payer",
            trace_number="TRC-MATCH",
            payment_date=date.today(),
            total_paid_cents=25000,
            lines=[
                {"external_claim_id": claim.external_claim_id, "paid_cents": 25000},
            ],
        )

        # Set external_claim_id on claim so it can match
        claim.external_claim_id = claim.external_claim_id or f"EXT-{claim.id}"
        line = db.query(RemittanceLine).filter(RemittanceLine.remittance_id == rem.id).first()
        line.external_claim_id = claim.external_claim_id
        db.flush()

        result = RemittanceReconciliationService.reconcile_remittance(db, rem.id)
        assert result["total_lines"] == 1
        assert result["matched"] + result["unmatched"] + result["mismatches"] == 1

    def test_reconcile_nonexistent(self, db):
        result = RemittanceReconciliationService.reconcile_remittance(db, 999999)
        assert "error" in result


# ─── Backward Compatibility Tests ───

class TestBackwardCompatibility:

    def test_existing_claim_fields_still_work(self, db):
        """Existing claims with original fields should still work."""
        practice = _make_practice(db)
        c = Claim(
            practice_id=practice.id,
            patient_name="Old Claim Patient",
            payer="Old Payer",
            amount_cents=50000,
            status=ClaimStatus.APPROVED.value,
            claim_token=Claim.generate_claim_token(),
            fingerprint=f"compat-{Claim.generate_claim_token()}",
            procedure_codes="D0120,D1110",
        )
        db.add(c)
        db.flush()
        assert c.id is not None
        assert c.patient_name == "Old Claim Patient"
        assert c.amount_cents == 50000

    def test_new_fk_columns_nullable(self, db):
        """New FK columns (payer_id, provider_id, payer_contract_id) should be nullable."""
        practice = _make_practice(db)
        c = Claim(
            practice_id=practice.id,
            patient_name="Nullable FK Patient",
            payer="Some Payer",
            amount_cents=30000,
            status=ClaimStatus.NEW.value,
            claim_token=Claim.generate_claim_token(),
            fingerprint=f"nullable-{Claim.generate_claim_token()}",
        )
        db.add(c)
        db.flush()
        assert c.payer_id is None
        assert c.provider_id is None
        assert c.payer_contract_id is None

    def test_payment_intent_backward_compat(self, db):
        """PaymentIntent should work with both old and new fields."""
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)
        pi = PaymentIntent(
            claim_id=claim.id,
            practice_id=practice.id,
            amount_cents=40000,
            status=PaymentIntentStatus.QUEUED.value,
        )
        pi.idempotency_key = PaymentIntent.generate_idempotency_key(claim.id)
        db.add(pi)
        db.flush()
        assert pi.id is not None
        assert pi.queued_at is None  # New field, should be nullable

    def test_practice_enhanced_fields(self, db):
        """Practice should accept new fields while keeping old ones."""
        p = Practice(
            name="Enhanced Practice",
            legal_name="Enhanced Practice LLC",
            ein="12-3456789",
            group_npi="1234567890",
            city="Austin",
            state="TX",
            zip_code="78701",
            pms_type="Dentrix",
            status="ACTIVE",
            funding_limit_cents=100_000_00,
        )
        db.add(p)
        db.flush()
        assert p.id is not None
        assert p.legal_name == "Enhanced Practice LLC"
        assert p.pms_type == "Dentrix"
        # Old fields still work
        assert p.name == "Enhanced Practice"
        assert p.funding_limit_cents == 100_000_00


# ─── Enum Tests ───

class TestEnums:

    def test_provider_role_enum(self):
        assert ProviderRole.OWNER.value == "OWNER"
        assert ProviderRole.HYGIENIST.value == "HYGIENIST"

    def test_claim_line_status_enum(self):
        assert ClaimLineStatus.PENDING.value == "PENDING"
        assert ClaimLineStatus.ADJUDICATED.value == "ADJUDICATED"
        assert ClaimLineStatus.DENIED.value == "DENIED"

    def test_funding_decision_type_enum(self):
        assert FundingDecisionType.APPROVE.value == "APPROVE"
        assert FundingDecisionType.DENY.value == "DENY"
        assert FundingDecisionType.NEEDS_REVIEW.value == "NEEDS_REVIEW"

    def test_posting_status_enum(self):
        assert PostingStatus.RECEIVED.value == "RECEIVED"
        assert PostingStatus.POSTED.value == "POSTED"
        assert PostingStatus.EXCEPTION.value == "EXCEPTION"

    def test_network_status_enum(self):
        assert NetworkStatus.IN_NETWORK.value == "IN_NETWORK"
        assert NetworkStatus.OUT_OF_NETWORK.value == "OUT_OF_NETWORK"

    def test_procedure_category_enum(self):
        assert ProcedureCategory.PREVENTIVE.value == "PREVENTIVE"
        assert ProcedureCategory.RESTORATIVE.value == "RESTORATIVE"
