# Spoonbill Internal System of Record

Phase 1 implementation of the Spoonbill claim lifecycle management system with authentication, underwriting, and audit trail.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker and Docker Compose (for PostgreSQL)

### 1. Start PostgreSQL

```bash
# Start only the database container
docker-compose up -d db
```

This starts a PostgreSQL container on port 5432 with database `spoonbill`.

### 2. Set up Backend

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
# IMPORTANT: Edit .env and set ADMIN_PASSWORD before proceeding
```

### 3. Run Database Migrations

```bash
alembic upgrade head
```

### 4. Seed Initial Admin User

```bash
# Set your admin password (required)
export ADMIN_PASSWORD='your-secure-password-here'

# Create the admin user
python -m app.cli
```

**CLI Behavior:**
- If the admin user doesn't exist, it creates one with the email from `ADMIN_EMAIL` (default: admin@spoonbill.com)
- If the admin user already exists, it prints a message and exits successfully (idempotent)
- If `ADMIN_PASSWORD` is not set, it exits with an error

### 5. Start Backend

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### 6. Start Frontend

```bash
cd spoonbill-frontend
npm install
npm run dev
```

### 7. Access the Application

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

Login with the admin email and the password you set in `ADMIN_PASSWORD`.

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
| ADMIN_PASSWORD | Initial admin password | **Required - no default** |

## Claim Lifecycle

Claims follow this state machine:

```
NEW → NEEDS_REVIEW → APPROVED → PAID → COLLECTING → CLOSED
  ↓        ↓            ↓
  └────────┴────────────┴──→ DECLINED
```

### Status Definitions

- **NEW**: Initial status when claim is created (transient - underwriting runs immediately)
- **NEEDS_REVIEW**: Underwriting flagged for manual review (amount exceeds threshold, missing fields)
- **APPROVED**: Underwriting approved, ready for payment
- **PAID**: Payment sent to practice
- **COLLECTING**: Collecting from payer
- **CLOSED**: Claim fully resolved
- **DECLINED**: Claim rejected (duplicate or manual decline)

**Note:** When a claim is created via `POST /api/claims`, underwriting runs automatically and the claim transitions from NEW to APPROVED, NEEDS_REVIEW, or DECLINED within the same request. The NEW status is transient and you typically won't see claims in NEW status in the UI.

## Duplicate Detection

Claims are deduplicated using a fingerprint computed from:
- `practice_id` (nullable - treated as empty string if null)
- `patient_name` (nullable - treated as empty string if null)
- `procedure_date` (nullable - treated as empty string if null)
- `amount_cents` (required)
- `payer` (required)

**Important:** Since `practice_id` is nullable, two claims without a practice_id but with the same patient_name, procedure_date, amount_cents, and payer will be considered duplicates. If you need stronger duplicate detection, always provide `practice_id`.

## Reproduce Phase 1 Flow

Here's a complete curl-based walkthrough to verify the system works:

```bash
# 1. Login and get token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@spoonbill.com&password=YOUR_PASSWORD" | jq -r '.access_token')

echo "Token: $TOKEN"

# 2. Create a claim (underwriting runs automatically)
# Expected: claim created with status APPROVED (amount below threshold)
curl -s -X POST http://localhost:8000/api/claims \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payer": "Aetna",
    "amount_cents": 15000,
    "patient_name": "John Doe",
    "procedure_date": "2026-01-15",
    "practice_id": "PRAC-001",
    "procedure_codes": "D0120, D1110"
  }' | jq .

# Expected response includes:
# - "status": "APPROVED" (auto-approved, amount < $1000 threshold)
# - "underwriting_decisions": array with APPROVE decision
# - "audit_events": array with CLAIM_CREATED, UNDERWRITING_DECISION, STATUS_CHANGE

# 3. Create a claim that requires review (amount > threshold)
curl -s -X POST http://localhost:8000/api/claims \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payer": "BCBS",
    "amount_cents": 150000,
    "patient_name": "Jane Smith",
    "procedure_date": "2026-01-16",
    "practice_id": "PRAC-002"
  }' | jq .

# Expected: "status": "NEEDS_REVIEW" (amount > $1000 threshold)

# 4. List all claims
curl -s http://localhost:8000/api/claims \
  -H "Authorization: Bearer $TOKEN" | jq .

# 5. Get valid transitions for claim 1
curl -s http://localhost:8000/api/claims/1/transitions \
  -H "Authorization: Bearer $TOKEN" | jq .

# Expected: {"claim_id": 1, "current_status": "APPROVED", "valid_transitions": ["PAID", "DECLINED"]}

# 6. Transition claim 1 from APPROVED to PAID
curl -s -X POST http://localhost:8000/api/claims/1/transition \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to_status": "PAID", "reason": "Payment processed"}' | jq .

# Expected: status changes to PAID, new audit event added

# 7. View claim detail with full audit trail
curl -s http://localhost:8000/api/claims/1 \
  -H "Authorization: Bearer $TOKEN" | jq .

# Expected: audit_events array shows:
# - CLAIM_CREATED (NEW)
# - UNDERWRITING_DECISION
# - STATUS_CHANGE (NEW → APPROVED)
# - STATUS_CHANGE (APPROVED → PAID)

# 8. Manually approve the NEEDS_REVIEW claim
curl -s -X POST http://localhost:8000/api/claims/2/transition \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"to_status": "APPROVED", "reason": "Manual approval after review"}' | jq .

# 9. Try to create a duplicate claim (should fail)
curl -s -X POST http://localhost:8000/api/claims \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payer": "Aetna",
    "amount_cents": 15000,
    "patient_name": "John Doe",
    "procedure_date": "2026-01-15",
    "practice_id": "PRAC-001"
  }' | jq .

# Expected: 409 Conflict with "Duplicate claim detected"
```

## Underwriting Rules

The rules-based underwriting engine evaluates claims automatically:

1. **Missing payer** → NEEDS_REVIEW
2. **Missing amount** → NEEDS_REVIEW
3. **Duplicate claim** → DECLINE (based on fingerprint)
4. **Amount > threshold** (default $1000) → NEEDS_REVIEW
5. **Amount < auto-approve threshold** (default $100) → APPROVE (auto)
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
│   ├── state_machine.py     # Claim status transition validation
│   ├── cli.py               # CLI commands (seed admin - idempotent)
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

- **ADMIN**: Can manage users (create, deactivate) and perform all operations
- **OPS**: Can view claims, run underwriting, and transition claim statuses
