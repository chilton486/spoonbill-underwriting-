# Cognitive Underwriting Implementation Plan

## Phase 1: Audit Summary

### What Exists Today

**Deterministic Underwriting (keep as-is)**
- `app/underwriting.py` — Rule-based `underwrite_claim()` with `UnderwritingPolicy` dataclass: checks approved payers, excluded plan keywords, allowed procedures, pay rate thresholds, practice tenure, clean claim rate, exposure limits, pool liquidity
- `app/services/underwriting.py` — `UnderwritingService.run_underwriting()`: checks missing payer, invalid amount, duplicate fingerprint, amount thresholds; creates `UnderwritingDecision` record
- `app/services/funding.py` — `FundingDecisionService`: creates `FundingDecision` with risk-score-based rate adjustments, creates `PaymentIntent` from approved decisions
- `app/models/underwriting.py` — `UnderwritingDecision` model (claim_id, decision, reasons, decided_at, decided_by)
- `app/models/funding_decision.py` — `FundingDecision` model with risk_score, advance_rate, model_version, policy_version, reasons_json

**Claim Evaluation Flow**
- `app/routers/claims.py` — `create_claim()` endpoint: creates claim → runs `UnderwritingService.run_underwriting()` → logs audit → transitions status
- `app/state_machine.py` — Claim status transitions (NEW → NEEDS_REVIEW/APPROVED/DECLINED → PAID → COLLECTING → CLOSED)
- `app/services/audit.py` — `AuditService`: logs events, status changes, underwriting decisions to `audit_events` table

**Remittance/EOB**
- `app/services/remittance_reconciliation.py` — `RemittanceReconciliationService`: ingests remittances, reconciles by external_claim_id matching
- No existing EOB text parsing capability

**Ontology**
- `app/services/ontology_brief.py` — Uses OpenAI (gpt-4o-mini) for practice brief generation with structured JSON output and template fallback
- `app/services/ontology_crud.py` — Practice summary, payer performance, provider productivity, procedure risk, claim cycle times, reconciliation summary, funding decisions aggregation
- `app/routers/ontology_objects.py` — 15+ practice-scoped insight endpoints

**Configuration**
- `app/config.py` — `Settings` class using pydantic-settings, loads from `.env`, has `openai_api_key` already

**Internal Console UI**
- `spoonbill-frontend/src/components/ClaimDetailDialog.jsx` — Shows claim info, underwriting decisions (basic text), payment status, audit trail, status transitions
- No cognitive/AI underwriting display

### What Should Remain Deterministic
- Duplicate claim detection (fingerprint)
- Missing required fields checks
- Hard amount thresholds
- Invalid status transitions
- Payment idempotency
- Tenant scoping (practice_id isolation)
- "Must not fund" blocking rules

### What Anthropic Should Augment
- Risk scoring with contextual reasoning
- Advance rate / fee rate recommendations with rationale
- Required document identification
- EOB/remittance text parsing into structured data
- Ontology update proposals (payer behavior, procedure risk, provider patterns)
- Operator-facing explanations for review decisions

### New Schema Objects
- `UnderwritingRun` — Audit trail for LLM-assisted decisions
- Pydantic schemas: `UnderwriteClaimInput/Output`, `ParseEobInput/Output`, `OntologyUpdateInput/Output`

### Where Data Is Persisted
- `underwriting_runs` table (new Alembic migration)
- `FundingDecision.reasons_json` enriched with cognitive output
- `AuditEvent` for cognitive decision logging

### UI Surfaces Updated
- `ClaimDetailDialog` — New "Cognitive Underwriting" section with recommendation, confidence, risk factors, rationale, required docs

## Implementation Phases

### Phase 2: Anthropic Service Layer
New file: `app/services/anthropic_service.py`
- Wraps Anthropic Python SDK
- Centralized prompt templates + response parsing
- Retry/timeout/fallback handling
- Three core methods: `underwrite_claim()`, `parse_eob()`, `generate_ontology_updates()`

