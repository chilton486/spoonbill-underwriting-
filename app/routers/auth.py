import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models.user import User, UserRole
from ..schemas.auth import Token
from ..schemas.user import UserResponse
from ..services.auth import AuthService
from ..services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

SPOONBILL_ROLES = {UserRole.SPOONBILL_ADMIN.value, UserRole.SPOONBILL_OPS.value}

auth_rate_limiter = RateLimiter(max_requests=10, window_seconds=300)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    payload = AuthService.decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = AuthService.get_user_by_id(db, int(user_id))
    if not user or not user.is_active:
        return None
    return user


def require_auth(
    current_user: Optional[User] = Depends(get_current_user),
) -> User:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_spoonbill_admin(
    current_user: User = Depends(require_auth),
) -> User:
    if current_user.role != UserRole.SPOONBILL_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Spoonbill Admin access required",
        )
    return current_user


def require_spoonbill_user(
    current_user: User = Depends(require_auth),
) -> User:
    if current_user.role not in SPOONBILL_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Spoonbill employee access required",
        )
    return current_user


# Alias for require_spoonbill_user
require_spoonbill_role = require_spoonbill_user


def require_practice_manager(
    current_user: User = Depends(require_auth),
) -> User:
    if current_user.role != UserRole.PRACTICE_MANAGER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Practice Manager access required",
        )
    if not current_user.practice_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Practice Manager must be associated with a practice",
        )
    return current_user


def get_current_practice_scope(current_user: User = Depends(require_auth)) -> Optional[int]:
    if current_user.role in SPOONBILL_ROLES:
        return None
    if current_user.role == UserRole.PRACTICE_MANAGER.value:
        return current_user.practice_id
    return None


def get_practice_ids_for_user(current_user: User) -> Optional[List[int]]:
    if current_user.role in SPOONBILL_ROLES:
        return None
    if current_user.role == UserRole.PRACTICE_MANAGER.value and current_user.practice_id:
        return [current_user.practice_id]
    return []


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    allowed, remaining = auth_rate_limiter.is_allowed(client_ip)
    if not allowed:
        logger.warning(f"Auth rate limit exceeded: ip={client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )
    auth_rate_limiter.record_request(client_ip)

    user = AuthService.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        logger.info(f"Failed login attempt: email={form_data.username} ip={client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
        )
    token_data = {"sub": str(user.id), "email": user.email, "role": user.role}
    if user.practice_id:
        token_data["practice_id"] = user.practice_id
    access_token = AuthService.create_access_token(data=token_data)
    logger.info(f"Successful login: user_id={user.id} email={user.email} role={user.role}")
    return Token(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(require_auth)):
    return current_user
