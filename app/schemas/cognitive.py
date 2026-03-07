"""Pydantic schemas for Anthropic cognitive underwriting.

Structured input/output contracts for:
- underwrite_claim()
- parse_eob()
- generate_ontology_updates()
"""
from datetime import datetime, date
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────

class CognitiveRecommendation(str, Enum):
    APPROVE = "APPROVE"
    DECLINE = "DECLINE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ReconciliationAction(str, Enum):
    AUTO_POST = "AUTO_POST"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    HOLD = "HOLD"
    REJECT = "REJECT"


# ── Underwrite Claim ───────────────────────────────────────────────────

class ClaimLineContext(BaseModel):
    """Context for a single claim line."""
    cdt_code: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    billed_fee_cents: int = 0
    units: int = 1
    tooth: Optional[str] = None
    surface: Optional[str] = None
    common_denial_reasons: Optional[List[str]] = None
    risk_notes: Optional[str] = None


class PracticeContext(BaseModel):
    """Practice profile for underwriting context."""
    id: int
    name: str
    status: Optional[str] = None
    pms_type: Optional[str] = None
    clearinghouse: Optional[str] = None
    state: Optional[str] = None
    total_claims: Optional[int] = None
    total_billed_cents: Optional[int] = None
    total_funded_cents: Optional[int] = None
    funding_utilization: Optional[float] = None
    historical_denial_rate: Optional[float] = None


class PayerContext(BaseModel):
    """Payer metadata for underwriting context."""
    id: Optional[int] = None
    name: str
    plan_types: Optional[List[str]] = None
    eft_capable: Optional[bool] = None
    era_capable: Optional[bool] = None
    filing_limit_days: Optional[int] = None


class PayerContractContext(BaseModel):
    """Payer contract context."""
    id: Optional[int] = None
    network_status: Optional[str] = None
    status: Optional[str] = None
    timely_filing_limit_days: Optional[int] = None
    effective_start_date: Optional[str] = None
    effective_end_date: Optional[str] = None


class ProviderContext(BaseModel):
    """Provider context."""
    id: Optional[int] = None
    full_name: Optional[str] = None
    npi: Optional[str] = None
    specialty: Optional[str] = None
    role: Optional[str] = None


class DeterministicSignals(BaseModel):
    """Signals from the deterministic underwriting layer."""
    decision: str  # APPROVE, DECLINE, NEEDS_REVIEW
    reasons: List[Dict[str, str]] = Field(default_factory=list)
    duplicate_detected: bool = False
    missing_required_fields: List[str] = Field(default_factory=list)
    amount_exceeds_threshold: bool = False
    inactive_contract: bool = False


class UnderwriteClaimInput(BaseModel):
    """Full context for cognitive claim underwriting."""
    # Claim identifiers
    claim_id: int
    claim_token: Optional[str] = None
    external_claim_id: Optional[str] = None

    # Practice profile
    practice: PracticeContext

    # Payer metadata
    payer: PayerContext
    payer_contract: Optional[PayerContractContext] = None

    # Provider
    provider: Optional[ProviderContext] = None

    # Procedure lines
    claim_lines: List[ClaimLineContext] = Field(default_factory=list)

    # Financials
    total_billed_cents: int = 0
    total_allowed_cents: Optional[int] = None
    patient_responsibility_estimate: Optional[int] = None

    # Dates
    procedure_date: Optional[str] = None
    submitted_at: Optional[str] = None
    claim_age_days: Optional[int] = None

    # Deterministic layer signals
    deterministic: DeterministicSignals

    # Historical signals
    historical_payer_denial_rate: Optional[float] = None
    historical_payer_avg_cycle_days: Optional[float] = None
    practice_clean_claim_rate: Optional[float] = None


class RiskFactor(BaseModel):
    """A single risk factor identified by the model."""
    factor: str
    severity: str  # LOW, MEDIUM, HIGH
    detail: str


class PolicyFlag(BaseModel):
    """A policy flag from the model."""
    flag: str
    detail: str


class OntologyObservation(BaseModel):
    """An observation about the ontology from underwriting."""
    entity_type: str  # payer, provider, procedure, practice
    observation: str
    confidence: Optional[float] = None


class NextAction(BaseModel):
    """A recommended next action."""
    action: str
    detail: str
    priority: Optional[str] = None  # LOW, MEDIUM, HIGH


class UnderwriteClaimOutput(BaseModel):
    """Structured output from cognitive underwriting."""
    recommendation: CognitiveRecommendation
    risk_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    suggested_advance_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    suggested_max_advance_amount_cents: Optional[int] = None
    fee_rate_suggestion: Optional[float] = Field(default=None, ge=0.0, le=0.2)
    required_documents: List[str] = Field(default_factory=list)
    key_risk_factors: List[RiskFactor] = Field(default_factory=list)
    rationale_summary: str = ""
    rationale_detailed: str = ""
    policy_flags: List[PolicyFlag] = Field(default_factory=list)
    ontology_observations: List[OntologyObservation] = Field(default_factory=list)
    next_actions: List[NextAction] = Field(default_factory=list)
    model_version: str = ""
    prompt_version: str = ""


# ── Parse EOB ──────────────────────────────────────────────────────────

class ParseEobInput(BaseModel):
    """Input for EOB/ERA parsing."""
    raw_text: str
    ocr_text: Optional[str] = None
    # Optional context for claim matching
    practice_id: Optional[int] = None
    known_claim_ids: Optional[List[str]] = None
    known_payer_names: Optional[List[str]] = None


