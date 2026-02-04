from datetime import datetime
from pydantic import BaseModel

from ..models.user import UserRole


class UserCreate(BaseModel):
    email: str
    password: str
    role: UserRole = UserRole.OPS


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
