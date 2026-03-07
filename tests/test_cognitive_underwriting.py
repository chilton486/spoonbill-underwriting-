"""Tests for Cognitive Underwriting (Anthropic integration).

Tests cover:
- Pydantic schema validation for all input/output types
- AnthropicService output validation with mocked responses
- AnthropicService fallback behavior when provider fails
- CognitiveUnderwritingService merge_decisions policy
- CognitiveUnderwritingService run_cognitive_layer integration
- UnderwritingRun persistence and audit trail
- Tenant isolation for cognitive runs
- EOB parsing schema handling
- Ontology update proposal validation
- Prompt template formatting
"""
import json
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.practice import Practice
from app.models.claim import Claim, ClaimStatus
from app.models.underwriting_run import UnderwritingRun
from app.schemas.cognitive import (
    CognitiveRecommendation,
    ReconciliationAction,
    UnderwriteClaimInput,
    UnderwriteClaimOutput,
    ParseEobInput,
    ParseEobOutput,
    OntologyUpdateInput,
    OntologyUpdateOutput,
    PracticeContext,
    PayerContext,
    DeterministicSignals,
    RiskFactor,
    PolicyFlag,
    OntologyObservation,
    NextAction,
    EobClaimMatch,
    EobLineAdjudication,
    EntityUpdate,
    KPIUpdate,
    RiskFlag,
    BehaviorObservation,
    ClaimLineContext,
    PayerContractContext,
    ProviderContext,
    UnderwritingRunResponse,
)
from app.services.anthropic_service import AnthropicService, AnthropicServiceError
from app.services.cognitive_underwriting import CognitiveUnderwritingService
from app.prompts.underwriting_v1 import (
    SYSTEM_PROMPT as UW_SYSTEM_PROMPT,
    VERSION as UW_VERSION,
    format_user_prompt as format_uw_prompt,
)
from app.prompts.eob_parsing_v1 import (
    SYSTEM_PROMPT as EOB_SYSTEM_PROMPT,
    VERSION as EOB_VERSION,
    format_user_prompt as format_eob_prompt,
)
from app.prompts.ontology_updates_v1 import (
    SYSTEM_PROMPT as ONTO_SYSTEM_PROMPT,
    VERSION as ONTO_VERSION,
    format_user_prompt as format_onto_prompt,
)

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

def _make_practice(db, name="Cognitive Test Practice", limit=100_000_00):
    p = Practice(name=name, status="ACTIVE", funding_limit_cents=limit)
    db.add(p)
    db.flush()
    return p


def _make_claim(db, practice_id, amount=50000, status=ClaimStatus.APPROVED.value):
    c = Claim(
        practice_id=practice_id,
        patient_name="Test Patient",
        payer="Test Payer",
        amount_cents=amount,
        total_billed_cents=amount,
        total_allowed_cents=int(amount * 0.8),
        status=status,
        procedure_date=date.today() - timedelta(days=30),
        submitted_at=datetime.utcnow() - timedelta(days=28),
        claim_token=Claim.generate_claim_token(),
        fingerprint=f"cog-test-{practice_id}-{Claim.generate_claim_token()}",
        source_system="TEST",
    )
    db.add(c)
    db.flush()
    return c


def _mock_underwrite_response():
    """Return a realistic mocked Anthropic underwriting JSON response."""
    return {
        "recommendation": "APPROVE",
        "risk_score": 0.25,
        "confidence_score": 0.85,
        "suggested_advance_rate": 0.80,
        "suggested_max_advance_amount_cents": 40000,
        "fee_rate_suggestion": 0.03,
        "required_documents": ["Pre-authorization form"],
        "key_risk_factors": [
            {"factor": "New practice", "severity": "LOW", "detail": "Practice has limited history"}
        ],
        "rationale_summary": "Low-risk preventive procedure with established payer. Recommend approval.",
        "rationale_detailed": "The claim is for a routine preventive dental procedure with a PPO payer that has a strong reimbursement history. Risk factors are minimal.",
        "policy_flags": [
            {"flag": "FIRST_CLAIM", "detail": "First claim from this practice"}
        ],
        "ontology_observations": [
            {"entity_type": "payer", "observation": "Payer has reliable EFT capability", "confidence": 0.9}
        ],
        "next_actions": [
            {"action": "Monitor", "detail": "Track first payment cycle time", "priority": "LOW"}
        ],
    }


