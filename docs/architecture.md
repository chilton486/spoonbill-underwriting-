# Spoonbill Architecture

This document describes the technical architecture of the Spoonbill platform -- a capital orchestration system for pre-funding insurance claims to healthcare practices.

---

## System Overview

Spoonbill is a monolithic FastAPI backend serving three single-page application (SPA) frontends. All services share a single PostgreSQL database. The system implements multi-tenant isolation, a double-entry ledger, a rules-based underwriting engine, and a strict claim state machine.

```
+------------------------------------------------------------------+
|                        Render Platform                            |
|                                                                   |
|  +--------------------+   +------------------+                    |
|  | spoonbill-api      |   | spoonbill-db     |                   |
|  | (Python/FastAPI)   |<->| (PostgreSQL 15)  |                   |
|  | Port: $PORT        |   | Managed instance |                   |
|  +--------------------+   +------------------+                    |
|          ^                                                        |
|          | REST/JSON                                              |
|          |                                                        |
|  +-------+--------+----------+                                    |
|  |                |          |                                    |
|  v                v          v                                    |
|  +-----------+ +---------+ +---------+                            |
|  | Console   | | Portal  | | Intake  |                            |
|  | (Static)  | | (Static)| | (Static)|                            |
|  +-----------+ +---------+ +---------+                            |
+------------------------------------------------------------------+
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend framework | FastAPI (Python 3.11) |
| ORM | SQLAlchemy 2.x (declarative base) |
| Database | PostgreSQL 15 |
| Migrations | Alembic |
| Authentication | JWT (HS256) via python-jose |
| Password hashing | bcrypt via passlib |
| Frontend framework | React 18 + Material UI 5 |
| Frontend build | Vite |
| Deployment | Render (Blueprint) |
| Containerization | Docker (python:3.11-slim) |

---

## Service Boundaries

The backend is a single deployable unit, but internally organized into clear service boundaries:

### Router Layer (`app/routers/`)

Routes are organized by audience and domain:

| Router | Prefix | Audience | Purpose |
|--------|--------|----------|---------|
| `auth.py` | `/auth` | All | Login, token issuance, current user |
| `claims.py` | `/api/claims` | Spoonbill ops | Internal claim management |
| `practice.py` | `/practice` | Practice managers | Practice-facing claim + document + dashboard |
| `payments.py` | `/api/payments` | Spoonbill ops | Payment orchestration + ledger |
| `applications.py` | `/apply`, `/internal/applications`, `/invite` | Public + Spoonbill ops | Intake + review + invite |
| `users.py` | `/api/users` | Spoonbill admins | User and practice CRUD |
| `internal_practices.py` | `/api/practices` | Spoonbill ops | Practice detail + invite management |
| `ontology.py` | `/practices/{id}/ontology` | Practice managers | Financial analytics |
| `integrations.py` | `/practice/integrations` | Practice managers + Spoonbill | External data sync |
| `ops.py` | `/ops` | Spoonbill ops | Economics, reconciliation, tasks, playbooks |

### Service Layer (`app/services/`)

Business logic is extracted into service modules, keeping routers thin:

| Service | Responsibility |
|---------|---------------|
| `auth.py` | JWT creation/validation, password hashing |
| `underwriting.py` | Rule evaluation, duplicate detection, decision recording |
| `payments.py` | PaymentIntent lifecycle, provider dispatch |
| `ledger.py` | Account creation, double-entry posting, balance queries |
| `audit.py` | Immutable event logging |
| `ontology.py` / `ontology_v2.py` | Claims data -> ontology objects, links, KPIs |
| `ontology_brief.py` | Deterministic + LLM-assisted financial briefs |
| `economics.py` | Liquidity, exposure, and capital analytics |
| `control_tower.py` | Aggregated operational dashboard |
| `reconciliation.py` | External balance ingestion, mismatch resolution |
| `ingestion.py` | External claim data normalization and import |
| `underwriting_score.py` | Application risk scoring |
| `action_proposals.py` | Automated operational action generation |
| `playbooks.py` | Templated operational workflows |
| `email.py` | SendGrid email dispatch |
| `rate_limiter.py` | IP-based rate limiting with in-memory store |

### Provider Layer (`app/providers/`)

Payment execution is abstracted behind a provider interface:

```
BasePaymentProvider (abstract)
    |
    +-- SimulatedPaymentProvider (stub, always succeeds)
    |
    +-- [Future: FedNowProvider, ACHProvider]
