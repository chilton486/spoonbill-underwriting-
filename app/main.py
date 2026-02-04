from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth_router, claims_router, users_router, practice_router

app = FastAPI(
    title="Spoonbill Internal System of Record",
    description="Phase 2: Multi-tenant practice portal with claim lifecycle management",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
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


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "2.0.0"}
