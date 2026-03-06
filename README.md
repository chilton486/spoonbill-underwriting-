# Spoonbill

Capital orchestration platform for pre-funding insurance claims. Spoonbill advances payments to healthcare practices before insurance reimbursement arrives, bridging the gap between claim submission and payer settlement.

## Project Overview

### Problem

Healthcare practices submit insurance claims and wait 30-90 days for reimbursement. This creates cash flow pressure that limits growth, delays payroll, and forces practices into expensive credit lines.

### Solution

Spoonbill underwrites and pre-funds approved claims, then collects directly from payers -- turning receivables into same-day capital.

### How It Works

1. A practice submits a claim through the Practice Portal or via integration (CSV upload / Open Dental API).
2. The underwriting engine evaluates the claim automatically (duplicate check, amount thresholds, payer validation).
3. Approved claims generate a `PaymentIntent`, which reserves capital in the double-entry ledger.
4. Funds are sent to the practice. The ledger records every financial event as paired DEBIT/CREDIT entries.
5. Spoonbill collects from the insurance payer and reconciles the claim to close it out.

---

## System Architecture

```
                    +---------------------------+
                    |      FastAPI Backend       |
                    |  PostgreSQL + Alembic      |
                    |  JWT Auth + Multi-Tenant   |
                    |  PaymentIntent + Ledger    |
                    +---------------------------+
                     /           |            \
          +-----------+  +-----------+  +-----------+
          |  Internal |  | Practice  |  |  Intake   |
          |  Console  |  |  Portal   |  |  Portal   |
          +-----------+  +-----------+  +-----------+
          Spoonbill Ops  Practice Mgr   Public App
```

**Backend** -- FastAPI (Python 3.11), PostgreSQL, Alembic migrations, JWT authentication, multi-tenant enforcement, double-entry ledger, rules-based underwriting engine, payment orchestration.

**Internal Console** -- React + Material UI SPA. Used by Spoonbill operators for claims management, underwriting review, practice administration, payment processing, reconciliation, economics monitoring, and audit trail inspection.

**Practice Portal** -- React + Material UI SPA. Used by practice managers to submit claims, upload documents, track claim/payment status, and view financial analytics (ontology). Uses HashRouter for static hosting compatibility.

**Intake Portal** -- React + Material UI SPA. Public-facing application form for practice onboarding. No authentication required.

### Data Flow

```
Practice Portal / CSV Upload / Open Dental API
        |
        v
   Claim Created (NEW)
        |
        v
   Underwriting Engine (auto-evaluate)
        |
   +----+----+
   |         |
   v         v
APPROVED   NEEDS_REVIEW / DECLINED
   |
   v
PaymentIntent (QUEUED)
   |
   v
Ledger Reserve (CAPITAL_CASH -> PAYMENT_CLEARING)
   |
   v
Payment Sent (SENT -> CONFIRMED)
   |
   v
Ledger Confirm (PAYMENT_CLEARING -> PRACTICE_PAYABLE)
   |
   v
Claim -> PAID -> COLLECTING -> CLOSED
```

> See [docs/architecture.md](docs/architecture.md) for detailed architecture, service boundaries, event flows, and scaling considerations.

---

## Core Data Model