### Phase 3: Pydantic Schemas
New file: `app/schemas/cognitive.py`
- `UnderwriteClaimInput` (claim context, practice profile, payer metadata, procedure lines, historical signals)
- `UnderwriteClaimOutput` (recommendation, risk_score, confidence, advance_rate, risk_factors, rationale, policy_flags)
- `ParseEobInput` (raw text, claim matching context)
- `ParseEobOutput` (trace/payment data, claim matches, line adjudication, denial codes)
- `OntologyUpdateInput` (claim data, funding decisions, remittance data, ontology state)
- `OntologyUpdateOutput` (entity updates, KPI updates, risk flags, payer/procedure observations)

### Phase 4: Prompt Templates
New directory: `app/prompts/`
- `underwriting_v1.py` — Structured financial underwriting prompt
- `eob_parsing_v1.py` — EOB/ERA text parsing prompt
- `ontology_updates_v1.py` — Ontology proposal generation prompt
- Versioned, modifiable, explicit schema requirements

### Phase 5: Claim Evaluation Integration
Modified: `app/routers/claims.py`, `app/services/underwriting.py`
- Layer 1: existing deterministic rules
- Layer 2: cognitive augmentation when enabled
- Merge policy: deterministic hard-blocks override; cognitive refines scores/rationale
- Safe fallback on model failure

### Phase 6: Persistence
New model: `app/models/underwriting_run.py`
New migration: `alembic/versions/cognitive_underwriting_v1.py`
- claim_id, model_provider, model_name, prompt_version, input_hash, output_json, latency_ms, fallback_used, merged_recommendation

### Phase 7: Internal Console UI
Modified: `spoonbill-frontend/src/components/ClaimDetailDialog.jsx`
New: Cognitive Underwriting Summary section
- Recommendation + confidence badge
- Key risk factors list
- Required documentation flags
- Rationale (summary + detailed)
- Deterministic vs model comparison

### Phase 8: EOB Parsing
New endpoint: `POST /api/cognitive/parse-eob`
- Accepts raw EOB text
- Returns structured ParseEobOutput
- Integrates with existing remittance models

### Phase 9: Ontology Updates
New endpoint: `POST /api/cognitive/ontology-updates`
- Generates proposals from claim/remittance data
- Returns validated OntologyUpdateOutput
- Proposals surfaced for review, not auto-applied

### Phase 10: Configuration
Modified: `app/config.py`
- ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_ENABLED
- ANTHROPIC_TIMEOUT_SECONDS, ANTHROPIC_MAX_RETRIES, ANTHROPIC_PROMPT_VERSION
- COGNITIVE_UNDERWRITING_ENABLED, COGNITIVE_EOB_PARSING_ENABLED, COGNITIVE_ONTOLOGY_UPDATES_ENABLED

### Phase 11: Testing -- COMPLETE
New file: `tests/test_cognitive_underwriting.py` (65 tests, all passing)
- Schema validation for all input/output types (18 tests)
- Merge decision policy (10 tests covering all decision matrix combinations)
- AnthropicService with mocked responses (12 tests: hash, JSON parsing, availability, underwriting, EOB, ontology, errors)
- CognitiveUnderwritingService integration (6 tests: enable/disable, success, fallback, escalation)
- UnderwritingRun persistence and audit trail (5 tests: all run types, auto-timestamps)
- Tenant isolation for cognitive runs (1 test)
- Prompt template formatting and versioning (7 tests)
- Configuration defaults (4 tests)

### Phase 12: Documentation -- COMPLETE
Updated: `docs/cognitive_underwriting_plan.md` (this file)

---

## How to Enable Cognitive Underwriting

Set the following environment variables (`.env` or system):

