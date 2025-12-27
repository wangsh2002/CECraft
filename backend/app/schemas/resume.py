from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ResumeBase(BaseModel):
    title: str
    content: Optional[str] = None

class ResumeCreate(ResumeBase):
    pass

class ResumeUpdate(ResumeBase):
    pass

class Resume(ResumeBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