| Object | Purpose |
|--------|---------|
| **Practice** | A healthcare practice enrolled on the platform. Has a name, status (`ACTIVE`/`INACTIVE`), and optional funding limit. All claims, users, and ledger accounts are scoped to a practice. |
| **User** | An authenticated user with a role (`SPOONBILL_ADMIN`, `SPOONBILL_OPS`, or `PRACTICE_MANAGER`). Practice managers are scoped to a single practice via `practice_id`. |
| **Claim** | An insurance claim submitted by a practice. Contains patient name, payer, amount, procedure date, and a unique `claim_token` (format: `SB-CLM-XXXXXXXX`). Tracks status through a state machine. |
| **UnderwritingDecision** | A record of an underwriting evaluation (`APPROVE`, `DECLINE`, `NEEDS_REVIEW`) with reasons, linked to a claim. |
| **PaymentIntent** | Represents a payment to a practice for an approved claim. One-to-one with claim. Tracks status (`QUEUED` -> `SENT` -> `CONFIRMED`/`FAILED`) with an idempotency key. |
| **LedgerAccount** | A named account in the double-entry ledger (`CAPITAL_CASH`, `PAYMENT_CLEARING`, or `PRACTICE_PAYABLE`). Scoped by practice and currency. |
| **LedgerEntry** | A single debit or credit entry in the ledger. Always created in pairs that sum to zero. Has an idempotency key to prevent double-posting. |
| **AuditEvent** | An immutable log entry recording any significant action (status changes, underwriting decisions, payments, user creation). |
| **PracticeApplication** | An intake application submitted by a prospective practice. Contains practice, financial, and billing information. Reviewed by ops. |
| **PracticeManagerInvite** | A single-use, time-limited (7-day) token for a practice manager to set their password after approval. |
| **ClaimDocument** | A file uploaded against a claim (stored on disk at `/data/uploads`). |
| **IntegrationConnection** | Configuration for an external data integration (currently Open Dental). Tracks sync status and cursor. |
| **OpsTask** | An operational task generated by playbooks or manually created. Tracks status, priority, and SLA. |

### Relationships

```
Practice --< User
Practice --< Claim --< UnderwritingDecision
                   --< AuditEvent
                   --< ClaimDocument
                   --- PaymentIntent (one-to-one)
                   --< LedgerEntry
Practice --< LedgerAccount --< LedgerEntry
Practice --< IntegrationConnection --< IntegrationSyncRun
PracticeApplication --> Practice (created on approval)
User --< PracticeManagerInvite
```

---

## Claim Lifecycle

Claims follow a strict state machine with validated transitions:

```
NEW --> NEEDS_REVIEW --> APPROVED --> PAID --> COLLECTING --> CLOSED
 |          |              |
 +----------+--------------+---> DECLINED (terminal)
                           |
                           +---> PAYMENT_EXCEPTION --> APPROVED (retry)
                                                   --> DECLINED (cancel)
```

| Status | Description |
|--------|-------------|
| `NEW` | Claim created; underwriting rules evaluate automatically |
| `NEEDS_REVIEW` | Flagged for manual ops review (missing data, high amount) |
| `APPROVED` | Underwriting passed; PaymentIntent created |
| `PAID` | Payment confirmed; funds sent to practice |
| `COLLECTING` | Collecting reimbursement from insurance payer |
| `CLOSED` | Claim fully resolved (terminal) |
| `DECLINED` | Rejected (terminal) |
| `PAYMENT_EXCEPTION` | Payment failed; can be retried or cancelled |

### Underwriting Rules

Executed automatically on claim creation:

1. Missing payer or amount -> `NEEDS_REVIEW`
2. Duplicate fingerprint (practice_id + patient + date + amount + payer) -> `DECLINED`
3. Amount > `UNDERWRITING_AMOUNT_THRESHOLD_CENTS` -> `NEEDS_REVIEW`
4. Amount < `UNDERWRITING_AUTO_APPROVE_BELOW_CENTS` -> `APPROVED`
5. Otherwise -> `APPROVED`

### Payments

Double-entry accounting with three ledger accounts:

| Account | Purpose |
|---------|---------|
| `CAPITAL_CASH` | Spoonbill's available capital |
| `PAYMENT_CLEARING` | In-flight payments awaiting confirmation |
| `PRACTICE_PAYABLE` | Amounts owed to practices |

Every financial event creates paired DEBIT/CREDIT entries that sum to zero.

**Payment flow:**

```
Claim APPROVED
  --> PaymentIntent created (QUEUED)
  --> Reserve: CAPITAL_CASH debit, PAYMENT_CLEARING credit
  --> Send: PaymentIntent status --> SENT
  --> Confirm: PAYMENT_CLEARING debit, PRACTICE_PAYABLE credit, Claim --> PAID
  --> (Failure path): Reversal entries posted, payment_exception flag set
```

