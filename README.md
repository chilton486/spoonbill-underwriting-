# Spoonbill Internal System of Record

Phase 1-4 implementation of the Spoonbill claim lifecycle management system with authentication, underwriting, audit trail, multi-tenant Practice Portal, payments, and practice onboarding.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose (for PostgreSQL)

### 1. Start PostgreSQL

```bash
docker-compose up -d
```

### 2. Set up Backend

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run database migrations
alembic upgrade head

# Seed initial admin user
python -m app.cli
```

### 3. Start Backend

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### 4. Start Internal Console (Frontend)

```bash
cd spoonbill-frontend
npm install
npm run dev
```

### 5. Start Practice Portal (Frontend)

```bash
cd spoonbill-practice-frontend
npm install
npm run dev
```

### 6. Access the Applications

- Internal Console: http://localhost:5173
- Practice Portal: http://localhost:5174
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

Default admin credentials (from .env):
- Email: admin@spoonbill.com
- Password: changeme123

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection string | postgresql://spoonbill:spoonbill_dev@localhost:5432/spoonbill |
| JWT_SECRET_KEY | Secret key for JWT tokens | change-this-in-production |
| JWT_ALGORITHM | JWT algorithm | HS256 |
| JWT_ACCESS_TOKEN_EXPIRE_MINUTES | Token expiration | 60 |
| UNDERWRITING_AMOUNT_THRESHOLD_CENTS | Amount requiring review | 100000 ($1000) |
| UNDERWRITING_AUTO_APPROVE_BELOW_CENTS | Auto-approve threshold | 10000 ($100) |
| ADMIN_EMAIL | Initial admin email | admin@spoonbill.com |
| ADMIN_PASSWORD | Initial admin password | changeme123 |

## Claim Lifecycle

Claims follow this state machine:

```
NEW → NEEDS_REVIEW → APPROVED → PAID → COLLECTING → CLOSED
  ↓        ↓            ↓
  └────────┴────────────┴──→ DECLINED
```

### Status Definitions

- **NEW**: Claim just created, awaiting underwriting
- **NEEDS_REVIEW**: Underwriting flagged for manual review
- **APPROVED**: Underwriting approved, ready for payment
- **PAID**: Payment sent to practice
- **COLLECTING**: Collecting from payer
- **CLOSED**: Claim fully resolved
- **DECLINED**: Claim rejected

## API Endpoints

### Authentication

```bash
# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@spoonbill.com&password=changeme123"

# Get current user
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <token>"
```

### Claims

```bash
# Create a claim (triggers automatic underwriting)
curl -X POST http://localhost:8000/api/claims \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "payer": "Aetna",
    "amount_cents": 15000,
    "patient_name": "John Doe",
    "procedure_date": "2026-01-15",
    "procedure_codes": "D0120, D1110"
  }'

# List claims
curl http://localhost:8000/api/claims \
  -H "Authorization: Bearer <token>"

# List claims by status
curl "http://localhost:8000/api/claims?status=NEW" \
  -H "Authorization: Bearer <token>"

# Get claim detail
curl http://localhost:8000/api/claims/1 \
  -H "Authorization: Bearer <token>"

# Get valid transitions for a claim
curl http://localhost:8000/api/claims/1/transitions \
  -H "Authorization: Bearer <token>"

# Transition claim status
curl -X POST http://localhost:8000/api/claims/1/transition \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"to_status": "APPROVED", "reason": "Manual approval after review"}'
```

### Users (Admin only)

```bash
# Create user
curl -X POST http://localhost:8000/api/users \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"email": "ops@spoonbill.com", "password": "password123", "role": "OPS"}'

# List users
curl http://localhost:8000/api/users \
  -H "Authorization: Bearer <token>"