def _mock_eob_response():
    """Return a realistic mocked EOB parsing JSON response."""
    return {
        "trace_number": "TRC-2024-001",
        "check_number": "CHK-5555",
        "payment_method": "EFT",
        "payer_name": "Delta Dental",
        "payer_id_code": "DD-001",
        "payment_date": "2024-06-15",
        "total_paid_cents": 35000,
        "total_adjustments_cents": 5000,
        "total_billed_cents": 40000,
        "claim_matches": [
            {
                "external_claim_id": "CLM-001",
                "patient_name": "John Smith",
                "procedure_date": "2024-06-01",
                "confidence": 0.95,
                "match_method": "claim_id",
            }
        ],
        "line_adjudications": [
            {
                "cdt_code": "D0120",
                "description": "Periodic oral eval",
                "billed_cents": 5000,
                "allowed_cents": 4500,
                "paid_cents": 4500,
                "adjustment_cents": 500,
                "adjustment_reason_codes": ["CO-45"],
                "denial_code": None,
                "denial_reason": None,
                "remark_codes": [],
            }
        ],
        "overall_confidence": 0.92,
        "ambiguity_flags": [],
        "recommended_action": "AUTO_POST",
        "action_rationale": "High confidence match with complete adjudication data.",
    }


def _mock_ontology_response():
    """Return a realistic mocked ontology update JSON response."""
    return {
        "proposed_entity_updates": [
            {
                "entity_type": "payer",
                "entity_identifier": "Delta Dental",
                "field": "avg_cycle_days",
                "current_value": "30",
                "proposed_value": "28",
                "reason": "Recent claims show faster processing",
                "confidence": 0.8,
            }
        ],
        "proposed_kpi_updates": [
            {
                "metric_name": "denial_rate",
                "entity_type": "payer",
                "entity_identifier": "Delta Dental",
                "current_value": 0.12,
                "proposed_value": 0.10,
                "direction": "DECREASE",
                "reason": "Improved clean claim rate",
            }
        ],
        "risk_flags": [
            {
                "entity_type": "practice",
                "entity_identifier": "Test Practice",
                "flag_type": "HIGH_DENIAL_RATE",
                "severity": "MEDIUM",
                "detail": "Practice denial rate above average",
                "recommended_action": "Review documentation requirements",
            }
        ],
        "payer_observations": [
            {
                "entity_type": "payer",
                "entity_identifier": "Delta Dental",
                "observation": "Consistent payment behavior",
                "evidence": "5 consecutive on-time payments",
                "confidence": 0.85,
            }
        ],
        "procedure_observations": [],
        "provider_observations": [],
        "practice_observations": [],
        "review_needed": False,
        "overall_confidence": 0.82,
        "summary": "Payer performance improving. Practice denial rate warrants monitoring.",
    }


# ── Schema Validation Tests ──────────────────────────────────────────