```

The `SimulatedPaymentProvider` generates fake provider references and always returns success. This allows the full payment lifecycle to be exercised without real banking integration.

---

## Authentication & Authorization

### JWT Flow

```
Client                  Backend
  |                       |
  |-- POST /auth/login -->|
  |   {email, password}   |
  |                       |-- verify password (bcrypt)
  |                       |-- generate JWT (HS256)
  |<-- {access_token} ----|
  |                       |
  |-- GET /api/claims --->|
  |   Authorization:      |
  |   Bearer <token>      |
  |                       |-- decode JWT
  |                       |-- load User from DB
  |                       |-- check role
  |<-- [claims] ----------|
```

### Role-Based Access Control

Authorization is enforced via FastAPI dependency injection:

| Dependency | Allows |
|------------|--------|
| `require_auth` | Any authenticated user |
| `require_spoonbill_admin` | `SPOONBILL_ADMIN` only |
| `require_spoonbill_user` | `SPOONBILL_ADMIN` or `SPOONBILL_OPS` |
| `require_practice_manager` | `PRACTICE_MANAGER` only |

Practice managers are scoped to their own practice via `practice_id` stored in the JWT payload. This is the only source of truth for tenant identity -- it is never accepted from client request payloads.

### Rate Limiting

- Login: 10 requests per 5 minutes per IP
- Intake submission: 5 requests per hour per IP
- Implemented via in-memory dictionary with timestamp tracking (`app/services/rate_limiter.py`)

---

## Multi-Tenant Architecture

### Tenant Isolation Model

Every `PRACTICE_MANAGER` user belongs to exactly one practice. The `practice_id` is embedded in the JWT at login time and extracted server-side on every request.

```
JWT Token
  |
  +-- user_id
  +-- email
  +-- role
  +-- practice_id  <-- tenant boundary
```

### Data Scoping

All queries for practice-scoped resources include `practice_id` as a mandatory filter:

```python
# Example: fetching claims for the current practice
query = select(Claim).where(
    Claim.practice_id == current_user.practice_id,
    Claim.id == claim_id
)
```

### Information Hiding

When a `PRACTICE_MANAGER` attempts to access a resource from another practice, the system returns HTTP 404 (not 403). This prevents:
- Enumeration attacks (testing if a resource exists in another tenant)
- Information leakage about other practices

### Spoonbill User Access

`SPOONBILL_ADMIN` and `SPOONBILL_OPS` users have cross-practice visibility. They can view and manage claims, payments, and practices across all tenants. Their `practice_id` is `None`.

---

## Claim Lifecycle

### State Machine

The claim state machine is defined in `app/models/claim.py` and enforced by `app/state_machine.py`. Every transition is validated against an allowlist:

```
                                    +---> DECLINED (terminal)
                                    |
NEW ----> NEEDS_REVIEW ----> APPROVED ----> PAID ----> COLLECTING ----> CLOSED (terminal)
 |              |               |
 +--------------+               +---> PAYMENT_EXCEPTION
                |                          |
                +---> DECLINED             +---> APPROVED (retry)
                     (terminal)            +---> DECLINED (cancel)
```

### Transition Rules

```python
CLAIM_STATUS_TRANSITIONS = {
    ClaimStatus.NEW:               {NEEDS_REVIEW, APPROVED, DECLINED},
    ClaimStatus.NEEDS_REVIEW:      {APPROVED, DECLINED},
    ClaimStatus.APPROVED:          {PAID, DECLINED, PAYMENT_EXCEPTION},
    ClaimStatus.PAID:              {COLLECTING},
    ClaimStatus.COLLECTING:        {CLOSED},
    ClaimStatus.CLOSED:            frozenset(),   # terminal
    ClaimStatus.DECLINED:          frozenset(),   # terminal
    ClaimStatus.PAYMENT_EXCEPTION: {APPROVED, DECLINED},
}
```

### Underwriting Engine

When a claim is created, the underwriting engine (`app/services/underwriting.py`) evaluates it synchronously:

```
Claim submitted
    |
    v
