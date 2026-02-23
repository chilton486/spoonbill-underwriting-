"""Regression tests for Control Tower vNext: control tower payload, reconciliation, simulation."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.practice import Practice
from app.models.claim import Claim, ClaimStatus
from app.models.payment import PaymentIntent, PaymentIntentStatus, PaymentProvider
from app.models.ledger import (
    LedgerAccount, LedgerAccountType, LedgerEntry,
    LedgerEntryDirection, LedgerEntryStatus,
)
from app.services.control_tower import ControlTowerService
from app.services.reconciliation import ReconciliationService
from app.services.action_proposals import ActionProposalService

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
        session.close()


def _create_practice(db, name="CT Test Practice", limit=500_000_00):
    p = Practice(name=name, status="ACTIVE", funding_limit_cents=limit)
    db.add(p)
    db.flush()
    return p


def _create_claim(db, practice_id, payer="Delta Dental", amount=50000, status=ClaimStatus.APPROVED.value):
    c = Claim(
        practice_id=practice_id,
        patient_name="Test Patient",
        payer=payer,
        amount_cents=amount,
        status=status,
        claim_token=Claim.generate_claim_token(),
        fingerprint=f"ct-test-{practice_id}-{Claim.generate_claim_token()}",
        procedure_codes="D0120",
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
        idempotency_key=f"ct-test-{claim_id}-{Claim.generate_claim_token()}",
        provider=PaymentProvider.SIMULATED.value,
        sent_at=datetime.utcnow() - timedelta(hours=24),
        confirmed_at=datetime.utcnow() if status == PaymentIntentStatus.CONFIRMED.value else None,
    )
    db.add(pi)
    db.flush()
    return pi


class TestControlTowerPayload:

    def test_control_tower_returns_expected_top_level_keys(self, db):
        result = ControlTowerService.get_control_tower(db)
        expected_keys = [
            "liquidity_by_facility",
            "commitments",
            "freshness",
            "top_concentrations",
            "alerts",
            "can_fund_now",
            "computed_at",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_liquidity_by_facility_structure(self, db):
        result = ControlTowerService.get_control_tower(db)
        facilities = result["liquidity_by_facility"]
        assert isinstance(facilities, list)
        for f in facilities:
            assert "facility" in f
            assert "cash_cents" in f
            assert "reserved_cents" in f
            assert "inflight_cents" in f
            assert "settled_cents" in f
            assert "as_of" in f

    def test_commitments_structure(self, db):
        result = ControlTowerService.get_control_tower(db)
        commitments = result["commitments"]
        assert "approved_not_sent_cents" in commitments
        assert "sent_not_confirmed_cents" in commitments
        assert "exception_amount_cents" in commitments

    def test_freshness_structure(self, db):
        result = ControlTowerService.get_control_tower(db)
        freshness = result["freshness"]
        assert "updated_at" in freshness
        assert "staleness_seconds" in freshness

    def test_can_fund_now_structure(self, db):
        result = ControlTowerService.get_control_tower(db)
        cfn = result["can_fund_now"]
        assert "value" in cfn
        assert "available_cents" in cfn
        assert isinstance(cfn["value"], bool)

    def test_alerts_are_list(self, db):
        result = ControlTowerService.get_control_tower(db)
        assert isinstance(result["alerts"], list)

    def test_top_concentrations_structure(self, db):
        result = ControlTowerService.get_control_tower(db)
        conc = result["top_concentrations"]
        assert "practices" in conc
        assert "payers" in conc
        assert isinstance(conc["practices"], list)
        assert isinstance(conc["payers"], list)


class TestReconciliationSummary:

    def test_summary_returns_expected_keys(self, db):
        result = ReconciliationService.get_summary(db)
        assert "ledger_totals" in result
        assert "external_balances" in result
        assert "unmatched_confirmations" in result

    def test_ledger_totals_structure(self, db):
        result = ReconciliationService.get_summary(db)
        lt = result["ledger_totals"]
        assert "queued_cents" in lt
        assert "sent_cents" in lt
        assert "confirmed_cents" in lt

    def test_external_balances_is_list(self, db):
        result = ReconciliationService.get_summary(db)
        assert isinstance(result["external_balances"], list)

    def test_unmatched_confirmations_is_int(self, db):
        result = ReconciliationService.get_summary(db)
        assert isinstance(result["unmatched_confirmations"], int)


class TestReconciliationPaymentIntents:

    def test_payment_intent_reconciliation_structure(self, db):
        result = ReconciliationService.get_payment_intent_reconciliation(db)
        assert "items" in result
        assert "total" in result
        assert isinstance(result["items"], list)

    def test_payment_intent_item_structure(self, db):
        practice = _create_practice(db)
        c = _create_claim(db, practice.id, amount=50000, status=ClaimStatus.PAID.value)
        _create_payment(db, c.id, practice.id, 50000)
        db.commit()

        result = ReconciliationService.get_payment_intent_reconciliation(db)
        if result["items"]:
            item = result["items"][0]
            assert "id" in item
            assert "amount_cents" in item
            assert "ledger_status" in item
            assert "matched" in item
            assert "mismatch" in item


class TestReconciliationIngest:

    def test_ingest_balance_creates_snapshot(self, db):
        result = ReconciliationService.ingest_balance(
            db, facility="Test Facility", balance_cents=100000,
            as_of="2026-01-15T12:00:00", source="test",
        )
        assert "id" in result
        assert result["facility"] == "Test Facility"
        assert result["balance_cents"] == 100000

    def test_ingest_payment_confirmation_creates_record(self, db):
        practice = _create_practice(db)
        c = _create_claim(db, practice.id, amount=25000, status=ClaimStatus.PAID.value)
        pi = _create_payment(db, c.id, practice.id, 25000)
        db.commit()

        result = ReconciliationService.ingest_payment_confirmation(
            db, payment_intent_id=str(pi.id),
            rail_ref="RAIL-123", status="CONFIRMED",
            confirmed_at="2026-01-15T12:00:00",
            raw_json=None,
        )
        assert "id" in result
        assert result["payment_intent_id"] == str(pi.id)
        assert result["status"] == "CONFIRMED"


class TestProposalSimulation:

    def test_simulation_returns_expected_keys(self, db):
        practice = _create_practice(db, limit=200_000)
        db.commit()

        proposal = {
            "action": "ADJUST_LIMIT",
            "practice_id": practice.id,
            "practice_name": practice.name,
            "params": {
                "current_limit_cents": 200_000,
                "proposed_limit_cents": 300_000,
            },
            "reason": "Test simulation",
            "supporting_metrics": {},
            "severity": "medium",
        }

        result = ActionProposalService.simulate_proposal(db, proposal)
        assert "proposal" in result
        assert "validation" in result
        assert "expected_impact" in result
        assert "risk_assessment" in result
        assert "policy_checks_passed" in result
        assert "current_state" in result
        assert "required_approvals" in result
        assert "simulated_at" in result

    def test_simulation_impact_structure(self, db):
        practice = _create_practice(db, limit=200_000)
        db.commit()

        proposal = {
            "action": "ADJUST_LIMIT",
            "practice_id": practice.id,
            "practice_name": practice.name,
            "params": {
                "current_limit_cents": 200_000,
                "proposed_limit_cents": 300_000,
            },
            "reason": "Test simulation",
            "supporting_metrics": {},
            "severity": "medium",
        }

        result = ActionProposalService.simulate_proposal(db, proposal)
        impact = result["expected_impact"]
        assert "liquidity_delta_cents" in impact
        assert "exposure_delta_cents" in impact
        assert "dso_proxy_change" in impact

    def test_simulation_policy_checks_structure(self, db):
        practice = _create_practice(db, limit=200_000)
        db.commit()

        proposal = {
            "action": "REVIEW_EXCEPTIONS",
            "practice_id": practice.id,
            "practice_name": practice.name,
            "params": {},
            "reason": "Test policy checks",
            "supporting_metrics": {},
            "severity": "low",
        }

        result = ActionProposalService.simulate_proposal(db, proposal)
        checks = result["policy_checks_passed"]
        assert isinstance(checks, list)
        for c in checks:
            assert "name" in c
            assert "passed" in c
            assert "detail" in c

    def test_simulation_risk_assessment_valid_values(self, db):
        practice = _create_practice(db, limit=200_000)
        db.commit()

        proposal = {
            "action": "REVIEW_EXCEPTIONS",
            "practice_id": practice.id,
            "practice_name": practice.name,
            "params": {},
            "reason": "Test risk",
            "supporting_metrics": {},
            "severity": "low",
        }

        result = ActionProposalService.simulate_proposal(db, proposal)
        assert result["risk_assessment"] in ["low", "medium", "high"]
