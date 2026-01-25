# Spoonbill Frontend Demo (React)

This is a demo-ready React UI that connects to the existing FastAPI backend at `http://localhost:8000`.

## Start backend

From the backend folder:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Start frontend

From `spoonbill-frontend/`:

```bash
npm install
npm run dev
```

Then open:

- http://localhost:5173

## Notes

- The UI calls `POST /simulate` on initial load with `seed_if_empty=true` to ensure demo data exists.
- The kanban board polls the backend every ~1.5s so cards move stages after actions/simulation.
