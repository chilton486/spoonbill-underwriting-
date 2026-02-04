from datetime import datetime
from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    id: int
    claim_id: int
    practice_id: int
    filename: str
    content_type: str
    uploaded_by_user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    id: int
    filename: str
    content_type: str
    created_at: datetime

    class Config:
        from_attributes = True