[1] Missing payer or amount? ----yes----> NEEDS_REVIEW
    |no
    v
[2] Duplicate fingerprint? ------yes----> DECLINED
    |no
    v
[3] Amount > threshold? ---------yes----> NEEDS_REVIEW
    |no
    v
[4] Amount < auto-approve? ------yes----> APPROVED
    |no
    v
[5] Default --------------------------> APPROVED
```

**Duplicate detection** uses a fingerprint hash of: `practice_id + patient_first + patient_last + procedure_date + amount_cents + payer_name`.

### Audit Trail

Every claim state change creates an `AuditEvent` with:
- `event_type`: e.g., `CLAIM_STATUS_CHANGED`
- `claim_id`: the affected claim
- `user_id`: who made the change
- `details`: JSON with old_status, new_status, and context

---

## Payment & Ledger System

### Double-Entry Ledger

The ledger implements double-entry accounting with three account types:

| Account | Normal Balance | Purpose |
|---------|---------------|---------|
| `CAPITAL_CASH` | Debit | Spoonbill's available capital pool |
| `PAYMENT_CLEARING` | Credit | In-flight payments awaiting confirmation |
| `PRACTICE_PAYABLE` | Credit | Amounts owed to practices |

Every financial event creates a pair of entries (debit + credit) that sum to zero.

### Payment Flow

```
1. Claim reaches APPROVED status
   |
   v
2. PaymentIntent created (status: QUEUED)
   - idempotency_key = "claim:{id}:payment:v1"
   - One PaymentIntent per claim (UNIQUE constraint)
   |
   v
3. Ledger reservation
   - DEBIT  CAPITAL_CASH      (reduce available capital)
   - CREDIT PAYMENT_CLEARING   (reserve for in-flight payment)
   |
   v
4. Payment provider dispatch
   - SimulatedPaymentProvider.send()
   - PaymentIntent status -> SENT
   - provider_reference stored
   |
   v
5a. Confirmation (success path)           5b. Failure path
   - PaymentIntent status -> CONFIRMED       - PaymentIntent status -> FAILED
   - DEBIT  PAYMENT_CLEARING                 - Reversal entries posted
   - CREDIT PRACTICE_PAYABLE                 - Claim -> PAYMENT_EXCEPTION
   - Claim -> PAID
```

### Idempotency

Multiple layers prevent double-processing:

1. **PaymentIntent uniqueness**: `claim_id` has a UNIQUE constraint -- only one payment per claim
2. **Idempotency keys**: Each PaymentIntent has a deterministic idempotency key (`claim:{id}:payment:v1`)
3. **Ledger entry keys**: Each ledger entry has a unique idempotency key to prevent double-posting
4. **Retry safety**: Retry operations check existing payment state before creating new entries

### Capital Management

Capital is seeded into the system via `POST /api/payments/ledger/seed`:
- Creates a `CAPITAL_CASH` account (or uses existing)
- Posts a debit entry to increase available capital
- This is the source of all funds for claim pre-funding

The `GET /api/payments/ledger/summary` endpoint returns current balances across all accounts, enabling real-time liquidity monitoring.

---

## Data Model

### Entity Relationship Diagram

```
+-------------------+       +-------------------+       +-------------------+
| Practice          |       | User              |       | PracticeApplication|
|-------------------|       |-------------------|       |-------------------|
| id (PK)           |<------| practice_id (FK)  |       | id (PK)           |
| name              |       | email             |       | legal_name        |
| status            |       | role              |       | status            |
| funding_limit     |       | hashed_password   |       | underwriting_score|
| created_at        |       | is_active         |       | review_notes      |
+-------------------+       +-------------------+       +-------------------+
        |                          |                           |
        |                          v                           | (on approval)
        |                   +--------------+                   v
        |                   | PracticeMgr  |            Creates Practice
        |                   | Invite       |            + User + Invite
        |                   |--------------|
        |                   | token        |
        |                   | expires_at   |
        |                   | used         |
        |                   +--------------+
        |
        +------< Claim >------+
        |  | id (PK)          |
        |  | claim_token      |
        |  | patient_first    |
        |  | patient_last     |
        |  | payer_name       |
        |  | amount_cents     |
        |  | status           |
        |  | fingerprint_hash |
        |  +------------------+
        |        |    |    |
        |        |    |    +------< ClaimDocument
        |        |    |              | filename
        |        |    |              | file_path
        |        |    |
        |        |    +------< UnderwritingDecision
        |        |              | decision (APPROVE/DECLINE/NEEDS_REVIEW)
        |        |              | reasons (JSON)
        |        |
        |        +------< AuditEvent
        |        |          | event_type
        |        |          | details (JSON)
        |        |
        |        +------- PaymentIntent (one-to-one)
        |                    | status (QUEUED/SENT/CONFIRMED/FAILED)
        |                    | idempotency_key
        |                    | provider_reference
        |                    | amount_cents
        |
        +------< LedgerAccount
        |          | account_type (CAPITAL_CASH/PAYMENT_CLEARING/PRACTICE_PAYABLE)
        |          | currency
        |          |
        |          +------< LedgerEntry
        |                    | direction (DEBIT/CREDIT)
        |                    | amount_cents
        |                    | status (PENDING/POSTED/REVERSED)
        |                    | idempotency_key
        |
        +------< IntegrationConnection
                   | provider (OPEN_DENTAL)
                   | status
                   | sync_cursor
                   |
                   +------< IntegrationSyncRun
                              | status (RUNNING/SUCCEEDED/FAILED)
                              | claims_created
                              | errors