class TestCognitiveSchemas:

    def test_cognitive_recommendation_enum(self):
        assert CognitiveRecommendation.APPROVE.value == "APPROVE"
        assert CognitiveRecommendation.DECLINE.value == "DECLINE"
        assert CognitiveRecommendation.NEEDS_REVIEW.value == "NEEDS_REVIEW"

    def test_reconciliation_action_enum(self):
        assert ReconciliationAction.AUTO_POST.value == "AUTO_POST"
        assert ReconciliationAction.MANUAL_REVIEW.value == "MANUAL_REVIEW"
        assert ReconciliationAction.HOLD.value == "HOLD"
        assert ReconciliationAction.REJECT.value == "REJECT"

    def test_underwrite_claim_input_minimal(self):
        """Test minimum required fields for UnderwriteClaimInput."""
        inp = UnderwriteClaimInput(
            claim_id=1,
            practice=PracticeContext(id=1, name="Test Practice"),
            payer=PayerContext(name="Test Payer"),
            deterministic=DeterministicSignals(decision="APPROVE"),
        )
        assert inp.claim_id == 1
        assert inp.practice.name == "Test Practice"
        assert inp.total_billed_cents == 0
        assert inp.claim_lines == []

    def test_underwrite_claim_input_full(self):
        """Test all fields for UnderwriteClaimInput."""
        inp = UnderwriteClaimInput(
            claim_id=1,
            claim_token="tok-123",
            external_claim_id="EXT-001",
            practice=PracticeContext(
                id=1, name="Full Practice", status="ACTIVE",
                pms_type="Dentrix", clearinghouse="Tesia",
                state="TX", total_claims=100,
                total_billed_cents=5000000, total_funded_cents=3000000,
                funding_utilization=0.60, historical_denial_rate=0.08,
            ),
            payer=PayerContext(
                id=5, name="Delta Dental", plan_types=["PPO", "HMO"],
                eft_capable=True, era_capable=True, filing_limit_days=365,
            ),
            payer_contract=PayerContractContext(
                id=10, network_status="IN_NETWORK", status="ACTIVE",
                timely_filing_limit_days=180,
            ),
            provider=ProviderContext(
                id=3, full_name="Dr. Smith", npi="1234567890",
                specialty="General Dentistry", role="OWNER",
            ),
            claim_lines=[
                ClaimLineContext(
                    cdt_code="D0120", description="Periodic eval",
                    category="PREVENTIVE", billed_fee_cents=5000, units=1,
                )
            ],
            total_billed_cents=50000,
            total_allowed_cents=40000,
            patient_responsibility_estimate=10000,
            procedure_date="2024-06-01",
            submitted_at="2024-06-03T12:00:00",
            claim_age_days=30,
            deterministic=DeterministicSignals(
                decision="APPROVE",
                reasons=[{"rule": "AMOUNT_OK", "detail": "Within threshold"}],
                duplicate_detected=False,
                amount_exceeds_threshold=False,
            ),
            historical_payer_denial_rate=0.10,
            historical_payer_avg_cycle_days=28.5,
            practice_clean_claim_rate=0.92,
        )
        assert inp.total_billed_cents == 50000
        assert len(inp.claim_lines) == 1
        assert inp.practice.pms_type == "Dentrix"
        assert inp.payer.plan_types == ["PPO", "HMO"]

    def test_underwrite_claim_output_validation(self):
        """Test UnderwriteClaimOutput validates response data."""
        data = _mock_underwrite_response()
        output = UnderwriteClaimOutput(**data, model_version="test", prompt_version="test-v1")
        assert output.recommendation == CognitiveRecommendation.APPROVE
        assert output.risk_score == 0.25
        assert output.confidence_score == 0.85
        assert len(output.key_risk_factors) == 1
        assert output.key_risk_factors[0].severity == "LOW"
        assert len(output.required_documents) == 1
        assert output.rationale_summary != ""

    def test_underwrite_claim_output_score_bounds(self):
        """Test that risk_score and confidence_score are bounded."""
        with pytest.raises(Exception):
            UnderwriteClaimOutput(
                recommendation=CognitiveRecommendation.APPROVE,
                risk_score=1.5,  # out of bounds
                confidence_score=0.5,
            )
        with pytest.raises(Exception):
            UnderwriteClaimOutput(
                recommendation=CognitiveRecommendation.APPROVE,
                risk_score=0.5,
                confidence_score=-0.1,  # out of bounds
            )

    def test_parse_eob_input(self):
        inp = ParseEobInput(
            raw_text="EXPLANATION OF BENEFITS\nPayer: Delta Dental\nDate: 2024-06-15",
            practice_id=1,
            known_claim_ids=["CLM-001"],
            known_payer_names=["Delta Dental"],
        )
        assert inp.raw_text.startswith("EXPLANATION")
        assert inp.practice_id == 1

    def test_parse_eob_output_validation(self):
        data = _mock_eob_response()
        output = ParseEobOutput(**data, model_version="test", prompt_version="test-v1")
        assert output.trace_number == "TRC-2024-001"
        assert output.total_paid_cents == 35000
        assert len(output.claim_matches) == 1
        assert output.claim_matches[0].confidence == 0.95
        assert output.recommended_action == ReconciliationAction.AUTO_POST
        assert len(output.line_adjudications) == 1

    def test_ontology_update_input(self):
        inp = OntologyUpdateInput(
            practice_id=1,
            claim_id=10,
            claim_status="APPROVED",
            claim_payer="Delta Dental",
            claim_total_billed_cents=50000,
            claim_total_paid_cents=40000,
            funding_decision="APPROVE",
            risk_score=0.2,
            payer_name="Delta Dental",
        )
        assert inp.practice_id == 1
        assert inp.funding_decision == "APPROVE"

    def test_ontology_update_output_validation(self):
        data = _mock_ontology_response()
        output = OntologyUpdateOutput(**data, model_version="test", prompt_version="test-v1")
        assert len(output.proposed_entity_updates) == 1
        assert output.proposed_entity_updates[0].entity_type == "payer"
        assert len(output.risk_flags) == 1
        assert output.review_needed is False
        assert output.overall_confidence == 0.82

    def test_risk_factor_schema(self):
        rf = RiskFactor(factor="High amount", severity="HIGH", detail="Claim amount is unusually high")
        assert rf.severity == "HIGH"

    def test_policy_flag_schema(self):
        pf = PolicyFlag(flag="NEW_PAYER", detail="First claim with this payer")
        assert pf.flag == "NEW_PAYER"

    def test_ontology_observation_schema(self):
        obs = OntologyObservation(entity_type="payer", observation="Good track record", confidence=0.9)
        assert obs.confidence == 0.9

    def test_next_action_schema(self):
        na = NextAction(action="Review", detail="Check documentation", priority="HIGH")
        assert na.priority == "HIGH"

    def test_eob_claim_match_confidence_bounds(self):
        match = EobClaimMatch(confidence=0.95, match_method="claim_id")
        assert match.confidence == 0.95
        with pytest.raises(Exception):
            EobClaimMatch(confidence=1.5, match_method="test")

    def test_entity_update_schema(self):
        eu = EntityUpdate(
            entity_type="payer",
            entity_identifier="Delta",
            field="denial_rate",
            proposed_value="0.10",
            reason="Improved",
            confidence=0.8,
        )
        assert eu.entity_type == "payer"

    def test_behavior_observation_schema(self):
        bo = BehaviorObservation(
            entity_type="provider",
            entity_identifier="Dr. Smith",
            observation="High productivity",
            confidence=0.75,
        )
        assert bo.confidence == 0.75

    def test_underwriting_run_response_schema(self):
        resp = UnderwritingRunResponse(
            id=1,
            claim_id=10,
            model_provider="anthropic",
            model_name="claude-sonnet-4-20250514",
            prompt_version="underwriting-v1",
            recommendation="APPROVE",
            risk_score=0.25,
            confidence_score=0.85,
            latency_ms=1200,
            fallback_used=False,
            parse_success=True,
            merged_recommendation="APPROVE",
            deterministic_recommendation="APPROVE",
        )
        assert resp.id == 1
        assert resp.model_provider == "anthropic"


