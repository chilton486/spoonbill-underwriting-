from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from ..models.user import UserRole


class UserCreate(BaseModel):
    email: str
    password: str
    role: UserRole = UserRole.SPOONBILL_OPS
    practice_id: Optional[int] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    practice_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PracticeManagerCreate(BaseModel):
    email: str
    password: str
    practice_id: int
