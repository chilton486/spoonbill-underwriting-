# Spoonbill

System of record and capital orchestration layer for insurance claims.

Claims are obligations. Payments are irreversible. The ledger is truth. The audit log is defense.

One canonical backend serves three purpose-built frontends, each scoped to a specific user role and workflow.

## Architecture

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

**Backend**: FastAPI, PostgreSQL, Alembic migrations, JWT authentication, multi-tenant enforcement, double-entry ledger, PaymentIntent lifecycle, rules-based underwriting engine.

**Internal Console** (Spoonbill Ops): Claims management, underwriting review, practice administration, invite management, payment processing, audit trail.

**Practice Portal** (Practice Manager): Claim submission, document uploads, claim status tracking, password setup via invite link.

**Intake Portal** (Public): Practice onboarding application form. No authentication required.

## Claim Lifecycle

Claims follow a strict state machine:

```
NEW --> NEEDS_REVIEW --> APPROVED --> PAID --> COLLECTING --> CLOSED
 |          |              |
 +----------+--------------+---> DECLINED (terminal)
```

| Status | Description |
|--------|-------------|
| `NEW` | Claim created, underwriting rules evaluate automatically |
| `NEEDS_REVIEW` | Flagged for manual ops review (missing data, high amount) |
| `APPROVED` | Underwriting passed, PaymentIntent created |
| `PAID` | Payment confirmed, funds sent to practice |
| `COLLECTING` | Collecting from insurance payer |
| `CLOSED` | Claim fully resolved |
| `DECLINED` | Rejected (terminal state) |

**Underwriting rules** run automatically on claim creation:

1. Missing payer or amount --> `NEEDS_REVIEW`
2. Duplicate fingerprint (practice_id + patient + date + amount + payer) --> `DECLINED`
3. Amount > threshold --> `NEEDS_REVIEW`
4. Amount < auto-approve threshold --> `APPROVED`
5. Otherwise --> `APPROVED`

When a claim reaches `APPROVED`, a `PaymentIntent` is created automatically. This triggers the ledger reservation flow.

### Claim Tokenization

Every claim gets a unique, non-guessable `claim_token` in the format `SB-CLM-<8 chars base32>`. Generated at creation, immutable, indexed for fast lookups. Displayed in both Internal Console and Practice Portal. Usable for filtering and search.

## Payments

Double-entry accounting with three ledger accounts:

| Account | Purpose |
|---------|---------|
| `CAPITAL_CASH` | Spoonbill's available capital |
| `PAYMENT_CLEARING` | In-flight payments awaiting confirmation |
| `PRACTICE_PAYABLE` | Amounts owed to practices |

Every financial event creates paired DEBIT/CREDIT entries that sum to zero.

### Payment Flow

```
Claim APPROVED
  --> PaymentIntent created (QUEUED)
  --> Reserve: CAPITAL_CASH debit, PAYMENT_CLEARING credit
  --> Send: PaymentIntent status --> SENT
  --> Confirm: PAYMENT_CLEARING debit, PRACTICE_PAYABLE credit, Claim --> PAID
  --> (Failure path): Reversal entries posted, payment_exception flag set
```

### Idempotency

- One PaymentIntent per claim (UNIQUE constraint on `claim_id`)
- Deterministic idempotency key: `claim:{claim_id}:payment:v1`
- Ledger entries have unique idempotency keys to prevent double-posting
- Retry operations check existing state before creating new entries

### Payment API

```bash
# Process payment for an approved claim
POST /api/payments/claims/{id}/process

# Get payment status
GET /api/payments/claims/{id}

# Retry a failed payment
POST /api/payments/{id}/retry

# Seed capital (admin only)
POST /api/payments/capital/seed
# Body: {"amount_cents": 100000000}

# Get capital balance
GET /api/payments/capital/balance
```

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

### Application Statuses

| Status | Description |
|--------|-------------|
| `SUBMITTED` | Received, awaiting ops review |
| `NEEDS_INFO` | Ops requested additional information |
| `APPROVED` | Practice + manager created, invite generated |
| `DECLINED` | Rejected, no accounts created |

