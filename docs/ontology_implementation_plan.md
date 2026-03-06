# Ontology Expansion Implementation Plan

## Audit Summary

### What Already Exists (mapped to 10 target ontology objects)

| # | Target Object | Status | Current Location | Notes |
|---|---------------|--------|-----------------|-------|
| 1 | Practice | **Partial** | `app/models/practice.py` | Has id, name, status, funding_limit_cents. Missing: legal_name, dba_name, ein, group_npi, address, pms_type, clearinghouse, owners metadata. PracticeApplication has some of these fields but is a separate onboarding model. |
| 2 | Provider | **Missing** | — | No provider model exists. Claims don't reference providers. |
| 3 | Payer | **Missing** | — | Payer is just a string field on Claim (`claim.payer`). Exists as OntologyObjectType but not a first-class table. |
| 4 | PayerContract | **Missing** | — | No contract model. |
| 5 | ProcedureCode | **Missing** | — | `procedure_codes` is a comma-separated string on Claim. No dedicated table. |
| 6 | Claim | **Partial** | `app/models/claim.py` | Has core fields. Missing: payer_id FK, provider_id FK, payer_contract_id FK, total_allowed_cents, total_paid_cents, submitted_at, adjudicated_at, source_system. |
| 7 | ClaimLine | **Missing** | — | No line-item model. |
| 8 | FundingDecision | **Partial** | `app/models/underwriting.py` as `UnderwritingDecision` | Has claim_id, decision, reasons, decided_at. Missing: advance_rate, max_advance_amount_cents, fee_rate, risk_score, model_version, policy_version, required_docs_flags. |
| 9 | PaymentIntent | **Exists** | `app/models/payment.py` | Good shape. Missing: queued_at, failed_at, funding_source_account_ref, destination_account_ref. |
| 10 | Remittance | **Missing** | — | No Remittance model. ReconciliationService uses ExternalPaymentConfirmation/ExternalBalanceSnapshot instead. |

### Supporting Objects
- **RemittanceLine**: Missing — required for reconciliation
- **FeeScheduleItem**: Missing — will add as lightweight child of PayerContract
- **LedgerEntry/LedgerAccount**: Exists — keep internal, do not expose as ontology object
- **OntologyObject/OntologyLink/KPIObservation/MetricTimeseries**: Exists — generic graph model, will be supplemented (not replaced) by first-class tables

### Current Ontology System
- Generic graph-based: OntologyObject + OntologyLink + KPIObservation + MetricTimeseries
- OntologyBuilderV2 in `services/ontology_v2.py` (1348 lines) builds ontology from Claims and Payments
- Router at `routers/ontology.py` with endpoints: context, rebuild, brief, cohorts, cfo, risks, graph, retention, reimbursement, rcm
- Frontend OntologyTab.jsx (887 lines) with CFO 360, retention, reimbursement, RCM ops, relationship explorer, brief panel

### Existing Seed Script
- `scripts/seed_ontology_demo.py`: Creates 40 claims + payments for one practice
- Limited: no providers, payers (as objects), contracts, procedure codes, remittances, claim lines

### Conflicts / Issues
1. `Claim.payer` is a string — need to add `payer_id` FK while keeping string for backward compat
2. `Claim.procedure_codes` is comma-separated — need ClaimLine + ProcedureCode tables
3. `UnderwritingDecision` partially overlaps FundingDecision — will refactor in-place (add fields, create alias)
4. `Claim.amount_cents` maps to `total_billed_cents` — will add alias/new fields

## Implementation Plan

### Keep (no changes needed)
- LedgerAccount, LedgerEntry (internal accounting subsystem)
- AuditEvent (event logging)
- ClaimDocument (document storage)
- PracticeApplication (onboarding flow)
- PracticeManagerInvite (invite flow)
- IntegrationConnection, IntegrationSyncRun (integration system)
- OpsTask, ExternalBalanceSnapshot, ExternalPaymentConfirmation (ops tooling)
- All existing routers, auth patterns, tenant isolation

### Refactor (enhance existing)
- Practice: add ontology fields (legal_name, dba_name, ein, group_npi, etc.)
- Claim: add FK columns (payer_id, provider_id, payer_contract_id), add missing fields
- UnderwritingDecision → FundingDecision: add risk_score, advance_rate, model_version, etc.
- PaymentIntent: add queued_at, failed_at, account refs
- OntologyBuilderV2: enhance to use first-class tables alongside generic graph
- seed_ontology_demo.py: replace with comprehensive synthetic data generator

### New to Add
- Provider model + service + API
- Payer model + service + API
- PayerContract model + service + API
- ProcedureCode model + service + API
- ClaimLine model + service
- Remittance + RemittanceLine models + service + API
- FeeScheduleItem model
- Synthetic data generation framework (3 practice archetypes)
- Model training pipeline (feature extraction, baseline models, evaluation)
- Enhanced ontology UI sections (7 panels)
- Comprehensive test suite

### Deferred
- Real banking rails integration
- Real ERA/835 file parsing
- Production ML model deployment
- Internal console ontology inspection pages
- Import/export tooling for synthetic datasets
- Notebook-based model analysis reports
