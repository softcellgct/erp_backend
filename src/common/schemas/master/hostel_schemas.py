from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class HostelBase(BaseModel):
    name: str
    institution_id: UUID
    code: Optional[str] = None
    is_active: Optional[bool] = True
    meta: Optional[dict] = None


class HostelCreate(HostelBase):
    pass


class HostelUpdate(BaseModel):
    id: UUID
    name: Optional[str] = None
    code: Optional[str] = None
    is_active: Optional[bool] = None
    meta: Optional[dict] = None


class HostelResponse(HostelBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