```

## Underwriting Rules

The rules-based underwriting engine evaluates claims automatically:

1. **Missing payer** → NEEDS_REVIEW
2. **Missing amount** → NEEDS_REVIEW
3. **Duplicate claim** → DECLINE (based on fingerprint: practice_id + patient_name + procedure_date + amount_cents + payer)
4. **Amount > threshold** → NEEDS_REVIEW
5. **Amount < auto-approve threshold** → APPROVE (auto)
6. **Otherwise** → APPROVE

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

## Project Structure

```
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings from environment
│   ├── database.py          # SQLAlchemy setup
│   ├── state_machine.py     # Claim status transitions
│   ├── cli.py               # CLI commands (seed admin)
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   ├── routers/             # API endpoints
│   └── services/            # Business logic
├── alembic/                 # Database migrations
├── tests/                   # Unit tests
├── spoonbill-frontend/      # React frontend
├── docker-compose.yml       # PostgreSQL setup
└── requirements.txt         # Python dependencies
```

## Accessing the Old Demo

The original demo is preserved in the `demo-v0` branch:

```bash
git checkout demo-v0
```

## Roles

- **SPOONBILL_ADMIN**: Can manage users, practices, and perform all operations
- **SPOONBILL_OPS**: Can view claims, run underwriting, and transition claim statuses
- **PRACTICE_MANAGER**: Can only access their own practice's claims and documents

## Phase 2: Practice Portal

### Creating a Practice

Practices must be created by a Spoonbill admin before practice managers can be added:

```bash
# Login as admin
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@spoonbill.com&password=changeme123" | jq -r '.access_token')

# Create a practice
curl -X POST http://localhost:8000/api/users/practices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Downtown Family Dentistry"}'

# List all practices
curl http://localhost:8000/api/users/practices \
  -H "Authorization: Bearer $TOKEN"
```

### Creating a Practice Manager

Practice managers are users tied to exactly one practice:

```bash
# Create a practice manager for practice_id=1
curl -X POST http://localhost:8000/api/users/practice-managers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "manager@downtown-dental.com",
    "password": "securepassword123",
    "practice_id": 1
  }'
```

### Practice Portal Features

The Practice Portal (http://localhost:5174) allows practice managers to:

1. **Login** with their practice credentials
2. **View claims** belonging only to their practice
3. **Submit new claims** (underwriting runs automatically)
4. **Upload documents** to their claims
5. **View claim status** with near-real-time updates (5-second polling)
6. **View audit trail** for their claims (read-only)

### Practice Portal API Endpoints

```bash
# Login as practice manager
PM_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=manager@downtown-dental.com&password=securepassword123" | jq -r '.access_token')

# List practice's claims
curl http://localhost:8000/practice/claims \
  -H "Authorization: Bearer $PM_TOKEN"

# Submit a new claim (practice_id comes from auth token)
curl -X POST http://localhost:8000/practice/claims \
  -H "Authorization: Bearer $PM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payer": "Aetna",
    "amount_cents": 15000,
    "patient_name": "John Doe",
    "procedure_date": "2026-01-15",
    "procedure_codes": "D0120, D1110"
  }'

# Get claim detail
curl http://localhost:8000/practice/claims/1 \
  -H "Authorization: Bearer $PM_TOKEN"

# Upload a document
curl -X POST http://localhost:8000/practice/claims/1/documents \
  -H "Authorization: Bearer $PM_TOKEN" \
  -F "file=@/path/to/document.pdf"

# List documents for a claim
curl http://localhost:8000/practice/claims/1/documents \
  -H "Authorization: Bearer $PM_TOKEN"

# Download a document
curl http://localhost:8000/practice/documents/1 \
  -H "Authorization: Bearer $PM_TOKEN" \
  --output document.pdf
```

## Tenant Isolation

Phase 2 implements strict multi-tenant isolation with defense-in-depth:

**Query Scoping**: Every database query for claims and documents includes practice_id scope. Practice managers can only see data belonging to their practice.

**Service-Layer Authorization**: Any "get by ID" operation verifies practice ownership even if the query is filtered. This prevents ID guessing attacks.

**practice_id Source of Truth**:
- For PRACTICE_MANAGER users: practice_id comes from the JWT token only, never from request payload
- For SPOONBILL roles: optional practice_id filter is allowed, but defaults to "all"

**Unauthorized Access**: Returns 404 (not 403) to avoid information disclosure about whether a resource exists.

**Document Storage**: Files are stored on disk with a Docker volume (`/data/uploads`). Download endpoints enforce practice scoping, not just document ID lookup.

## Phase 3: Payments MVP

Phase 3 introduces safe, auditable capital movement tied to approved insurance claims.

### Ledger Design

The system uses double-entry accounting with three account types:

- **CAPITAL_CASH**: Spoonbill's available capital
- **PAYMENT_CLEARING**: In-flight payments
- **PRACTICE_PAYABLE**: Amounts owed to practices

Every financial event creates paired ledger entries (DEBIT/CREDIT) that sum to zero.

### Payment Flow

1. **Claim APPROVED** → PaymentIntent created (QUEUED)
2. **Reserve funds** → CAPITAL_CASH debited, PAYMENT_CLEARING credited
3. **Send payment** → PaymentIntent status → SENT
4. **Confirm payment** → PAYMENT_CLEARING debited, PRACTICE_PAYABLE credited, claim → PAID
5. **Failure path** → Reversal entries posted, claim gets payment_exception flag

### Payment API Endpoints

```bash
# Process payment for an approved claim
curl -X POST http://localhost:8000/api/payments/claims/1/process \
  -H "Authorization: Bearer $TOKEN"