# ── Merge Decision Policy Tests ──────────────────────────────────────

class TestMergeDecisions:
    """Test the two-layer decision merge policy."""

    def _make_output(self, recommendation):
        data = _mock_underwrite_response()
        data["recommendation"] = recommendation
        return UnderwriteClaimOutput(**data, model_version="test", prompt_version="test")

    def test_none_cognitive_returns_deterministic(self):
        result = CognitiveUnderwritingService.merge_decisions("APPROVE", None)
        assert result == "APPROVE"

    def test_none_cognitive_returns_decline(self):
        result = CognitiveUnderwritingService.merge_decisions("DECLINE", None)
        assert result == "DECLINE"

    def test_deterministic_decline_always_wins(self):
        """Deterministic DECLINE is a hard block - model cannot override."""
        for model_rec in ["APPROVE", "DECLINE", "NEEDS_REVIEW"]:
            output = self._make_output(model_rec)
            result = CognitiveUnderwritingService.merge_decisions("DECLINE", output)
            assert result == "DECLINE", f"Expected DECLINE but got {result} when model said {model_rec}"

    def test_approve_plus_approve(self):
        output = self._make_output("APPROVE")
        result = CognitiveUnderwritingService.merge_decisions("APPROVE", output)
        assert result == "APPROVE"

    def test_approve_plus_needs_review(self):
        """If deterministic approves but model sees ambiguity, escalate."""
        output = self._make_output("NEEDS_REVIEW")
        result = CognitiveUnderwritingService.merge_decisions("APPROVE", output)
        assert result == "NEEDS_REVIEW"

    def test_approve_plus_decline(self):
        """If deterministic approves but model says decline, escalate to review (don't auto-decline)."""
        output = self._make_output("DECLINE")
        result = CognitiveUnderwritingService.merge_decisions("APPROVE", output)
        assert result == "NEEDS_REVIEW"

    def test_needs_review_plus_approve(self):
        """Model cannot auto-approve out of NEEDS_REVIEW."""
        output = self._make_output("APPROVE")
        result = CognitiveUnderwritingService.merge_decisions("NEEDS_REVIEW", output)
        assert result == "NEEDS_REVIEW"

    def test_needs_review_plus_needs_review(self):
        output = self._make_output("NEEDS_REVIEW")
        result = CognitiveUnderwritingService.merge_decisions("NEEDS_REVIEW", output)
        assert result == "NEEDS_REVIEW"

    def test_needs_review_plus_decline(self):
        """If both layers agree it's bad, decline."""
        output = self._make_output("DECLINE")
        result = CognitiveUnderwritingService.merge_decisions("NEEDS_REVIEW", output)
        assert result == "DECLINE"

    def test_unknown_deterministic_passthrough(self):
        """Unknown deterministic values pass through."""
        result = CognitiveUnderwritingService.merge_decisions("PENDING", None)
        assert result == "PENDING"


# ── AnthropicService Tests (Mocked) ──────────────────────────────────