**Idempotency:**
- One PaymentIntent per claim (UNIQUE constraint on `claim_id`)
- Deterministic idempotency key: `claim:{claim_id}:payment:v1`
- Ledger entries have unique idempotency keys to prevent double-posting

---

## Repository Structure

```
spoonbill-underwriting-/
  app/
    main.py                       # FastAPI entry point, CORS, lifespan
    config.py                     # Pydantic settings (all env vars)
    database.py                   # SQLAlchemy engine, session factory
    state_machine.py              # Claim status transition validator
    cli.py                        # CLI commands (seed admin user)
    underwriting.py               # Standalone underwriting policy engine
    ledger.py                     # Standalone ledger funding/settlement
    models/                       # SQLAlchemy ORM models
      claim.py                    #   Claim, ClaimStatus, transitions
      user.py                     #   User, UserRole
      practice.py                 #   Practice, PracticeStatus
      payment.py                  #   PaymentIntent, PaymentIntentStatus
      ledger.py                   #   LedgerAccount, LedgerEntry
      audit.py                    #   AuditEvent
      underwriting.py             #   UnderwritingDecision
      practice_application.py     #   PracticeApplication (intake)
      invite.py                   #   PracticeManagerInvite
      document.py                 #   ClaimDocument
      ontology.py                 #   OntologyObject, OntologyLink, KPI
      integration.py              #   IntegrationConnection, SyncRun
      ops.py                      #   OpsTask, ExternalBalanceSnapshot
    routers/                      # API route handlers
      auth.py                     #   Login, JWT, role guards
      claims.py                   #   Internal claim CRUD + transitions
      practice.py                 #   Practice Portal endpoints
      payments.py                 #   Payment processing + ledger
      applications.py             #   Intake submission + ops review
      users.py                    #   User/practice management (admin)
      internal_practices.py       #   Practice list, detail, invite mgmt
      ontology.py                 #   Financial ontology endpoints
      integrations.py             #   Open Dental sync + CSV upload
      ops.py                      #   Economics, control tower, tasks
    schemas/                      # Pydantic request/response schemas
    services/                     # Business logic layer
      auth.py                     #   JWT creation, password hashing
      underwriting.py             #   Underwriting rule evaluation
      payments.py                 #   Payment orchestration
      ledger.py                   #   Ledger account/entry management
      audit.py                    #   Audit event logging
      ontology.py, ontology_v2.py #   Financial ontology builder
      ontology_brief.py           #   AI-assisted ontology briefs
      economics.py                #   Liquidity & exposure analytics
      control_tower.py            #   Ops control tower dashboard
      reconciliation.py           #   Payment reconciliation
      ingestion.py                #   External claim ingestion
      underwriting_score.py       #   Application scoring
      action_proposals.py         #   Automated action proposals
      playbooks.py                #   Ops playbook runner
      email.py                    #   SendGrid email service
      rate_limiter.py             #   IP-based rate limiting
      cdt_families.py             #   CDT procedure code families
    integrations/                 # External system connectors
      csv_parser.py               #   Claims/lines CSV parsing
      open_dental/                #   Open Dental API connector
    providers/                    # Payment provider abstractions
      base.py                     #   Base payment provider interface
      simulated.py                #   Simulated payment provider (stub)
    utils/
      migrations.py               #   Auto-migration on startup
  alembic/                        # Database migration scripts
    versions/                     #   Individual migration files
    env.py                        #   Alembic environment config
  tests/                          # pytest test suite
    test_payments.py              #   Payment lifecycle tests
    test_tenant_isolation.py      #   Multi-tenant security tests
    test_underwriting.py          #   Underwriting rule tests
    test_applications.py          #   Application + invite tests
    test_state_machine.py         #   Status transition tests
    test_integrations.py          #   Integration sync tests
    test_ontology.py              #   Ontology builder tests
    test_economics.py             #   Economics service tests
    test_control_tower.py         #   Control tower tests
    test_intake_scoring.py        #   Application scoring tests
    test_crm_edit.py              #   CRM edit tests
  spoonbill-frontend/             # Internal Console (React + Vite + MUI)
  spoonbill-practice-frontend/    # Practice Portal (React + Vite + MUI)
  spoonbill-intake-frontend/      # Intake Portal (React + Vite + MUI)
  shared-ui/                      # Shared CSS and theme config
  scripts/
    start.sh                      # Production start script
    seed_ontology_demo.py         # Ontology demo data seeder
  docs/
    integration_templates/        # Integration configuration templates
  docker-compose.yml              # Local PostgreSQL container
  Dockerfile                      # Backend Docker image
  render.yaml                     # Render deployment blueprint
  requirements.txt                # Python dependencies
  runtime.txt                     # Python version (3.11.9)
  .env.example                    # Environment variable template
```