# Get payment status for a claim
curl http://localhost:8000/api/payments/claims/1 \
  -H "Authorization: Bearer $TOKEN"

# Retry a failed payment
curl -X POST http://localhost:8000/api/payments/1/retry \
  -H "Authorization: Bearer $TOKEN"

# Seed capital (admin only)
curl -X POST http://localhost:8000/api/payments/capital/seed \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount_cents": 100000000}'

# Get capital balance
curl http://localhost:8000/api/payments/capital/balance \
  -H "Authorization: Bearer $TOKEN"
```

### Idempotency Guarantees

- Each claim can have exactly one PaymentIntent (UNIQUE constraint on claim_id)
- Deterministic idempotency key: `claim:{claim_id}:payment:v1`
- Ledger entries have unique idempotency keys to prevent double-posting
- Retry operations check existing state before creating new entries

## Phase 3.1: Hardening + Product Updates

### Claim Tokenization

Every claim gets a unique, non-guessable `claim_token` in the format `SB-CLM-<8 chars base32>`.

- Generated at claim creation time
- Immutable and indexed for fast lookups
- Displayed in both Internal Console and Practice Portal
- Can be used for filtering in Practice Portal

### Practice Portal Filters

The Practice Portal now supports server-enforced filtering:

```bash
# Filter by claim token
curl "http://localhost:8000/practice/claims?claim_token=SB-CLM-A3B7C9D2" \
  -H "Authorization: Bearer $PM_TOKEN"

# Filter by date range
curl "http://localhost:8000/practice/claims?submitted_from=2026-01-01&submitted_to=2026-01-31" \
  -H "Authorization: Bearer $PM_TOKEN"

# Search across patient name, payer, external claim ID
curl "http://localhost:8000/practice/claims?q=John" \
  -H "Authorization: Bearer $PM_TOKEN"

# Pagination
curl "http://localhost:8000/practice/claims?page=1&page_size=20" \
  -H "Authorization: Bearer $PM_TOKEN"
```

All filters are optional and composable. Results are always tenant-scoped and ordered by most recent first.

### Running Tests

```bash
# Run all tests
source .venv/bin/activate
pytest tests/ -v

# Run payment-specific tests
pytest tests/test_payments.py -v

# Run tenant isolation tests
pytest tests/test_tenant_isolation.py -v
```

### UI Improvements

- **Theme Parity**: Internal Console now uses the same light theme (ChatGPT colorway) as Practice Portal
- **Role Badge**: Both UIs display the current user's role (Admin/Ops/Practice Manager)
- **Claim Token Display**: Claim tokens shown in list views and detail dialogs

## Phase 4: Practice Onboarding

Phase 4 introduces a pre-account onboarding and underwriting intake flow for practices. This flow occurs BEFORE username/password creation and BEFORE Practice Portal access.

### Onboarding Flow Overview

1. **Practice applies** via public intake form (no authentication required)
2. **Application submitted** with status SUBMITTED
3. **Ops reviews** application in Internal Console
4. **On approval**: Practice and Practice Manager user created automatically
5. **On decline**: Application closed, no accounts created

### Starting the Intake Form

```bash
cd spoonbill-intake-frontend
npm install
npm run dev
```

Access the public intake form at: http://localhost:5175

### Application Statuses

- **SUBMITTED**: Application received, awaiting review
- **NEEDS_INFO**: Ops requested additional information from applicant
- **APPROVED**: Application approved, practice and manager created
- **DECLINED**: Application rejected, no accounts created

### Public Intake API

```bash
# Submit a practice application (no auth required)
curl -X POST http://localhost:8000/apply \
  -H "Content-Type: application/json" \
  -d '{
    "legal_name": "Downtown Family Dentistry",
    "address": "123 Main St, Suite 100, Anytown, ST 12345",
    "phone": "555-123-4567",
    "practice_type": "GENERAL_DENTISTRY",
    "years_in_operation": 5,
    "provider_count": 3,
    "operatory_count": 6,
    "avg_monthly_collections_range": "$100,000 - $250,000",
    "insurance_vs_self_pay_mix": "75% Insurance / 25% Self-Pay",
    "billing_model": "IN_HOUSE",
    "urgency_level": "MEDIUM",
    "contact_name": "Jane Smith",
    "contact_email": "jane@downtown-dental.com"
  }'