```

### Key Design Decisions

1. **UUIDs as primary keys**: All entities use UUID primary keys for security (non-enumerable) and distributed system readiness.

2. **Claim tokens**: Human-readable identifiers (`SB-CLM-XXXXXXXX`) separate from UUIDs. Used in UI and communications. Generated from base32 encoding, immutable after creation.

3. **Fingerprint hashing**: Claims are fingerprinted (SHA-256 of key fields) for duplicate detection. This allows O(1) duplicate checks via database index.

4. **JSONB for flexible data**: Audit event details, underwriting reasons, and application data use JSONB columns for schema flexibility.

5. **Soft delete pattern**: Users have an `is_active` flag rather than being deleted. Practices have `ACTIVE`/`INACTIVE` status.

---

## Event Flow

### Claim Creation -> Payment

```
[Practice Portal]                [Backend]                    [Database]
      |                             |                             |
      |-- POST /practice/claims --> |                             |
      |                             |-- INSERT Claim (NEW)------> |
      |                             |-- Run underwriting -------> |
      |                             |   |                         |
      |                             |   +-- INSERT Decision ----> |
      |                             |   +-- INSERT AuditEvent --> |
      |                             |   |                         |
      |                             |   [if APPROVED]             |
      |                             |   +-- UPDATE Claim status-> |
      |                             |   +-- INSERT PaymentIntent> |
      |                             |   +-- INSERT AuditEvent --> |
      |                             |                             |
      |<-- {claim, decision} -------|                             |
```

### Payment Processing

```
[Internal Console]              [Backend]                    [Database]
      |                             |                             |
      |-- POST /api/payments/    -->|                             |
      |   process {claim_id}        |                             |
      |                             |-- Load PaymentIntent -----> |
      |                             |-- Create LedgerEntries ---> |
      |                             |   (CAPITAL_CASH debit)      |
      |                             |   (PAYMENT_CLEARING credit) |
      |                             |-- Call PaymentProvider ---> |
      |                             |   SimulatedProvider.send()  |
      |                             |-- UPDATE PaymentIntent ---> |
      |                             |   status = SENT             |
      |                             |-- [on confirm]              |
      |                             |   Create LedgerEntries ---> |
      |                             |   (CLEARING debit)          |
      |                             |   (PAYABLE credit)          |
      |                             |   UPDATE Claim -> PAID ---> |
      |                             |   INSERT AuditEvent ------> |
      |<-- {payment, entries} ------|                             |