class TestAnthropicServiceMocked:
    """Test AnthropicService with mocked Anthropic SDK calls."""

    def test_compute_input_hash_deterministic(self):
        """Same input should produce the same hash."""
        data1 = {"claim_id": 1, "amount": 5000}
        data2 = {"claim_id": 1, "amount": 5000}
        h1 = AnthropicService._compute_input_hash(data1)
        h2 = AnthropicService._compute_input_hash(data2)
        assert h1 == h2
        assert len(h1) == 16

    def test_compute_input_hash_different(self):
        data1 = {"claim_id": 1, "amount": 5000}
        data2 = {"claim_id": 2, "amount": 5000}
        h1 = AnthropicService._compute_input_hash(data1)
        h2 = AnthropicService._compute_input_hash(data2)
        assert h1 != h2

    def test_parse_json_response_plain(self):
        text = '{"recommendation": "APPROVE", "risk_score": 0.2}'
        result = AnthropicService._parse_json_response(text)
        assert result["recommendation"] == "APPROVE"

    def test_parse_json_response_markdown(self):
        text = '```json\n{"recommendation": "APPROVE"}\n```'
        result = AnthropicService._parse_json_response(text)
        assert result["recommendation"] == "APPROVE"

    def test_parse_json_response_invalid(self):
        with pytest.raises(AnthropicServiceError, match="Invalid JSON"):
            AnthropicService._parse_json_response("not json at all")

    def test_is_available_disabled(self):
        """When anthropic_enabled is False, service should not be available."""
        with patch("app.services.anthropic_service.settings") as mock_settings:
            mock_settings.anthropic_enabled = False
            mock_settings.anthropic_api_key = "test-key"
            assert AnthropicService.is_available() is False

    def test_is_available_no_key(self):
        with patch("app.services.anthropic_service.settings") as mock_settings:
            mock_settings.anthropic_enabled = True
            mock_settings.anthropic_api_key = ""
            assert AnthropicService.is_available() is False

    def test_is_available_enabled(self):
        with patch("app.services.anthropic_service.settings") as mock_settings:
            mock_settings.anthropic_enabled = True
            mock_settings.anthropic_api_key = "sk-test-key"
            assert AnthropicService.is_available() is True

    @patch.object(AnthropicService, "_call_anthropic")
    def test_underwrite_claim_success(self, mock_call):
        """Test successful underwriting with mocked Anthropic response."""
        response_data = _mock_underwrite_response()
        mock_call.return_value = (json.dumps(response_data), 1200)

        inp = UnderwriteClaimInput(
            claim_id=1,
            practice=PracticeContext(id=1, name="Test"),
            payer=PayerContext(name="Delta Dental"),
            deterministic=DeterministicSignals(decision="APPROVE"),
            total_billed_cents=50000,
        )

        with patch("app.services.anthropic_service.settings") as mock_settings:
            mock_settings.anthropic_model = "claude-sonnet-4-20250514"
            output, metadata = AnthropicService.underwrite_claim(inp)

        assert output.recommendation == CognitiveRecommendation.APPROVE
        assert output.risk_score == 0.25
        assert output.confidence_score == 0.85
        assert metadata["latency_ms"] == 1200
        assert metadata["parse_success"] is True
        assert len(metadata["input_hash"]) == 16

    @patch.object(AnthropicService, "_call_anthropic")
    def test_underwrite_claim_invalid_json(self, mock_call):
        """Test that invalid JSON from model raises AnthropicServiceError."""
        mock_call.return_value = ("not valid json", 500)

        inp = UnderwriteClaimInput(
            claim_id=1,
            practice=PracticeContext(id=1, name="Test"),
            payer=PayerContext(name="Test"),
            deterministic=DeterministicSignals(decision="APPROVE"),
        )

        with pytest.raises(AnthropicServiceError, match="Invalid JSON"):
            AnthropicService.underwrite_claim(inp)

    @patch.object(AnthropicService, "_call_anthropic")
    def test_underwrite_claim_schema_violation(self, mock_call):
        """Test that response missing required fields raises error."""
        mock_call.return_value = (json.dumps({"recommendation": "APPROVE"}), 300)

        inp = UnderwriteClaimInput(
            claim_id=1,
            practice=PracticeContext(id=1, name="Test"),
            payer=PayerContext(name="Test"),
            deterministic=DeterministicSignals(decision="APPROVE"),
        )

        with pytest.raises(AnthropicServiceError, match="Output validation failed"):
            AnthropicService.underwrite_claim(inp)

    @patch.object(AnthropicService, "_call_anthropic")
    def test_parse_eob_success(self, mock_call):
        """Test successful EOB parsing with mocked response."""
        response_data = _mock_eob_response()
        mock_call.return_value = (json.dumps(response_data), 800)

        inp = ParseEobInput(
            raw_text="EOB text here",
            practice_id=1,
        )

        with patch("app.services.anthropic_service.settings") as mock_settings:
            mock_settings.anthropic_model = "claude-sonnet-4-20250514"
            output, metadata = AnthropicService.parse_eob(inp)

        assert output.trace_number == "TRC-2024-001"
        assert output.total_paid_cents == 35000
        assert output.recommended_action == ReconciliationAction.AUTO_POST
        assert metadata["latency_ms"] == 800

    @patch.object(AnthropicService, "_call_anthropic")
    def test_generate_ontology_updates_success(self, mock_call):
        """Test successful ontology update generation."""
        response_data = _mock_ontology_response()
        mock_call.return_value = (json.dumps(response_data), 600)

        inp = OntologyUpdateInput(
            practice_id=1,
            claim_id=10,
            claim_status="APPROVED",
            payer_name="Delta Dental",
        )

        with patch("app.services.anthropic_service.settings") as mock_settings:
            mock_settings.anthropic_model = "claude-sonnet-4-20250514"
            output, metadata = AnthropicService.generate_ontology_updates(inp)

        assert len(output.proposed_entity_updates) == 1
        assert output.review_needed is False
        assert output.overall_confidence == 0.82
        assert metadata["latency_ms"] == 600

    @patch.object(AnthropicService, "_call_anthropic")
    def test_anthropic_api_error_raises(self, mock_call):
        """Test that API errors are properly wrapped."""
        mock_call.side_effect = AnthropicServiceError("API timeout")

        inp = UnderwriteClaimInput(
            claim_id=1,
            practice=PracticeContext(id=1, name="Test"),
            payer=PayerContext(name="Test"),
            deterministic=DeterministicSignals(decision="APPROVE"),
        )

        with pytest.raises(AnthropicServiceError, match="API timeout"):
            AnthropicService.underwrite_claim(inp)


