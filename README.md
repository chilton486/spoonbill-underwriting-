# Spoonbill Underwriting & Capital Allocation (V1)

This repo is a minimal, auditable backend for deterministic underwriting and capital allocation.

## Why this stack

- FastAPI: small surface area, easy to test.
- SQLModel + SQLite: correct-by-default transactional updates with minimal operational overhead.

## Files

- `app/models.py`: canonical domain models (Practice, Claim, CapitalPool).
- `app/underwriting.py`: deterministic underwriting policy + decision function.
- `app/ledger.py`: atomic balance-sheet updates for funding and settlement.
- `app/db.py`: DB engine + transactional session scope.
- `app/main.py`: minimal API to create entities and run claim lifecycle.
- `simulate.py`: example end-to-end flow with fake data.

## Run

Install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run API:

```bash
uvicorn app.main:app --reload
```

Run simulation:

```bash
python simulate.py
```
