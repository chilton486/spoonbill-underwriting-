import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from .routers import auth_router, claims_router, users_router, practice_router, payments_router, applications_router, internal_practices_router, ontology_router, integrations_router
from .database import engine, get_db
from .config import get_settings
from .utils.migrations import run_migrations_if_enabled, get_migration_state

logger = logging.getLogger(__name__)

settings = get_settings()

_cors_origins = settings.get_cors_origins()
logger.info("CORS allowed origins: %s", _cors_origins)
print(f"[startup] CORS allowed origins: {_cors_origins}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations_if_enabled(engine)
    state = get_migration_state(engine)
    print(f"[startup] Migration state: {state}")
    yield


app = FastAPI(
    title="Spoonbill Internal System of Record",
    description="Phase 4: Practice Onboarding with underwriting intake flow",
    version="4.0.0",
    lifespan=lifespan,
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
app.include_router(integrations_router)


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
def diagnostics():
    """Runtime diagnostics endpoint (no secrets exposed)."""
    state = get_migration_state(engine)

    return {
        "ok": True,
        "cors_allow_origins": _cors_origins,
        "cors_allow_methods": ["*"],
        "cors_allow_headers": ["*"],
        "cors_allow_credentials": False,
        "environment": os.environ.get("RENDER", "local"),
        "current_revision": state["current_revision"],
        "head_revision": state["head_revision"],
        "migration_pending": state["migration_pending"],
        "run_migrations_on_startup_enabled": settings.run_migrations_on_startup.lower() == "true",
    }
