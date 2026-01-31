# Spoonbill Underwriting & Capital Allocation

Spoonbill provides same-day liquidity for approved dental insurance claims. This demo showcases the core financial engine: deterministic underwriting, atomic capital allocation, and real-time claim lifecycle tracking.

## Business Model (For Investors)

1. **Practices submit** dental insurance claims
2. **Spoonbill underwrites** risk using deterministic rules
3. **Capital is deployed** same-day to the practice
4. **Insurer reimburses** Spoonbill days later
5. **Spoonbill earns** basis-point fees on the liquidity provided

This is not RCM, collections, or a billing tool. It's a capital deployment engine for healthcare receivables.

## Running the Demo

### Prerequisites
- Python 3.10+
- Node.js 18+

### Start the Backend

```bash
cd /path/to/spoonbill-underwriting
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Start the Frontend

```bash
cd spoonbill-frontend
npm install
npm run dev
```

Then open http://localhost:5173 in your browser.

## Demo Walkthrough

### What Investors Should Notice

1. **Capital Pool Panel** (right side): Shows total capital, available capital, and deployed capital with a visual bar. Watch how these numbers change as claims move through stages.

2. **Claim Lifecycle** (left to right):
   - **Submitted**: Claims awaiting underwriting review
   - **Underwriting**: Risk assessment in progress
   - **Funded**: Capital deployed to practice (shows days outstanding)
   - **Reimbursed**: Insurer has paid back, capital returned
   - **Exception**: Claims requiring attention

3. **Key Interactions**:
   - Click **"Next"** on any claim card to advance it through the lifecycle
   - Click **"Run Simulation Step"** to advance ALL claims one step
   - Click **"Reset Demo"** to return to a clean, deterministic starting state

### Reset Demo

The "Reset Demo" button clears all data and seeds the same 5 dental claims every time:
- 3 dental practices with realistic profiles
- 5 claims at various amounts ($1,480 - $3,600)
- $1M starting capital pool

This ensures consistent, reproducible demos for investor presentations.

## Architecture

### Backend (FastAPI + SQLite)
- `app/models.py`: Domain models (Practice, Claim, CapitalPool)
- `app/underwriting.py`: Deterministic underwriting rules
- `app/ledger.py`: Atomic capital movements with invariant checks
- `app/main.py`: REST API endpoints

### Frontend (React + Vite + MUI)
- Kanban-style claim lifecycle visualization
- Real-time capital pool metrics
- Loading states and success feedback on all actions

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/reset` | POST | Reset demo to deterministic starting state |
| `/simulate` | POST | Seed data and/or advance claims one step |
| `/claims` | GET | List all claims |
| `/claims/{id}/underwrite` | POST | Move claim to underwriting |
| `/claims/{id}/fund` | POST | Deploy capital for claim |
| `/claims/{id}/settle` | POST | Record insurer reimbursement |
| `/capital-pool/{id}` | GET | Get capital pool metrics |
| `/state` | GET | Get full system state |

## Development Notes

This project uses Python 3.10+ and Node.js 18+ for development.

The demo prioritizes clarity over production-readiness:
- SQLite for simplicity (no Postgres setup required)
- In-memory state resets on server restart
- Simplified underwriting rules for demo purposes
- No authentication (demo only)