# Check application status (requires application ID and email)
curl "http://localhost:8000/apply/status/1?email=jane@downtown-dental.com"
```

### Internal Ops Review API

```bash
# List all applications (requires Spoonbill role)
curl http://localhost:8000/internal/applications \
  -H "Authorization: Bearer $TOKEN"

# Get application details
curl http://localhost:8000/internal/applications/1 \
  -H "Authorization: Bearer $TOKEN"

# Approve application (creates practice + manager)
curl -X POST http://localhost:8000/internal/applications/1/review \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "APPROVE", "review_notes": "Verified practice information"}'

# Request more information
curl -X POST http://localhost:8000/internal/applications/1/review \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "NEEDS_INFO", "review_notes": "Please provide tax ID"}'

# Decline application
curl -X POST http://localhost:8000/internal/applications/1/review \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "DECLINE", "review_notes": "Does not meet minimum requirements"}'
```

### Approval Flow Details

When an application is approved:

1. A new Practice is created with the legal name from the application
2. A new PRACTICE_MANAGER user is created with the contact email (with a random, never-shown password)
3. A one-time invite token is generated (expires in 7 days)
4. The application is linked to the created practice for audit purposes
5. Audit events are logged for application approval, practice creation, and user creation

The Ops user receives an invite link that they share with the practice manager. The link goes to a set-password page where the manager creates their own password.

### Invite Token Flow

1. **Ops approves application** → Invite token generated
2. **Ops copies invite link** → `http://localhost:5175/set-password/{token}`
3. **Practice manager opens link** → Token validated, set-password form shown
4. **Manager sets password** → Token marked as used, account activated
5. **Manager logs in** → Practice Portal at http://localhost:5174

Invite tokens are:
- Single-use (cannot be reused after password is set)
- Time-limited (expire after 7 days)
- Secure (64-character random token)

### Security Hardening

The public `/apply` endpoint includes several protections:

**Rate Limiting**: IP-based rate limiting (5 requests per hour per IP) prevents abuse.

**Input Validation**: Server-side validation enforces max length constraints, required fields, and email/phone format checks.

**Honeypot Field**: A hidden `company_url` field catches spam bots. If filled, the submission appears to succeed but is silently rejected.

**Rejection Logging**: All rejected submissions are logged with the reason (no sensitive data logged).

### Internal Console Applications Queue

The Internal Console now has an "Applications" tab that shows:

- All practice applications sorted by urgency (CRITICAL first) then by submission date
- Quick view of application status, urgency, and contact info
- Detailed review dialog with full application data
- Approve/Decline/Request Info actions with optional notes

### Application Fields

The intake form collects comprehensive practice information:

**Practice Information**: Legal name, address, phone, website, tax ID, practice type

**Operations**: Years in operation, provider count, operatory count

**Financial**: Monthly collections range, insurance vs self-pay mix, top payers, average AR days

**Billing**: Billing model (in-house/outsourced/hybrid), follow-up frequency, practice management software, claims per month, electronic claims

**Application Details**: Stated goal, urgency level

**Contact**: Name, email, phone (this person becomes the Practice Manager)

## Internal Console: Practices Tab + Invite Management + Search

The Internal Console now includes enhanced features for managing practices and searching claims.

### Practices Tab

The new "Practices" tab in the Internal Console provides:

- **Practice List**: View all approved practices with summary info (name, status, claim count, primary manager email)
- **Active Invite Status**: See at a glance which practices have active invite links
- **Copy Invite Link**: One-click copy of the active invite link for sharing with practice managers
- **Practice Detail View**: Full practice details including all managers and complete invite history
- **Reissue Invite**: Generate a new invite link (automatically expires any existing active invites)

### Practices API Endpoints

```bash
# List all practices (requires Spoonbill role)
curl http://localhost:8000/api/practices \
  -H "Authorization: Bearer $TOKEN"

# Search practices by name, ID, or manager email
curl "http://localhost:8000/api/practices?q=downtown" \
  -H "Authorization: Bearer $TOKEN"

# Get practice details with managers and invite history
curl http://localhost:8000/api/practices/1 \
  -H "Authorization: Bearer $TOKEN"

# List all invites for a practice
curl http://localhost:8000/api/practices/1/invites \
  -H "Authorization: Bearer $TOKEN"

# Reissue invite (expires old invites, creates new one)
curl -X POST http://localhost:8000/api/practices/1/invites/reissue \
  -H "Authorization: Bearer $TOKEN"
```

