"""Tests for Economics aggregates and Action Proposals."""
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
from app.services.economics import EconomicsService
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


def _create_practice(db, name="Econ Test Practice", limit=500_000_00):
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
        fingerprint=f"econ-test-{practice_id}-{Claim.generate_claim_token()}",
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
        idempotency_key=f"econ-test-{claim_id}-{Claim.generate_claim_token()}",
        provider=PaymentProvider.SIMULATED.value,
        sent_at=datetime.utcnow() - timedelta(hours=24),
        confirmed_at=datetime.utcnow() if status == PaymentIntentStatus.CONFIRMED.value else None,
    )
    db.add(pi)
    db.flush()
    return pi


class TestEconomicsSummary:

    def test_summary_returns_expected_keys(self, db):
        summary = EconomicsService.get_liquidity_summary(db)
        expected_keys = [
            "available_cash_cents",
            "reserved_cents",
            "in_flight_cents",
            "settled_cents",
            "in_clearing_cents",
            "total_practice_payable_cents",
            "currency",
        ]
        for key in expected_keys:
            assert key in summary, f"Missing key: {key}"

    def test_summary_values_are_numeric(self, db):
        from decimal import Decimal
        summary = EconomicsService.get_liquidity_summary(db)
        for key in ["available_cash_cents", "reserved_cents", "in_flight_cents", "settled_cents"]:
            assert isinstance(summary[key], (int, float, Decimal)), f"{key} should be numeric, got {type(summary[key])}"

    def test_summary_currency_default(self, db):
        summary = EconomicsService.get_liquidity_summary(db)
        assert summary["currency"] == "USD"


class TestEconomicsExposure:

    def test_exposure_returns_expected_keys(self, db):
        exposure = EconomicsService.get_exposure(db)
        assert "by_practice" in exposure
        assert "aging_buckets" in exposure
        assert "concentration" in exposure

    def test_exposure_by_practice_structure(self, db):
        practice = _create_practice(db)
        c = _create_claim(db, practice.id, amount=100_000, status=ClaimStatus.PAID.value)
        _create_payment(db, c.id, practice.id, 100_000)
        db.commit()

        exposure = EconomicsService.get_exposure(db)
        by_practice = exposure["by_practice"]
        assert isinstance(by_practice, list)
        if by_practice:
            row = by_practice[0]
            assert "practice_id" in row
            assert "practice_name" in row
            assert "total_funded_cents" in row

    def test_aging_buckets_structure(self, db):
        exposure = EconomicsService.get_exposure(db)
        buckets = exposure["aging_buckets"]
        assert isinstance(buckets, list)
        for b in buckets:
            assert "bucket" in b
            assert "claim_count" in b
            assert "total_cents" in b

    def test_concentration_structure(self, db):
        practice = _create_practice(db)
        _create_claim(db, practice.id, payer="Big Payer", amount=80_000)
        _create_claim(db, practice.id, payer="Small Payer", amount=20_000)
        db.commit()

        exposure = EconomicsService.get_exposure(db)
        concentration = exposure["concentration"]
        assert isinstance(concentration, list)


class TestPaymentIntentsBoard:

    def test_board_returns_expected_keys(self, db):
        board = EconomicsService.get_payment_intents_board(db)
        assert "items" in board
        assert "status_counts" in board
        assert "total" in board
        assert isinstance(board["items"], list)
        assert isinstance(board["status_counts"], dict)

    def test_board_filters_by_status(self, db):
        practice = _create_practice(db)
        c1 = _create_claim(db, practice.id, amount=50_000, status=ClaimStatus.PAID.value)
        _create_payment(db, c1.id, practice.id, 50_000, status=PaymentIntentStatus.CONFIRMED.value)
        c2 = _create_claim(db, practice.id, amount=30_000, status=ClaimStatus.PAID.value)
        _create_payment(db, c2.id, practice.id, 30_000, status=PaymentIntentStatus.FAILED.value)
        db.commit()

        confirmed = EconomicsService.get_payment_intents_board(db, status_filter=PaymentIntentStatus.CONFIRMED.value)
        for item in confirmed["items"]:
            assert item["status"] == PaymentIntentStatus.CONFIRMED.value


class TestPracticeExposure:

    def test_practice_exposure_returns_expected_keys(self, db):
        practice = _create_practice(db, limit=200_000_00)
        c = _create_claim(db, practice.id, amount=100_000, status=ClaimStatus.PAID.value)
        _create_payment(db, c.id, practice.id, 100_000)
        db.commit()

        exp = EconomicsService.get_practice_exposure(db, practice.id)
        assert "practice_id" in exp
        assert "funded_outstanding_cents" in exp
        assert "funding_limit_cents" in exp
        assert "utilization_pct" in exp


class TestActionProposals:

    def test_generate_returns_proposals_list(self, db):
        practice = _create_practice(db, limit=100_000)
        for i in range(5):
            c = _create_claim(db, practice.id, amount=18_000, status=ClaimStatus.PAID.value)
            _create_payment(db, c.id, practice.id, 18_000)
        db.commit()

        result = ActionProposalService.generate_proposals(db)
        assert isinstance(result, list)

    def test_proposal_has_required_fields(self, db):
        practice = _create_practice(db, limit=100_000)
        for i in range(5):
            c = _create_claim(db, practice.id, amount=18_000, status=ClaimStatus.PAID.value)
            _create_payment(db, c.id, practice.id, 18_000)
        db.commit()

        result = ActionProposalService.generate_proposals(db, practice_id=practice.id)
        if result:
            p = result[0]
            assert "action" in p
            assert "practice_id" in p
            assert "reason" in p
            assert "supporting_metrics" in p

    def test_validate_proposal_structure(self, db):
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
            "reason": "Test adjustment",
            "supporting_metrics": {},
            "severity": "medium",
        }

        result = ActionProposalService.validate_proposal(db, proposal)
        assert "valid" in result
        assert isinstance(result["valid"], bool)


class TestEconomicsIntegration:

    def test_economics_summary_returns_expected_keys_integration(self, db):
        summary = EconomicsService.get_liquidity_summary(db)
        assert "available_cash_cents" in summary
        assert "reserved_cents" in summary
        assert "in_flight_cents" in summary
        assert "settled_cents" in summary
        assert "in_clearing_cents" in summary
        assert "total_practice_payable_cents" in summary
        assert summary["currency"] == "USD"

    def test_exposure_returns_all_sections(self, db):
        exposure = EconomicsService.get_exposure(db)
        assert "by_practice" in exposure
        assert "aging_buckets" in exposure
        assert "concentration" in exposure
        assert len(exposure["aging_buckets"]) > 0