class EobClaimMatch(BaseModel):
    """A candidate claim match from EOB parsing."""
    external_claim_id: Optional[str] = None
    patient_name: Optional[str] = None
    procedure_date: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    match_method: str = ""  # e.g. "claim_id", "patient+date", "fuzzy"


class EobLineAdjudication(BaseModel):
    """Line-level adjudication data from an EOB."""
    cdt_code: Optional[str] = None
    description: Optional[str] = None
    billed_cents: Optional[int] = None
    allowed_cents: Optional[int] = None
    paid_cents: Optional[int] = None
    adjustment_cents: Optional[int] = None
    adjustment_reason_codes: List[str] = Field(default_factory=list)
    denial_code: Optional[str] = None
    denial_reason: Optional[str] = None
    remark_codes: List[str] = Field(default_factory=list)


class ParseEobOutput(BaseModel):
    """Structured output from EOB/ERA parsing."""
    # Trace / payment reference
    trace_number: Optional[str] = None
    check_number: Optional[str] = None
    payment_method: Optional[str] = None  # EFT, CHECK

    # Payer
    payer_name: Optional[str] = None
    payer_id_code: Optional[str] = None

    # Payment summary
    payment_date: Optional[str] = None
    total_paid_cents: Optional[int] = None
    total_adjustments_cents: Optional[int] = None
    total_billed_cents: Optional[int] = None

    # Claim matches
    claim_matches: List[EobClaimMatch] = Field(default_factory=list)

    # Line adjudication
    line_adjudications: List[EobLineAdjudication] = Field(default_factory=list)

    # Confidence
    overall_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    ambiguity_flags: List[str] = Field(default_factory=list)

    # Recommended actions
    recommended_action: ReconciliationAction = ReconciliationAction.MANUAL_REVIEW
    action_rationale: str = ""

    model_version: str = ""
    prompt_version: str = ""


# ── Ontology Updates ───────────────────────────────────────────────────

class OntologyUpdateInput(BaseModel):
    """Input for ontology update generation."""
    practice_id: int
    # Claim context
    claim_id: Optional[int] = None
    claim_status: Optional[str] = None
    claim_payer: Optional[str] = None
    claim_total_billed_cents: Optional[int] = None
    claim_total_paid_cents: Optional[int] = None
    claim_lines: List[ClaimLineContext] = Field(default_factory=list)

    # Funding decision context
    funding_decision: Optional[str] = None  # APPROVE/DENY/NEEDS_REVIEW
    risk_score: Optional[float] = None
    advance_rate: Optional[float] = None

    # Remittance context
    remittance_total_paid_cents: Optional[int] = None
    remittance_total_adjustments_cents: Optional[int] = None
    remittance_match_rate: Optional[float] = None
    denial_codes: Optional[List[str]] = None

    # Practice snapshot
    practice_name: Optional[str] = None
    practice_total_claims: Optional[int] = None
    practice_denial_rate: Optional[float] = None
    practice_avg_cycle_days: Optional[float] = None

    # Payer/provider/procedure context
    payer_name: Optional[str] = None
    payer_denial_rate: Optional[float] = None
    provider_name: Optional[str] = None
    procedure_codes: Optional[List[str]] = None


class EntityUpdate(BaseModel):
    """A proposed entity update."""
    entity_type: str  # payer, provider, procedure_code, practice, payer_contract
    entity_identifier: str  # name, code, or ID
    field: str
    current_value: Optional[str] = None
    proposed_value: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class KPIUpdate(BaseModel):
    """A proposed KPI update."""
    metric_name: str
    entity_type: str
    entity_identifier: str
    current_value: Optional[float] = None
    proposed_value: float
    direction: str  # INCREASE, DECREASE, STABLE
    reason: str


class RiskFlag(BaseModel):
    """A risk flag observation."""
    entity_type: str
    entity_identifier: str
    flag_type: str  # e.g. HIGH_DENIAL_RATE, SLOW_CYCLE_TIME, UNDERPAYMENT
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    detail: str
    recommended_action: Optional[str] = None


class BehaviorObservation(BaseModel):
    """An observation about entity behavior."""
    entity_type: str
    entity_identifier: str
    observation: str
    evidence: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class OntologyUpdateOutput(BaseModel):
    """Structured output from ontology update generation."""
    proposed_entity_updates: List[EntityUpdate] = Field(default_factory=list)
    proposed_kpi_updates: List[KPIUpdate] = Field(default_factory=list)
    risk_flags: List[RiskFlag] = Field(default_factory=list)
    payer_observations: List[BehaviorObservation] = Field(default_factory=list)
    procedure_observations: List[BehaviorObservation] = Field(default_factory=list)
    provider_observations: List[BehaviorObservation] = Field(default_factory=list)
    practice_observations: List[BehaviorObservation] = Field(default_factory=list)
    review_needed: bool = False
    overall_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    summary: str = ""
    model_version: str = ""
    prompt_version: str = ""


# ── Underwriting Run (for API responses) ───────────────────────────────

class UnderwritingRunResponse(BaseModel):
    """API response for an underwriting run record."""
    id: int
    claim_id: int
    model_provider: str
    model_name: str
    prompt_version: str
    input_hash: Optional[str] = None
    output_json: Optional[Dict[str, Any]] = None
    recommendation: Optional[str] = None
    risk_score: Optional[float] = None
    confidence_score: Optional[float] = None
    latency_ms: Optional[int] = None
    fallback_used: bool = False
    parse_success: bool = True
    merged_recommendation: Optional[str] = None
    deterministic_recommendation: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