### Claims Search

The Claims tab now includes a search bar that searches across:

- Claim ID (exact match)
- Claim token (partial match)
- Patient name (case-insensitive)
- Payer (case-insensitive)
- Practice name (case-insensitive)

When searching, the status filter tabs are hidden and all matching claims are shown. Clear the search to return to the filtered view.

### Audit Events

New audit events for invite management:

- `PRACTICE_INVITE_REISSUED`: Logged when an invite is reissued, includes practice ID, user email, and count of expired invites

## Deploying to Render (Staging)

This section covers deploying Spoonbill to Render with the backend API and all three frontend applications.

### Prerequisites

- A Render account
- The backend API already deployed (or use the render.yaml blueprint)

### Backend API Deployment

If not already deployed, create a new Web Service on Render:

| Setting | Value |
|---------|-------|
| Root Directory | (leave empty) |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/health` |

**Required Environment Variables:**

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (from Render PostgreSQL) |
| `JWT_SECRET_KEY` | Secure random string for JWT signing |
| `ADMIN_EMAIL` | Initial admin email |
| `ADMIN_PASSWORD` | Initial admin password |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of frontend URLs (see below) |

### Frontend Deployments

Deploy each frontend as a Render Static Site:

#### Internal Console (spoonbill-frontend)

| Setting | Value |
|---------|-------|
| Root Directory | `spoonbill-frontend` |
| Build Command | `npm install && npm run build` |
| Publish Directory | `dist` |

**Environment Variables:**

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://your-backend-api.onrender.com` |

**Rewrite Rules** (for SPA routing):
- Source: `/*`
- Destination: `/index.html`

#### Practice Portal (spoonbill-practice-frontend)

| Setting | Value |
|---------|-------|
| Root Directory | `spoonbill-practice-frontend` |
| Build Command | `npm install && npm run build` |
| Publish Directory | `dist` |

**Environment Variables:**

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://your-backend-api.onrender.com` |

**Rewrite Rules** (for SPA routing):
- Source: `/*`
- Destination: `/index.html`

#### Intake Frontend (spoonbill-intake-frontend)

| Setting | Value |
|---------|-------|
| Root Directory | `spoonbill-intake-frontend` |
| Build Command | `npm install && npm run build` |
| Publish Directory | `dist` |

**Environment Variables:**

| Variable | Value |
|----------|-------|
| `VITE_API_BASE_URL` | `https://your-backend-api.onrender.com` |

**Rewrite Rules** (for SPA routing):
- Source: `/*`
- Destination: `/index.html`

### Configuring CORS

After deploying the frontends, update the backend's `CORS_ALLOWED_ORIGINS` environment variable with the deployed frontend URLs:

```
CORS_ALLOWED_ORIGINS=https://spoonbill-console.onrender.com,https://spoonbill-portal.onrender.com,https://spoonbill-intake.onrender.com
```

The backend automatically includes localhost origins for local development, so you only need to add the production/staging URLs.

### Using render.yaml Blueprint

Alternatively, you can use the included `render.yaml` blueprint to deploy all services at once:

1. Go to Render Dashboard → Blueprints
2. Connect your repository
3. Render will detect `render.yaml` and create all services
4. Set the required environment variables for each service

The blueprint defines:
- `spoonbill-api`: Backend web service
- `spoonbill-console`: Internal Console static site
- `spoonbill-portal`: Practice Portal static site
- `spoonbill-intake`: Intake Frontend static site
- `spoonbill-db`: PostgreSQL database

### Verifying Deployment

After deployment, verify the services are running:

```bash
# Check backend health
curl https://your-backend-api.onrender.com/
# Expected: {"status":"ok","service":"spoonbill-api"}

curl https://your-backend-api.onrender.com/health
# Expected: {"status":"healthy","version":"4.0.0","database":"connected"}

# Check API docs
# Open: https://your-backend-api.onrender.com/docs
```

### Troubleshooting

**CORS errors**: Ensure `CORS_ALLOWED_ORIGINS` includes the exact frontend URLs (no trailing slashes).

**API not found**: Verify `VITE_API_BASE_URL` is set correctly in each frontend's environment variables. The value must be set at build time (Vite embeds it during build).

**Database connection errors**: Check that `DATABASE_URL` is correctly set and the database is accessible from the backend service.