# ── CognitiveUnderwritingService Integration Tests ───────────────────

class TestCognitiveUnderwritingService:
    """Test the full cognitive underwriting orchestration."""

    def test_is_cognitive_enabled_false_by_default(self):
        """Cognitive underwriting should be disabled by default."""
        with patch("app.services.cognitive_underwriting.settings") as mock_settings:
            mock_settings.cognitive_underwriting_enabled = False
            with patch.object(AnthropicService, "is_available", return_value=True):
                assert CognitiveUnderwritingService.is_cognitive_enabled() is False

    def test_is_cognitive_enabled_true(self):
        with patch("app.services.cognitive_underwriting.settings") as mock_settings:
            mock_settings.cognitive_underwriting_enabled = True
            with patch.object(AnthropicService, "is_available", return_value=True):
                assert CognitiveUnderwritingService.is_cognitive_enabled() is True

    def test_run_cognitive_layer_disabled_returns_none(self, db):
        """When cognitive is disabled, run_cognitive_layer returns (None, None)."""
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)

        with patch.object(CognitiveUnderwritingService, "is_cognitive_enabled", return_value=False):
            output, run = CognitiveUnderwritingService.run_cognitive_layer(
                db, claim, "APPROVE", ["AMOUNT_OK"],
            )
        assert output is None
        assert run is None

    @patch.object(AnthropicService, "underwrite_claim")
    def test_run_cognitive_layer_success(self, mock_uw, db):
        """Test successful cognitive layer execution with persistence."""
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)

        response_data = _mock_underwrite_response()
        mock_output = UnderwriteClaimOutput(**response_data, model_version="test", prompt_version="test")
        mock_metadata = {
            "input_hash": "abcdef1234567890",
            "latency_ms": 1100,
            "model_name": "claude-sonnet-4-20250514",
            "prompt_version": "underwriting-v1",
            "parse_success": True,
            "raw_output": response_data,
        }
        mock_uw.return_value = (mock_output, mock_metadata)

        with patch.object(CognitiveUnderwritingService, "is_cognitive_enabled", return_value=True):
            output, run = CognitiveUnderwritingService.run_cognitive_layer(
                db, claim, "APPROVE", ["AMOUNT_OK"],
            )

        assert output is not None
        assert output.recommendation == CognitiveRecommendation.APPROVE
        assert run is not None
        assert run.claim_id == claim.id
        assert run.practice_id == practice.id
        assert run.model_provider == "anthropic"
        assert run.recommendation == "APPROVE"
        assert run.risk_score == 0.25
        assert run.confidence_score == 0.85
        assert run.latency_ms == 1100
        assert run.fallback_used is False
        assert run.parse_success is True
        assert run.deterministic_recommendation == "APPROVE"
        assert run.merged_recommendation == "APPROVE"

    @patch.object(AnthropicService, "underwrite_claim")
    def test_run_cognitive_layer_fallback_on_error(self, mock_uw, db):
        """Test fallback when Anthropic fails."""
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)

        mock_uw.side_effect = AnthropicServiceError("Connection timeout")

        with patch.object(CognitiveUnderwritingService, "is_cognitive_enabled", return_value=True):
            output, run = CognitiveUnderwritingService.run_cognitive_layer(
                db, claim, "APPROVE", ["AMOUNT_OK"],
            )

        assert output is None  # Fallback - no cognitive output
        assert run is not None  # But we still get a run record
        assert run.fallback_used is True
        assert run.fallback_reason == "Connection timeout"
        assert run.parse_success is False
        assert run.merged_recommendation == "APPROVE"  # Falls back to deterministic
        assert run.deterministic_recommendation == "APPROVE"

    @patch.object(AnthropicService, "underwrite_claim")
    def test_run_cognitive_layer_merge_escalation(self, mock_uw, db):
        """Test that model can escalate APPROVE to NEEDS_REVIEW."""
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)

        response_data = _mock_underwrite_response()
        response_data["recommendation"] = "NEEDS_REVIEW"
        response_data["risk_score"] = 0.55
        mock_output = UnderwriteClaimOutput(**response_data, model_version="test", prompt_version="test")
        mock_metadata = {
            "input_hash": "abc123",
            "latency_ms": 900,
            "model_name": "claude-sonnet-4-20250514",
            "prompt_version": "underwriting-v1",
            "parse_success": True,
            "raw_output": response_data,
        }
        mock_uw.return_value = (mock_output, mock_metadata)

        with patch.object(CognitiveUnderwritingService, "is_cognitive_enabled", return_value=True):
            output, run = CognitiveUnderwritingService.run_cognitive_layer(
                db, claim, "APPROVE", ["AMOUNT_OK"],
            )

        assert output.recommendation == CognitiveRecommendation.NEEDS_REVIEW
        assert run.recommendation == "NEEDS_REVIEW"
        assert run.deterministic_recommendation == "APPROVE"
        assert run.merged_recommendation == "NEEDS_REVIEW"  # Escalated