### Invite Tokens

- Single-use (marked as used after password is set)
- 7-day expiry
- 64-character random token
- Reissuable from Internal Console (expires previous active invites)
- Invite URL generated server-side using `PRACTICE_PORTAL_BASE_URL`

### Intake Form Fields

The intake form collects:

- **Practice info**: Legal name, address, phone, website, tax ID, practice type
- **Operations**: Years in operation, provider count, operatory count
- **Financial**: Monthly collections range, insurance vs self-pay mix, top payers, average AR days
- **Billing**: Model (in-house/outsourced/hybrid), follow-up frequency, practice management software, claims per month, electronic claims
- **Application**: Stated goal, urgency level
- **Contact**: Name, email, phone (this person becomes the Practice Manager)

### Intake Security

- IP-based rate limiting (5 requests/hour/IP)
- Server-side input validation (max lengths, required fields, email/phone format)
- Honeypot field (`company_url`) silently rejects bot submissions

### Public Intake API

```bash
# Submit application (no auth required)
POST /apply
# Body: {legal_name, address, phone, practice_type, years_in_operation, ...}

# Check status (requires application ID + email)
GET /apply/status/{id}?email=contact@practice.com
```

### Internal Ops Review API

```bash
# List all applications
GET /internal/applications

# Get application details
GET /internal/applications/{id}

# Review application (APPROVE / DECLINE / NEEDS_INFO)
POST /internal/applications/{id}/review
# Body: {"action": "APPROVE", "review_notes": "Verified practice information"}
```

## Practice Financial Ontology (Phase 2)

The Practice Portal includes a structured, queryable Dental Financial Ontology. This provides CFO-grade analytics, time-series and cohort modeling, a deterministic risk engine, and a relationship graph — all practice-scoped and without PHI.

- Everything is an object (Practice, Claim, Payer, Procedure, PaymentIntent, Patient [de-identified])
- Objects have relationships (CLAIM_BILLED_TO_PAYER, CLAIM_HAS_PROCEDURE, CLAIM_FUNDED_BY_PAYMENT_INTENT, CLAIM_BELONGS_TO_PATIENT)
- Metrics are traceable to objects; all views are projections of the ontology
- No PHI exposure: patient objects are de-identified (stable patient_hash)

### Key Endpoints (Practice-scoped)

```bash
GET  /practices/{id}/ontology/context   # Snapshot with totals, funding, mixes, cohorts, denials, risks, patient dynamics
POST /practices/{id}/ontology/rebuild   # Recompute ontology objects/links/kpis (fast)
POST /practices/{id}/ontology/brief     # Deterministic brief (LLM optional)
GET  /practices/{id}/ontology/cfo       # CFO 360° view (capital, revenue, payer risk, patient dynamics, ops risk, growth)
GET  /practices/{id}/ontology/cohorts   # Time-series, rolling windows, aging buckets, lag curve, submission cohorts
GET  /practices/{id}/ontology/risks     # Deterministic risk signals (severity, metric, value, explanation)
GET  /practices/{id}/ontology/graph     # Graph projection (nodes + edges) for explorer UI
```

### Frontend (Practice Portal → Ontology tab)

Sections:
- CFO Snapshot (utilization, capacity, billed MTD, reimbursed MTD, 90d avg)
- Time-Series Trends (30d rolling, cumulative billed/funded/confirmed)
- Cohort Aging Panel (0–30/30–60/60–90/90+ and lag curve)
- Patient Mix (age buckets, insurance type, repeat visit rate)
- Risk Intelligence (deterministic rules; color-coded severity)
- Ontology Brief (Generate Brief + Apply Adjust Limit recommendation)
- Relationship Explorer (interactive canvas graph)

No new env vars are required for Phase 2; all endpoints remain practice-scoped and honor tenant isolation.

## Multi-Tenancy and Security

**practice_id from JWT**: For `PRACTICE_MANAGER` users, `practice_id` is derived from the JWT token. It is never accepted from request payloads.