```

### Practice Onboarding

```
[Intake Portal]    [Backend]              [Internal Console]    [Practice Portal]
      |                |                         |                      |
      |-- POST /apply->|                         |                      |
      |                |-- INSERT Application -->|                      |
      |                |-- Compute score ------->|                      |
      |                |                         |                      |
      |                |<--- GET /internal/ -----|                      |
      |                |     applications        |                      |
      |                |                         |                      |
      |                |<--- POST review --------|                      |
      |                |     {action: APPROVE}   |                      |
      |                |                         |                      |
      |                |-- CREATE Practice ----->|                      |
      |                |-- CREATE User --------->|                      |
      |                |-- CREATE Invite ------->|                      |
      |                |-- [generate invite URL] |                      |
      |                |                         |                      |
      |                |                         |-- Copy invite URL -->|
      |                |                         |                      |
      |                |<--------- GET /invite/validate/{token} -------|
      |                |<--------- POST /invite/set-password ----------|
      |                |-- Mark invite used ---->|                      |
      |                |                         |                      |
      |                |<--------- POST /auth/login -------------------|
      |                |-- Return JWT ---------->|                      |
```

---

## Financial Ontology (Phase 2)

The ontology system provides CFO-grade analytics for practice managers, built from claims data.

### Architecture

```
Claims Data
    |
    v
OntologyBuilder (app/services/ontology_v2.py)
    |
    +-- Creates OntologyObjects (Practice, Claim, Payer, Procedure, Patient)
    +-- Creates OntologyLinks (relationships between objects)
    +-- Computes KPIs (metrics traceable to objects)
    |
    v
Ontology Endpoints
    |
    +-- /context    -> Full snapshot with totals, mixes, cohorts, risks
    +-- /cfo        -> CFO 360 view (capital, revenue, payer risk, growth)
    +-- /cohorts    -> Time-series, rolling windows, aging buckets
    +-- /risks      -> Deterministic risk signals with severity
    +-- /graph      -> Node/edge projection for visualization
    +-- /brief      -> AI-assisted or deterministic financial narrative
    +-- /retention  -> Patient retention and repeat visit metrics
    +-- /reimbursement -> Reimbursement rate and lag analysis
    +-- /rcm        -> Revenue cycle management operations