# ── UnderwritingRun Persistence Tests ─────────────────────────────────

class TestUnderwritingRunPersistence:
    """Test UnderwritingRun model and audit trail."""

    def test_create_underwriting_run(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)

        run = UnderwritingRun(
            claim_id=claim.id,
            practice_id=practice.id,
            model_provider="anthropic",
            model_name="claude-sonnet-4-20250514",
            prompt_version="underwriting-v1",
            input_hash="abcdef1234567890",
            output_json=_mock_underwrite_response(),
            recommendation="APPROVE",
            risk_score=0.25,
            confidence_score=0.85,
            run_type="underwrite_claim",
            latency_ms=1200,
            fallback_used=False,
            parse_success=True,
            deterministic_recommendation="APPROVE",
            merged_recommendation="APPROVE",
        )
        db.add(run)
        db.flush()

        assert run.id is not None
        assert run.claim_id == claim.id
        assert run.practice_id == practice.id
        assert run.model_provider == "anthropic"
        assert run.recommendation == "APPROVE"
        assert run.output_json is not None

    def test_create_fallback_run(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)

        run = UnderwritingRun(
            claim_id=claim.id,
            practice_id=practice.id,
            model_provider="anthropic",
            model_name="claude-sonnet-4-20250514",
            prompt_version="underwriting-v1",
            run_type="underwrite_claim",
            fallback_used=True,
            fallback_reason="API timeout after 30s",
            parse_success=False,
            error_message="Connection timeout",
            deterministic_recommendation="APPROVE",
            merged_recommendation="APPROVE",
        )
        db.add(run)
        db.flush()

        assert run.id is not None
        assert run.fallback_used is True
        assert run.fallback_reason == "API timeout after 30s"
        assert run.parse_success is False
        assert run.output_json is None

    def test_eob_parsing_run(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)

        run = UnderwritingRun(
            claim_id=claim.id,
            practice_id=practice.id,
            model_provider="anthropic",
            model_name="claude-sonnet-4-20250514",
            prompt_version="eob-parsing-v1",
            run_type="parse_eob",
            output_json=_mock_eob_response(),
            latency_ms=800,
            fallback_used=False,
            parse_success=True,
        )
        db.add(run)
        db.flush()

        assert run.run_type == "parse_eob"
        assert run.output_json["trace_number"] == "TRC-2024-001"

    def test_ontology_update_run(self, db):
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)

        run = UnderwritingRun(
            claim_id=claim.id,
            practice_id=practice.id,
            model_provider="anthropic",
            model_name="claude-sonnet-4-20250514",
            prompt_version="ontology-updates-v1",
            run_type="ontology_updates",
            output_json=_mock_ontology_response(),
            latency_ms=600,
            fallback_used=False,
            parse_success=True,
        )
        db.add(run)
        db.flush()

        assert run.run_type == "ontology_updates"

    def test_run_created_at_auto(self, db):
        """Test that created_at is automatically set."""
        practice = _make_practice(db)
        claim = _make_claim(db, practice.id)

        run = UnderwritingRun(
            claim_id=claim.id,
            practice_id=practice.id,
            model_provider="anthropic",
            model_name="test",
            prompt_version="test",
            run_type="underwrite_claim",
            fallback_used=False,
            parse_success=True,
        )
        db.add(run)
        db.flush()

        assert run.created_at is not None


# ── Tenant Isolation for Cognitive Runs ───────────────────────────────

