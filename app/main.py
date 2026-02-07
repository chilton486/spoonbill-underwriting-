from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth_router, claims_router, users_router, practice_router, payments_router, applications_router

app = FastAPI(
    title="Spoonbill Internal System of Record",
    description="Phase 4: Practice Onboarding with underwriting intake flow",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(claims_router)
app.include_router(users_router)
app.include_router(practice_router)
app.include_router(payments_router)
app.include_router(applications_router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "4.0.0"}