```bash
# Required: Anthropic API access
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_ENABLED=true

# Feature flags (each can be toggled independently)
COGNITIVE_UNDERWRITING_ENABLED=true    # Enable cognitive claim evaluation
COGNITIVE_EOB_PARSING_ENABLED=true     # Enable EOB text parsing
COGNITIVE_ONTOLOGY_UPDATES_ENABLED=true # Enable ontology update proposals

# Optional tuning
ANTHROPIC_MODEL=claude-sonnet-4-20250514     # Default model
ANTHROPIC_TIMEOUT_SECONDS=30            # Per-call timeout
ANTHROPIC_MAX_RETRIES=2                 # Retry count
ANTHROPIC_PROMPT_VERSION=v1             # Prompt template version
```

When `COGNITIVE_UNDERWRITING_ENABLED=false` (default), the system uses deterministic underwriting only. No Anthropic calls are made.

## Decision Merge Policy

The two-layer merge follows this matrix:

| Deterministic | Model       | Final Result  | Rationale                                       |
|---------------|-------------|---------------|------------------------------------------------|
| DECLINE       | *any*       | DECLINE       | Hard blocks are always final                    |
| APPROVE       | APPROVE     | APPROVE       | Both layers agree                               |
| APPROVE       | NEEDS_REVIEW| NEEDS_REVIEW  | Model sees ambiguity, escalate                  |
| APPROVE       | DECLINE     | NEEDS_REVIEW  | Model disagrees, escalate (don't auto-decline)  |
| NEEDS_REVIEW  | APPROVE     | NEEDS_REVIEW  | Model cannot auto-approve out of review         |
| NEEDS_REVIEW  | NEEDS_REVIEW| NEEDS_REVIEW  | Both layers agree on review                     |
| NEEDS_REVIEW  | DECLINE     | DECLINE        | Both layers agree it's bad                      |
| *any*         | unavailable | deterministic | Clean fallback to rules-only                    |

**Key safety principles:**
- Model never directly triggers money movement
- Deterministic hard blocks cannot be overridden
- Model cannot auto-approve claims flagged for review
- On failure/timeout, system falls back cleanly to deterministic rules

## Audit Trail

Every cognitive call creates an `UnderwritingRun` record containing:
- `model_provider`, `model_name`, `prompt_version` -- exact model identification
- `input_hash` -- SHA-256 hash of input context for reproducibility
- `output_json` -- full structured model output
- `recommendation`, `risk_score`, `confidence_score` -- extracted decision fields
- `deterministic_recommendation`, `merged_recommendation` -- the merge result
- `latency_ms` -- API call duration
- `fallback_used`, `fallback_reason` -- whether fallback was triggered and why
- `parse_success`, `error_message` -- response validation status
- `reviewer_user_id`, `reviewer_override`, `reviewer_notes` -- human review fields

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/cognitive/status` | Check config and availability |
| GET | `/api/cognitive/runs` | List underwriting runs (filterable) |
| GET | `/api/cognitive/runs/{id}` | Get single run |
| GET | `/api/cognitive/claims/{id}/runs` | Get all runs for a claim |
| GET | `/api/cognitive/claims/{id}/cognitive-summary` | UI-formatted cognitive summary |
| POST | `/api/cognitive/parse-eob` | Parse EOB/ERA text |
| POST | `/api/cognitive/ontology-updates` | Generate ontology update proposals |
| GET | `/api/cognitive/practices/{id}/cognitive-overview` | Practice-level cognitive stats |

## Risks and Limitations

- **Not production underwriting**: This is assistive intelligence, not autonomous decision-making
- **Hallucination risk**: Model may produce plausible-sounding but incorrect assessments -- always validate against deterministic rules
- **Latency**: Anthropic API calls add 500-3000ms to claim evaluation; fallback prevents blocking
- **Cost**: Each claim evaluation, EOB parse, or ontology update is a separate API call
- **Data privacy**: Claim context is sent to Anthropic; ensure compliance with data handling policies
- **Model drift**: Prompt templates should be versioned and regularly evaluated for accuracy