**Query scoping**: Every database query for claims and documents includes `practice_id` scope. Service-layer authorization verifies ownership on all get-by-ID operations.

**Unauthorized access**: Returns 404 (not 403) to prevent information disclosure about resource existence.

**Environment-driven CORS**: `CORS_ALLOWED_ORIGINS` controls which frontend domains can access the API. Localhost origins are included automatically for local development.

**Invite tokens**: Single-use, time-limited (7 days), 64-character random strings. URLs are generated server-side from `PRACTICE_PORTAL_BASE_URL` -- no client-side URL construction. The Practice Portal uses HashRouter (`/#/set-password/:token`) so invite links work on any static hosting without server-side rewrite rules.

**Document storage**: Files stored on disk with a Docker volume (`/data/uploads`). Download endpoints enforce practice scoping.

### Roles

| Role | Scope |
|------|-------|
| `SPOONBILL_ADMIN` | Full system access: users, practices, claims, payments |
| `SPOONBILL_OPS` | Claims, underwriting, status transitions, practice management |
| `PRACTICE_MANAGER` | Own practice only: claims, documents, status viewing |

## Deployment (Render)

Spoonbill staging is deployed on Render with four services and one database.

### Staging URLs

| Service | URL |
|---------|-----|
| Backend API | https://spoonbill-staging-api.onrender.com |
| Internal Console | https://spoonbill-staging-internal.onrender.com |
| Practice Portal | https://spoonbill-staging-portal.onrender.com |
| Intake Portal | https://spoonbill-staging-intake.onrender.com |

### Backend API

| Setting | Value |
|---------|-------|
| Service name | `spoonbill-staging-api` |
| Runtime | Python |
| Build command | `pip install -r requirements.txt` |
| Start command | `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health` |

**Required environment variables:**

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | PostgreSQL connection string (from Render PostgreSQL) |
| `JWT_SECRET_KEY` | Secure random string for JWT signing |
| `ADMIN_EMAIL` | Initial admin email |
| `ADMIN_PASSWORD` | Initial admin password |
| `CORS_ALLOWED_ORIGINS` | `https://spoonbill-staging-internal.onrender.com,https://spoonbill-staging-portal.onrender.com,https://spoonbill-staging-intake.onrender.com` |
| `PRACTICE_PORTAL_BASE_URL` | `https://spoonbill-staging-portal.onrender.com` |
| `INTAKE_PORTAL_BASE_URL` | `https://spoonbill-staging-intake.onrender.com` |

### Internal Console

| Setting | Value |
|---------|-------|
| Service name | `spoonbill-staging-internal` |
| Root directory | `spoonbill-frontend` |
| Build command | `npm install && npm run build` |
| Publish directory | `dist` |

**Environment variables:**

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://spoonbill-staging-api.onrender.com` |

**Rewrite rule**: `/*` --> `/index.html` (SPA routing)

### Practice Portal

| Setting | Value |
|---------|-------|
| Service name | `spoonbill-staging-portal` |
| Root directory | `spoonbill-practice-frontend` |
| Build command | `npm install && npm run build` |
| Publish directory | `dist` |

**Environment variables:**

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://spoonbill-staging-api.onrender.com` |

**Rewrite rule**: `/*` --> `/index.html` (SPA routing)

### Intake Portal

| Setting | Value |
|---------|-------|
| Service name | `spoonbill-staging-intake` |
| Root directory | `spoonbill-intake-frontend` |
| Build command | `npm install && npm run build` |
| Publish directory | `dist` |

**Environment variables:**

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://spoonbill-staging-api.onrender.com` |

**Rewrite rule**: `/*` --> `/index.html` (SPA routing)

### render.yaml Blueprint

The included `render.yaml` can deploy all services at once:

1. Go to Render Dashboard --> Blueprints
2. Connect the repository
3. Render detects `render.yaml` and creates all services
4. Set the required environment variables for each service

### Verifying Deployment

```bash
curl https://spoonbill-staging-api.onrender.com/health
# {"status":"healthy","version":"4.0.0","database":"connected"}

# API docs: https://spoonbill-staging-api.onrender.com/docs
```

