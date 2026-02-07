# Spoonbill Internal System of Record

Phase 1 & 2 implementation of the Spoonbill claim lifecycle management system with authentication, underwriting, audit trail, and multi-tenant Practice Portal.

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