---

## API Overview

### Authentication (`/auth`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/login` | None | Login with email/password, returns JWT |
| GET | `/auth/me` | JWT | Get current user profile |

**Roles:**

| Role | Scope |
|------|-------|
| `SPOONBILL_ADMIN` | Full system access: users, practices, claims, payments |
| `SPOONBILL_OPS` | Claims, underwriting, status transitions, practice management |
| `PRACTICE_MANAGER` | Own practice only: claims, documents, status viewing, ontology |

### Claims - Internal (`/api/claims`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/claims` | Spoonbill | Create a claim (triggers underwriting) |
| GET | `/api/claims` | Spoonbill | List claims (filter by status, practice, search) |
| GET | `/api/claims/{id}` | Spoonbill | Get claim detail |
| PATCH | `/api/claims/{id}` | Spoonbill | Update claim fields |
| POST | `/api/claims/{id}/transition` | Spoonbill | Transition claim status |
| GET | `/api/claims/{id}/transitions` | Spoonbill | Get valid transitions for claim |

### Claims - Practice Portal (`/practice`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/practice/claims` | Practice Mgr | Submit a claim (practice scoped) |
| GET | `/practice/claims` | Practice Mgr | List claims with filters + pagination |
| GET | `/practice/claims/{id}` | Practice Mgr | Get claim detail (tenant scoped) |
| POST | `/practice/claims/{id}/documents` | Practice Mgr | Upload document to claim |
| GET | `/practice/claims/{id}/documents` | Practice Mgr | List claim documents |
| GET | `/practice/documents/{id}` | Practice Mgr | Download document |
| GET | `/practice/claims/{id}/payment` | Practice Mgr | Get payment status for claim |
| GET | `/practice/dashboard` | Practice Mgr | Dashboard summary (claim counts by status) |
| GET | `/practice/payments` | Practice Mgr | List practice payments |

### Payments & Ledger (`/api/payments`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/payments/process` | Spoonbill | Process payment for approved claim |
| GET | `/api/payments` | Spoonbill | List payment intents |
| GET | `/api/payments/claim/{id}` | Spoonbill | Get payment for a specific claim |
| GET | `/api/payments/{id}` | Spoonbill | Get payment detail |
| POST | `/api/payments/{id}/retry` | Spoonbill | Retry failed payment |
| POST | `/api/payments/{id}/cancel` | Spoonbill | Cancel failed/queued payment |
| POST | `/api/payments/{id}/resolve` | Spoonbill | Resolve payment exception |
| GET | `/api/payments/ledger/summary` | Spoonbill | Get ledger account balances |
| POST | `/api/payments/ledger/seed` | Spoonbill | Seed capital into ledger |

### Practice Intake (`/apply`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/apply` | None | Submit practice application (rate limited: 5/hr/IP) |
| GET | `/apply/status/{id}` | None | Check application status (requires email) |

### Application Review (`/internal/applications`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/internal/applications` | Spoonbill | List all applications |
| GET | `/internal/applications/{id}` | Spoonbill | Get application detail |
| POST | `/internal/applications/{id}/review` | Spoonbill | Approve / Decline / Needs Info |
| PATCH | `/internal/applications/{id}` | Spoonbill | Edit application fields |
| GET | `/internal/applications/stats` | Spoonbill | Application statistics |
| POST | `/internal/applications/{id}/score` | Spoonbill | Compute underwriting score |
| POST | `/internal/applications/{id}/score/override` | Spoonbill | Override underwriting score |