### SPA Routing

The Practice Portal uses **HashRouter** (`/#/...` URLs) so client-side routes work on any static host without server-side rewrite configuration. Invite links use the format: `{PRACTICE_PORTAL_BASE_URL}/#/set-password/{token}`.

The Internal Console and Intake Portal have `/*` --> `/index.html` rewrite rules in `render.yaml`, but these only take effect if services are deployed via Render Blueprints. For manually created services, add the rewrite rule in the Render Dashboard under Static Site settings.

### How to Reissue an Invite

If a practice manager's invite link has expired or was lost:

1. Open the Internal Console
2. Navigate to the **Practices** tab
3. Select the practice
4. Click **Reissue Invite** -- this expires any previous active invites and generates a new 7-day token
5. Copy the new invite link and share it with the practice manager

**Troubleshooting:**
- **CORS errors**: Ensure `CORS_ALLOWED_ORIGINS` includes exact frontend URLs (no trailing slashes)
- **API not found**: `VITE_API_BASE_URL` must be set at build time (Vite embeds it during build). Changing it requires a redeploy.
- **Database errors**: Verify `DATABASE_URL` is set and the Render PostgreSQL instance is accessible
- **Invite links showing localhost**: Ensure `PRACTICE_PORTAL_BASE_URL` is set on the backend service

### Staging Debugging

**`/diag` endpoint**: Hit `https://spoonbill-staging-api.onrender.com/diag` to inspect runtime CORS config, alembic revision, and environment. No authentication required. Returns:

```json
{
  "ok": true,
  "cors_allow_origins": ["..."],
  "cors_allow_methods": ["*"],
  "cors_allow_headers": ["*"],
  "cors_allow_credentials": false,
  "environment": "true",
  "alembic_revision": "ontology_v2"
}
```

**CORS env var**: `CORS_ALLOWED_ORIGINS` must include all staging frontend domains (comma-separated, no trailing slashes):

```
CORS_ALLOWED_ORIGINS=https://spoonbill-staging-portal.onrender.com,https://spoonbill-staging-internal.onrender.com,https://spoonbill-staging-intake.onrender.com
```

**Migrations**: The Render start command runs `alembic upgrade head` before starting the server. If you see 503 errors with "migration may be pending", check `/diag` for the current `alembic_revision` and verify it matches the latest migration in `alembic/versions/`.

**Common staging issues:**

| Symptom | Cause | Fix |
|---------|-------|-----|
| Status "--" in Safari DevTools | CORS preflight blocked | Check `/diag` origins match frontend domain exactly |
| 503 "migration may be pending" | DB schema out of sync | Redeploy API (triggers `alembic upgrade head`) |
| 500 on `/api/practices` | Missing column from unapplied migration | Same as above |
| "Load failed" in Ontology tab | Ontology tables missing | Same as above |
| Invite links show localhost | `PRACTICE_PORTAL_BASE_URL` not set | Set env var on API service |

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose (for PostgreSQL)

### Setup

```bash
# Start PostgreSQL
docker-compose up -d

# Backend setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.cli   # seed initial admin user

# Start backend (port 8000)
uvicorn app.main:app --reload --port 8000

# In separate terminals:

# Start Internal Console (port 5173)
cd spoonbill-frontend && npm install && npm run dev

# Start Practice Portal (port 5174)
cd spoonbill-practice-frontend && npm install && npm run dev

# Start Intake Portal (port 5175)
cd spoonbill-intake-frontend && npm install && npm run dev
```

### Local URLs

| Service | URL |
|---------|-----|
| Internal Console | http://localhost:5173 |
| Practice Portal | http://localhost:5174 |
| Intake Portal | http://localhost:5175 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

Default admin credentials (from `.env`): `admin@spoonbill.com` / `changeme123`

### Database Migrations

```bash
alembic revision --autogenerate -m "Description"   # create migration
alembic upgrade head                                # apply migrations
alembic downgrade -1                                # rollback one
```

## Environment Variable Reference

