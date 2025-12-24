from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime


class DemandItemBase(BaseModel):
    student_id: UUID
    fee_structure_item_id: Optional[UUID] = None
    fee_structure_id: Optional[UUID] = None
    amount: float
    status: Optional[str] = "pending"


class DemandBatchCreate(BaseModel):
    name: str
    institution_id: UUID
    admission_year_id: Optional[UUID] = None
    fee_structure_id: Optional[UUID] = None
    filters: Optional[dict] = None  # filtering criteria for bulk demand


class DemandBatchResponse(BaseModel):
    id: UUID
    name: str
    institution_id: UUID
    admission_year_id: Optional[UUID] = None
    fee_structure_id: Optional[UUID] = None
    filters: Optional[dict] = None
    status: str
    generated_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DemandItemResponse(DemandItemBase):
    id: UUID
    batch_id: UUID
    invoice_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True
