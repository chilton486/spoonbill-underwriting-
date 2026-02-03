# Spoonbill Internal System of Record

Phase 1 implementation of the Spoonbill claim lifecycle management system with authentication, underwriting, and audit trail.

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

### 4. Start Frontend

```bash
cd spoonbill-frontend
npm install
npm run dev
```

### 5. Access the Application

- Frontend: http://localhost:5173
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

- **ADMIN**: Can manage users (create, deactivate) and perform all operations
- **OPS**: Can view claims, run underwriting, and transition claim statuses