### Backend

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DATABASE_URL` | Yes | `postgresql://spoonbill:spoonbill_dev@localhost:5432/spoonbill` | PostgreSQL connection string |
| `JWT_SECRET_KEY` | Yes | `change-this-in-production` | JWT signing key |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Token expiration in minutes |
| `ADMIN_EMAIL` | No | `admin@spoonbill.com` | Seed admin email |
| `ADMIN_PASSWORD` | No | `changeme123` | Seed admin password |
| `PRACTICE_PORTAL_BASE_URL` | Yes (staging/prod) | `http://localhost:5174` | Base URL for invite set-password links |
| `INTAKE_PORTAL_BASE_URL` | Yes (staging/prod) | `http://localhost:5175` | Intake Portal base URL |
| `CORS_ALLOWED_ORIGINS` | Yes (staging/prod) | (none) | Comma-separated allowed origins |
| `UNDERWRITING_AMOUNT_THRESHOLD_CENTS` | No | `100000` ($1,000) | Amount requiring manual review |
| `UNDERWRITING_AUTO_APPROVE_BELOW_CENTS` | No | `10000` ($100) | Auto-approve threshold |

### Frontends

| App | Variable | Required | Default | Purpose |
|-----|----------|----------|---------|---------|
| Internal Console | `VITE_API_BASE_URL` | Yes | `http://localhost:8000` | Backend API URL |
| Practice Portal | `VITE_API_BASE_URL` | Yes | `http://localhost:8000` | Backend API URL |
| Intake Portal | `VITE_API_BASE_URL` | Yes | `http://localhost:8000` | Backend API URL |

All `VITE_*` variables are embedded at build time by Vite. Changing them requires a rebuild.

## Testing

```bash
source .venv/bin/activate

# All tests
pytest tests/ -v

# Payment tests
pytest tests/test_payments.py -v

# Tenant isolation tests
pytest tests/test_tenant_isolation.py -v

# Invite URL generation tests
pytest tests/test_applications.py::TestInviteUrlGeneration -v
```

### Test Coverage

- **Payments**: PaymentIntent lifecycle, ledger balance, idempotency, failure/retry, capital seeding
- **Tenant isolation**: Cross-practice access denied, practice_id scoping, 404 on unauthorized access
- **Underwriting**: Auto-approve, manual review, duplicate detection, threshold enforcement
- **Invite URLs**: Environment variable reads, default values, no hardcoded localhost in staging, trailing slash handling, schema validation

## Known Limitations

- **Simulated payments only**: Payment provider is a stub. No real bank integration (FedNow, ACH) yet.
- **No real-time notifications**: Frontends poll on intervals (5-10 seconds) rather than WebSockets.
- **Invite URLs require correct env vars**: If `PRACTICE_PORTAL_BASE_URL` is not set on staging/production, invite links default to localhost.
- **No email delivery**: Invite links must be manually copied and shared by ops.
- **Single admin seed**: The CLI seeds one admin user. Additional users created via API.

## Roadmap

- Real bank integration (FedNow / ACH)
- Automated underwriting scoring model
- Observability (structured logging, metrics, tracing)
- Production hardening (connection pooling, rate limiting on all endpoints, secrets rotation)
- Email delivery for invite links
- WebSocket-based real-time updates

## Project Structure

```
spoonbill-underwriting-/
  app/
    main.py                     # FastAPI entry point
    config.py                   # Settings from environment
    database.py                 # SQLAlchemy setup
    state_machine.py            # Claim status transitions
    cli.py                      # CLI commands (seed admin)
    models/                     # SQLAlchemy models
    schemas/                    # Pydantic schemas
    routers/                    # API endpoints
    services/                   # Business logic
  alembic/                      # Database migrations
  tests/                        # Unit tests
  spoonbill-frontend/           # Internal Console (React + MUI)
  spoonbill-practice-frontend/  # Practice Portal (React + MUI)
  spoonbill-intake-frontend/    # Intake Portal (React + MUI)
  docker-compose.yml            # Local PostgreSQL
  render.yaml                   # Render deployment blueprint
  requirements.txt              # Python dependencies
```