```

### Privacy Model

- Patient objects use a stable `patient_hash` (SHA-256 of first + last name) instead of PII
- No PHI is exposed through ontology endpoints
- All views are projections of aggregated, de-identified data

---

## Integration Architecture

### Open Dental

Two ingestion modes:

1. **CSV Upload** (Practice Portal):
   - Practice manager uploads claims CSV + optional line items CSV
   - `csv_parser.py` parses and validates rows
   - `ingestion.py` normalizes data and creates claims
   - Duplicate detection via fingerprint hash

2. **API Sync** (Spoonbill-triggered):
   - Requires `IntegrationConnection` with API key and endpoint
   - Pulls claims since last sync cursor
   - Creates `IntegrationSyncRun` to track progress
   - Status: `RUNNING` -> `SUCCEEDED` / `FAILED`

### External Reconciliation

The ops reconciliation system (`app/services/reconciliation.py`) handles:

1. **Balance ingestion**: External balance snapshots are ingested from banking/payer systems
2. **Mismatch detection**: Compares external balances against internal ledger
3. **Resolution workflow**: Ops can resolve mismatches via the reconciliation endpoints

---

## Ops & Monitoring

### Economics Dashboard

The economics service (`app/services/economics.py`) provides real-time financial metrics:

- **Liquidity summary**: Available capital, reserved amounts, total exposure
- **Exposure breakdown**: By practice, by status, by age
- **Payment intent board**: All active payment intents with status
- **Exception tracking**: Failed payments and claims in exception state

### Control Tower

The control tower (`app/services/control_tower.py`) aggregates operational metrics:

- Active practices count
- Claims by status distribution
- Payment success/failure rates
- Exposure concentration
- Average processing times

### Playbooks

Operational playbooks (`app/services/playbooks.py`) automate common workflows:

| Playbook | Trigger | Actions |
|----------|---------|---------|
| `PAYMENT_FAILED` | Payment failure | Create ops task, notify, suggest retry |
| `INTEGRATION_SYNC_FAILED` | Sync failure | Create ops task, log error details |
| `CLAIM_MISSING_INFO` | Incomplete claim | Create ops task, flag for review |
| `DENIAL_SPIKE` | Unusual denial rate | Create ops task, alert team |

### Action Proposals

The action proposal system (`app/services/action_proposals.py`) can:
- **Generate** proposals based on current system state
- **Validate** that a proposal is safe to execute
- **Simulate** the effect of a proposal without execution
- **Execute** approved proposals

---

## Database & Migration Strategy

### Migration Process

Alembic manages all schema changes:

1. Developer modifies SQLAlchemy models in `app/models/`
2. Run `alembic revision --autogenerate -m "description"` to generate migration
3. Review generated migration in `alembic/versions/`
4. Apply with `alembic upgrade head`

### Auto-Migration on Startup

For deployed environments, `RUN_MIGRATIONS_ON_STARTUP=true` triggers automatic migration:

```python
# app/utils/migrations.py
1. Acquire PostgreSQL advisory lock (key: 9142026)
2. Run alembic.command.upgrade("head")
3. Release lock
4. If failure: sys.exit(1) -> Render restarts the service
```

The advisory lock prevents race conditions when multiple instances start simultaneously.

### Connection Management

- SQLAlchemy `create_engine` with default connection pooling
- Session-per-request pattern via FastAPI dependency injection
- `get_db()` yields a session and ensures cleanup

---

## Scaling Considerations

### Current Architecture

The system is designed as a monolith suitable for early-stage scaling:

- **Single backend process**: All request handling in one FastAPI instance
- **Single database**: All data in one PostgreSQL instance
- **Stateless backend**: No server-side session state; JWT tokens are self-contained
- **In-memory rate limiting**: Rate limit counters are per-process (not distributed)

### Scaling Path

| Phase | Action | Trigger |
|-------|--------|---------|
| **Horizontal API** | Run multiple Uvicorn workers behind load balancer | >100 concurrent users |
| **Distributed rate limiting** | Move rate limiter to Redis | Multiple API instances |
| **Read replicas** | PostgreSQL read replicas for analytics queries | Heavy ontology/reporting load |
| **Background workers** | Extract payment processing and ontology rebuilds to async workers (Celery/RQ) | Payment provider latency, long ontology computations |
| **Event bus** | Replace synchronous audit logging with async event bus (e.g., SQS/Kafka) | High write throughput |
| **Service extraction** | Extract payment orchestration and ontology into separate services | Team growth, independent scaling needs |
| **Real banking** | Replace SimulatedPaymentProvider with FedNow/ACH providers | Production launch |

### Performance Notes

- Fingerprint-based duplicate detection is O(1) via database index
- Ontology rebuild processes all practice claims in-memory; may need pagination for large practices
- Ledger balance queries aggregate entries; consider materialized views for high-frequency reads
- Advisory lock for migrations adds ~0ms overhead for normal requests (only runs on startup)

---

## Security Model

### Defense in Depth

| Layer | Mechanism |
|-------|-----------|
| Transport | HTTPS (Render-managed TLS) |
| Authentication | JWT with HS256 signing, bcrypt password hashing |
| Authorization | Role-based access control via FastAPI dependencies |
| Tenant isolation | JWT-derived practice_id, query-level scoping |
| Information hiding | 404 instead of 403 for cross-tenant access |
| Input validation | Pydantic schemas on all endpoints |
| Rate limiting | IP-based limits on login and public endpoints |
| Bot protection | Honeypot field on intake form |
| Invite security | Single-use, time-limited (7-day), 64-char random tokens |
| Audit trail | Immutable AuditEvent log for all significant actions |
| CORS | Environment-driven allowlist, no wildcard origins |

### Secrets Management

- `JWT_SECRET_KEY`: Used for token signing. Must be rotated periodically.
- `ADMIN_EMAIL` / `ADMIN_PASSWORD`: Used only for initial seed. Should be changed after first login.
- `SENDGRID_API_KEY`, `OPENAI_API_KEY`: Optional service credentials.
- All secrets are configured via environment variables, never committed to code.
