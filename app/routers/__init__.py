from .auth import router as auth_router
from .claims import router as claims_router
from .users import router as users_router
from .practice import router as practice_router
from .payments import router as payments_router
from .applications import router as applications_router

__all__ = ["auth_router", "claims_router", "users_router", "practice_router", "payments_router", "applications_router"]
