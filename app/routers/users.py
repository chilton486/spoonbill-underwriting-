from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import User, UserRole
from ..models.practice import Practice
from ..schemas.user import UserCreate, UserResponse, PracticeManagerCreate
from ..schemas.practice import PracticeCreate, PracticeResponse, PracticeListResponse
from ..services.auth import AuthService
from .auth import require_spoonbill_admin

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_admin),
):
    existing = AuthService.get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    
    if user_data.practice_id:
        practice = db.query(Practice).filter(Practice.id == user_data.practice_id).first()
        if not practice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Practice not found",
            )
    
    user = AuthService.create_user(
        db,
        email=user_data.email,
        password=user_data.password,
        role=user_data.role,
        practice_id=user_data.practice_id,
    )
    return user


@router.post("/practices", response_model=PracticeResponse, status_code=status.HTTP_201_CREATED)
def create_practice(
    practice_data: PracticeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_admin),
):
    practice = Practice(name=practice_data.name)
    db.add(practice)
    db.commit()
    db.refresh(practice)
    return practice


@router.get("/practices", response_model=List[PracticeListResponse])
def list_practices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_admin),
):
    return db.query(Practice).order_by(Practice.created_at.desc()).all()


@router.post("/practice-managers", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_practice_manager(
    user_data: PracticeManagerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_admin),
):
    existing = AuthService.get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )
    
    practice = db.query(Practice).filter(Practice.id == user_data.practice_id).first()
    if not practice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Practice not found",
        )
    
    user = AuthService.create_user(
        db,
        email=user_data.email,
        password=user_data.password,
        role=UserRole.PRACTICE_MANAGER,
        practice_id=user_data.practice_id,
    )
    return user


@router.get("", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_admin),
):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_admin),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_spoonbill_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user
