import logging
import os

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from .routers import auth_router, claims_router, users_router, practice_router, payments_router, applications_router, internal_practices_router, ontology_router
from .database import get_db
from .config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

_cors_origins = settings.get_cors_origins()
logger.info("CORS allowed origins: %s", _cors_origins)
print(f"[startup] CORS allowed origins: {_cors_origins}")

app = FastAPI(
    title="Spoonbill Internal System of Record",
    description="Phase 4: Practice Onboarding with underwriting intake flow",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(auth_router)
app.include_router(claims_router)
app.include_router(users_router)
app.include_router(practice_router)
app.include_router(payments_router)
app.include_router(applications_router)
app.include_router(internal_practices_router)
app.include_router(ontology_router)


@app.get("/")
def root():
    """Root endpoint - confirms API is running."""
    return {"status": "ok", "service": "spoonbill-api"}


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint with database connectivity verification."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "version": "4.0.0",
        "database": db_status,
    }


@app.get("/diag")
def diagnostics(db: Session = Depends(get_db)):
    """Runtime diagnostics endpoint (no secrets exposed)."""
    alembic_revision = None
    try:
        result = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        row = result.fetchone()
        if row:
            alembic_revision = row[0]
    except Exception:
        alembic_revision = "unknown"

    return {
        "ok": True,
        "cors_allow_origins": _cors_origins,
        "cors_allow_methods": ["*"],
        "cors_allow_headers": ["*"],
        "cors_allow_credentials": False,
        "environment": os.environ.get("RENDER", "local"),
        "alembic_revision": alembic_revision,
    }