class TestCognitiveTenantIsolation:

    def test_runs_scoped_to_practice(self, db):
        """Verify underwriting runs are properly scoped to practice."""
        p1 = _make_practice(db, name="Cognitive P1")
        p2 = _make_practice(db, name="Cognitive P2")
        c1 = _make_claim(db, p1.id)
        c2 = _make_claim(db, p2.id)

        run1 = UnderwritingRun(
            claim_id=c1.id,
            practice_id=p1.id,
            model_provider="anthropic",
            model_name="test",
            prompt_version="test",
            run_type="underwrite_claim",
            recommendation="APPROVE",
            fallback_used=False,
            parse_success=True,
        )
        run2 = UnderwritingRun(
            claim_id=c2.id,
            practice_id=p2.id,
            model_provider="anthropic",
            model_name="test",
            prompt_version="test",
            run_type="underwrite_claim",
            recommendation="NEEDS_REVIEW",
            fallback_used=False,
            parse_success=True,
        )
        db.add(run1)
        db.add(run2)
        db.flush()

        p1_runs = db.query(UnderwritingRun).filter(
            UnderwritingRun.practice_id == p1.id
        ).all()
        p2_runs = db.query(UnderwritingRun).filter(
            UnderwritingRun.practice_id == p2.id
        ).all()

        p1_claims = [r.claim_id for r in p1_runs]
        p2_claims = [r.claim_id for r in p2_runs]

        assert c1.id in p1_claims
        assert c2.id not in p1_claims
        assert c2.id in p2_claims
        assert c1.id not in p2_claims


# ── Prompt Template Tests ─────────────────────────────────────────────

class TestPromptTemplates:
    """Test prompt template formatting and versioning."""

    def test_underwriting_prompt_version(self):
        assert UW_VERSION == "underwriting-v1"

    def test_eob_prompt_version(self):
        assert EOB_VERSION == "eob-parsing-v1"

    def test_ontology_prompt_version(self):
        assert ONTO_VERSION == "ontology-updates-v1"

    def test_underwriting_system_prompt_content(self):
        assert "structured financial underwriting assistant" in UW_SYSTEM_PROMPT
        assert "NEEDS_REVIEW" in UW_SYSTEM_PROMPT
        assert "risk_score" in UW_SYSTEM_PROMPT
        assert "schema-valid structured JSON" in UW_SYSTEM_PROMPT

    def test_underwriting_user_prompt_formatting(self):
        input_data = {
            "claim_id": 1,
            "claim_token": "tok-abc",
            "total_billed_cents": 50000,
            "procedure_date": "2024-06-01",
            "claim_age_days": 30,
            "practice": {"name": "Test Practice", "state": "TX", "pms_type": "Dentrix"},
            "payer": {"name": "Delta Dental", "plan_types": ["PPO"], "eft_capable": True, "era_capable": True, "filing_limit_days": 365},
            "deterministic": {
                "decision": "APPROVE",
                "reasons": [{"rule": "OK", "detail": "Within limits"}],
                "duplicate_detected": False,
                "missing_required_fields": [],
                "amount_exceeds_threshold": False,
                "inactive_contract": False,
            },
            "claim_lines": [
                {"cdt_code": "D0120", "description": "Periodic eval", "billed_fee_cents": 5000},
            ],
        }
        prompt = format_uw_prompt(input_data)
        assert "Test Practice" in prompt
        assert "Delta Dental" in prompt
        assert "APPROVE" in prompt
        assert "D0120" in prompt
        assert "$500.00" in prompt

    def test_eob_user_prompt_formatting(self):
        input_data = {
            "raw_text": "EOB from Delta Dental, payment date 2024-06-15",
            "practice_id": 1,
            "known_claim_ids": ["CLM-001", "CLM-002"],
            "known_payer_names": ["Delta Dental"],
        }
        prompt = format_eob_prompt(input_data)
        assert "EOB from Delta Dental" in prompt

    def test_ontology_user_prompt_formatting(self):
        input_data = {
            "practice_id": 1,
            "practice_name": "Test Practice",
            "claim_id": 10,
            "claim_status": "APPROVED",
            "payer_name": "Delta Dental",
        }
        prompt = format_onto_prompt(input_data)
        assert "Test Practice" in prompt


# ── Config Tests ─────────────────────────────────────────────────────

class TestCognitiveConfig:
    """Test cognitive underwriting configuration."""

    def test_default_config_disabled(self):
        """By default, cognitive features should be disabled."""
        from app.config import Settings
        s = Settings()
        assert s.anthropic_enabled is False
        assert s.cognitive_underwriting_enabled is False
        assert s.cognitive_eob_parsing_enabled is False
        assert s.cognitive_ontology_updates_enabled is False

    def test_default_model(self):
        from app.config import Settings
        s = Settings()
        assert s.anthropic_model == "claude-sonnet-4-20250514"

    def test_default_timeout(self):
        from app.config import Settings
        s = Settings()
        assert s.anthropic_timeout_seconds == 30

    def test_default_max_retries(self):
        from app.config import Settings
        s = Settings()
        assert s.anthropic_max_retries == 2