### Invite & Password Setup

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/invite/validate/{token}` | None | Validate invite token |
| POST | `/invite/set-password` | None | Set password via invite token |

### User & Practice Management (`/api/users`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/users` | Admin | Create user |
| GET | `/api/users` | Admin | List users |
| PATCH | `/api/users/{id}/deactivate` | Admin | Deactivate user |
| PATCH | `/api/users/{id}/activate` | Admin | Activate user |
| POST | `/api/users/practices` | Admin | Create practice |
| GET | `/api/users/practices` | Admin | List practices |
| POST | `/api/users/practice-managers` | Admin | Create practice manager |

### Internal Practice Management (`/api/practices`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/practices` | Spoonbill | List practices with summary |
| GET | `/api/practices/{id}` | Spoonbill | Practice detail + managers + invites |
| GET | `/api/practices/{id}/invites` | Spoonbill | List invite history |
| POST | `/api/practices/{id}/invites/reissue` | Spoonbill | Reissue invite token (expires previous) |

### Financial Ontology (`/practices/{id}/ontology`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/practices/{id}/ontology/context` | Practice Mgr | Full ontology snapshot |
| POST | `/practices/{id}/ontology/rebuild` | Practice Mgr | Recompute ontology from claims data |
| POST | `/practices/{id}/ontology/brief` | Practice Mgr | Generate AI-assisted financial brief |
| GET | `/practices/{id}/ontology/cfo` | Practice Mgr | CFO 360 view |
| GET | `/practices/{id}/ontology/cohorts` | Practice Mgr | Time-series cohort data |
| GET | `/practices/{id}/ontology/risks` | Practice Mgr | Risk signals |
| GET | `/practices/{id}/ontology/graph` | Practice Mgr | Relationship graph (nodes + edges) |
| GET | `/practices/{id}/ontology/retention` | Practice Mgr | Patient retention metrics |
| GET | `/practices/{id}/ontology/reimbursement` | Practice Mgr | Reimbursement metrics |
| GET | `/practices/{id}/ontology/rcm` | Practice Mgr | RCM operations metrics |
| POST | `/practices/{id}/limit` | Practice Mgr | Adjust funding limit |

### Integrations (`/practice/integrations`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/practice/integrations/open-dental/status` | Practice Mgr | Integration status |
| POST | `/practice/integrations/open-dental/upload` | Practice Mgr | Upload claims CSV |
| POST | `/practice/integrations/open-dental/sync` | Spoonbill | Trigger API sync |
| GET | `/practice/integrations/open-dental/runs` | Practice Mgr | List sync runs |

