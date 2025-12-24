from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class FeeHeadBase(BaseModel):
    institution_id: UUID
    name: str
    description: Optional[str] = None
    # Make optional for existing records; creation requires this field (see FeeHeadCreate)
    is_active: Optional[bool] = True
    # Note: `short_name`, `amount`, and `fee_type` have been removed from FeeHead


class FeeHeadCreate(FeeHeadBase):
    # Require academic_year_id when creating a new FeeHead
    pass

class FeeHeadUpdate(BaseModel):
    id: UUID
    academic_year_id: Optional[UUID] = None
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class FeeHeadResponse(FeeHeadBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
