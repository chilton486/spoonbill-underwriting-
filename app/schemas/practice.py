from datetime import datetime
from pydantic import BaseModel


class PracticeCreate(BaseModel):
    name: str


class PracticeResponse(BaseModel):
    id: int
    name: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PracticeListResponse(BaseModel):
    id: int
    name: str
    status: str

    class Config:
        from_attributes = True