### Ops & Economics (`/ops`)

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/ops/economics/summary` | Spoonbill | Liquidity summary |
| GET | `/ops/economics/exposure` | Spoonbill | Exposure breakdown |
| GET | `/ops/economics/payment-intents` | Spoonbill | Payment intent board |
| GET | `/ops/economics/exceptions` | Spoonbill | Exception claims + failed payments |
| GET | `/ops/economics/control-tower` | Spoonbill | Control tower dashboard |
| GET | `/ops/practices/{id}/crm` | Spoonbill | Practice CRM view |
| PATCH | `/ops/practices/{id}` | Spoonbill | Update practice fields |
| GET | `/ops/practices/{id}/users` | Spoonbill | Practice user list |
| POST | `/ops/practices/{id}/users/invite` | Spoonbill | Invite new practice user |
| POST | `/ops/action-proposals/generate` | Spoonbill | Generate action proposals |
| POST | `/ops/action-proposals/execute` | Spoonbill | Execute proposal |
| POST | `/ops/action-proposals/validate` | Spoonbill | Validate proposal |
| POST | `/ops/action-proposals/simulate` | Spoonbill | Simulate proposal |
| GET | `/ops/reconciliation/summary` | Spoonbill | Reconciliation summary |
| GET | `/ops/reconciliation/payment-intents` | Spoonbill | Payment intent reconciliation |
| POST | `/ops/reconciliation/ingest` | Spoonbill | Ingest balance/payment confirmation |
| POST | `/ops/reconciliation/resolve` | Spoonbill | Resolve reconciliation mismatch |
| GET | `/ops/tasks` | Spoonbill | List ops tasks |
| POST | `/ops/tasks/{id}/update` | Spoonbill | Update ops task |
| POST | `/ops/playbooks/run` | Spoonbill | Run a playbook |
| GET | `/ops/playbooks/templates` | Spoonbill | List playbook templates |

### Diagnostics

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | None | Health check with DB status |
| GET | `/diag` | None | Runtime diagnostics (CORS, migrations, environment) |

---

## Environment Variables

### Backend

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DATABASE_URL` | Yes | `postgresql://spoonbill:spoonbill_dev@localhost:5432/spoonbill` | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Yes | `change-this-in-production` | JWT signing secret |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Token expiration (minutes) |
| `ADMIN_EMAIL` | No | `admin@spoonbill.com` | Seed admin email |
| `ADMIN_PASSWORD` | No | `changeme123` | Seed admin password |
| `PRACTICE_PORTAL_BASE_URL` | Yes (staging/prod) | `http://localhost:5174` | Base URL for invite set-password links |
| `INTAKE_PORTAL_BASE_URL` | Yes (staging/prod) | `http://localhost:5175` | Intake Portal base URL |
| `CORS_ALLOWED_ORIGINS` | Yes (staging/prod) | _(none)_ | Comma-separated allowed origins |
| `RUN_MIGRATIONS_ON_STARTUP` | No | _(empty)_ | Set to `true` to auto-run Alembic migrations on startup |
| `UNDERWRITING_AMOUNT_THRESHOLD_CENTS` | No | `100000` ($1,000) | Amount requiring manual review |
| `UNDERWRITING_AUTO_APPROVE_BELOW_CENTS` | No | `10000` ($100) | Auto-approve threshold |
| `SENDGRID_API_KEY` | No | _(empty)_ | SendGrid API key for email delivery |
| `EMAIL_FROM_ADDRESS` | No | `noreply@spoonbill.com` | Sender email address |
| `EMAIL_INTERNAL_ALERTS` | No | _(empty)_ | Internal alert recipient email |
| `OPENAI_API_KEY` | No | _(empty)_ | OpenAI API key for ontology briefs |

### Frontends

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `VITE_API_BASE_URL` | Yes | `http://localhost:8000` | Backend API URL (all three frontends) |
| `VITE_PRACTICE_PORTAL_URL` | No | _(none)_ | Practice Portal URL (Internal Console only) |

> All `VITE_*` variables are embedded at build time by Vite. Changing them requires a rebuild.

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose (for PostgreSQL)

### 1. Start PostgreSQL

```bash
docker-compose up -d
```

This starts a Postgres 15 container on port 5432 with:
- User: `spoonbill`
- Password: `spoonbill_dev`
- Database: `spoonbill`

### 2. Set Up the Backend

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env

# Run database migrations
alembic upgrade head

# Seed the initial admin user
python -m app.cli
```

### 3. Start the Backend Server

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### 4. Start the Frontend Applications

Each frontend runs in a separate terminal:

```bash
# Internal Console (port 5173)
cd spoonbill-frontend && npm install && npm run dev

# Practice Portal (port 5174)
cd spoonbill-practice-frontend && npm install && npm run dev

# Intake Portal (port 5175)
cd spoonbill-intake-frontend && npm install && npm run dev
```

### Local URLs

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Internal Console | http://localhost:5173 |
| Practice Portal | http://localhost:5174 |
| Intake Portal | http://localhost:5175 |

### Default Credentials

Admin login (from `.env`): `admin@spoonbill.com` / `changeme123`

---

## Database Setup

### Database Type

PostgreSQL 15 (via Docker for local development, Render managed PostgreSQL for staging/production).

### Migrations

Spoonbill uses [Alembic](https://alembic.sqlalchemy.org/) for schema migrations. Migration scripts live in `alembic/versions/`.

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration from model changes
alembic revision --autogenerate -m "Description of change"

# Rollback one migration
alembic downgrade -1

# Check current migration state
alembic current
```

