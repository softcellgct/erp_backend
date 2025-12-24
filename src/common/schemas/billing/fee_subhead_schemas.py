from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class FeeSubHeadBase(BaseModel):
    fee_head_id: UUID
    institution_id: UUID
    batch: Optional[str] = None
    name: str
    description: Optional[str] = None
    is_active: Optional[bool] = True
    academic_year_id: Optional[UUID] = None


class FeeSubHeadCreate(FeeSubHeadBase):
    pass


class FeeSubHeadUpdate(BaseModel):
    id: UUID
    fee_head_id: Optional[UUID] = None
    institution_id: Optional[UUID] = None
    batch: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    academic_year_id: Optional[UUID] = None


class FeeSubHeadResponse(FeeSubHeadBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