### Auto-Migrations on Startup

When `RUN_MIGRATIONS_ON_STARTUP=true` is set, the backend automatically runs `alembic upgrade head` during startup. It acquires a PostgreSQL advisory lock (key `9142026`) to prevent concurrent migration runs across multiple instances.

### Schema Management

- Models are defined in `app/models/` using SQLAlchemy declarative base
- The Alembic `env.py` reads `DATABASE_URL` from settings (not from `alembic.ini`)
- Always create migrations via `--autogenerate` and review the generated script before applying

---

## Deployment

### Render (Staging)

Spoonbill is deployed on Render with four services and one managed PostgreSQL database. The `render.yaml` blueprint file defines all services.

#### Staging URLs

| Service | URL |
|---------|-----|
| Backend API | https://spoonbill-staging-api.onrender.com |
| Internal Console | https://spoonbill-staging-internal.onrender.com |
| Practice Portal | https://spoonbill-staging-portal.onrender.com |
| Intake Portal | https://spoonbill-staging-intake.onrender.com |

#### Deploy via Blueprint

1. Go to Render Dashboard -> Blueprints
2. Connect the repository
3. Render detects `render.yaml` and creates all services
4. Set the required environment variables for each service

#### Service Configuration

**Backend API** (Web Service - Python):
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- Required env vars: `DATABASE_URL`, `JWT_SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `CORS_ALLOWED_ORIGINS`, `PRACTICE_PORTAL_BASE_URL`, `INTAKE_PORTAL_BASE_URL`, `RUN_MIGRATIONS_ON_STARTUP=true`

**Internal Console** (Static Site):
- Root: `spoonbill-frontend`
- Build: `npm install && npm run build`
- Publish: `dist`
- Rewrite: `/* -> /index.html`
- Env: `VITE_API_BASE_URL`, `VITE_PRACTICE_PORTAL_URL`

**Practice Portal** (Static Site):
- Root: `spoonbill-practice-frontend`
- Build: `npm install && npm run build`
- Publish: `dist`
- Rewrite: `/* -> /index.html`
- Env: `VITE_API_BASE_URL`

**Intake Portal** (Static Site):
- Root: `spoonbill-intake-frontend`
- Build: `npm install && npm run build`
- Publish: `dist`
- Rewrite: `/* -> /index.html`
- Env: `VITE_API_BASE_URL`

### Docker

A `Dockerfile` is provided for the backend:

```bash
docker build -t spoonbill-api .
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e JWT_SECRET_KEY=... \
  spoonbill-api
```

#### Verifying Deployment

```bash
# Health check
curl https://spoonbill-staging-api.onrender.com/health
# {"status":"healthy","version":"4.0.0","database":"connected"}

# Runtime diagnostics (CORS, migration state)
curl https://spoonbill-staging-api.onrender.com/diag
```

#### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| CORS errors | Frontend domain not in `CORS_ALLOWED_ORIGINS` | Add exact frontend URL (no trailing slash) |
| 503 on API | Database migration pending | Set `RUN_MIGRATIONS_ON_STARTUP=true` and redeploy |
| Invite links show localhost | `PRACTICE_PORTAL_BASE_URL` not set | Set env var on backend service |
| API changes not reflected | `VITE_API_BASE_URL` changed | Rebuild frontend (Vite embeds at build time) |

---

## Testing

```bash
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/test_payments.py -v
pytest tests/test_tenant_isolation.py -v
pytest tests/test_underwriting.py -v
pytest tests/test_applications.py -v
pytest tests/test_state_machine.py -v
pytest tests/test_integrations.py -v
pytest tests/test_ontology.py -v
pytest tests/test_economics.py -v
pytest tests/test_control_tower.py -v
pytest tests/test_intake_scoring.py -v
pytest tests/test_crm_edit.py -v
```

### Test Coverage Areas

| Test File | Coverage |
|-----------|----------|
| `test_payments.py` | PaymentIntent lifecycle, ledger balance, idempotency, failure/retry, capital seeding |
| `test_tenant_isolation.py` | Cross-practice access denied, practice_id scoping, 404 on unauthorized access |
| `test_underwriting.py` | Auto-approve, manual review, duplicate detection, threshold enforcement |
| `test_state_machine.py` | Valid/invalid transitions, terminal states |
| `test_applications.py` | Intake submission, invite URL generation, password setup |
| `test_integrations.py` | CSV parsing, claim ingestion, sync runs |
| `test_ontology.py` | Builder, context, cohorts, graph |
| `test_economics.py` | Liquidity, exposure, control tower |
| `test_control_tower.py` | Control tower dashboard metrics |
| `test_intake_scoring.py` | Application underwriting score |
| `test_crm_edit.py` | Practice editing, duplicate email conflicts |

---

## Multi-Tenancy & Security

- **JWT-derived practice_id**: For `PRACTICE_MANAGER` users, `practice_id` comes from the JWT. Never accepted from request payloads.
- **Query scoping**: Every query for claims, documents, and payments includes `practice_id`. Service-layer authorization verifies ownership.
- **Information hiding**: Unauthorized access returns 404 (not 403) to prevent resource existence disclosure.
- **Rate limiting**: Login (10 req/5 min/IP) and intake submission (5 req/hour/IP).
- **Honeypot**: Intake form includes a hidden `company_url` field; bots that fill it are silently rejected.
- **Invite security**: Single-use, 7-day expiry, 64-character random tokens. URLs generated server-side.
- **SPA routing**: Practice Portal uses HashRouter (`/#/...`) for static hosting compatibility.
- **Document storage**: Files stored on disk with a volume (`/data/uploads`). Download endpoints enforce practice scoping.

---

## External Integrations

### Open Dental

- **CSV Upload**: Practice managers can upload claims and line-item CSVs via the Practice Portal. The system parses, deduplicates, and ingests claims.
- **API Sync**: Spoonbill can pull claims from an Open Dental API endpoint (requires configuration in `IntegrationConnection`).
- **Sync Tracking**: Each sync run is recorded with status (`RUNNING`, `SUCCEEDED`, `FAILED`), counts, and error details.

### SendGrid

- Email delivery for notifications (requires `SENDGRID_API_KEY`). Currently not actively used for invite delivery -- invite links are manually shared.

### OpenAI

- Optional LLM integration for generating ontology briefs (`OPENAI_API_KEY`). Falls back to deterministic briefs when not configured.

---

## Onboarding Flow

Practice onboarding spans all three frontends:

```
Intake Portal          Internal Console           Practice Portal
-----------          ----------------           ---------------
Submit app  -------> Review application
                     Approve/Decline
                     |
                     (on APPROVE)
                     Create Practice
                     Create PRACTICE_MANAGER user
                     Generate invite token (7-day expiry)
                     |
                     Copy invite link  --------> /set-password/:token
                                                 Validate token
                                                 Set password
                                                 Login --> Dashboard
```

---

## Known Limitations

- **Simulated payments only**: Payment provider is a stub. No real bank integration (FedNow, ACH) yet.
- **No real-time notifications**: Frontends poll on intervals rather than WebSockets.
- **No email delivery for invites**: Invite links must be manually copied and shared by ops.
- **Single admin seed**: The CLI seeds one admin user. Additional users are created via API.

---

## Future Roadmap

- Real bank integration (FedNow / ACH) for live payment processing
- Automated underwriting scoring model with ML-based risk assessment
- Observability stack (structured logging, metrics, distributed tracing)
- Production hardening (connection pooling tuning, secrets rotation, comprehensive rate limiting)
- Email delivery for invite links and notifications
- WebSocket-based real-time updates for claim status changes
- Multi-currency support
- Practice self-service onboarding with automated KYB verification
