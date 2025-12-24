from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime
from decimal import Decimal


class ConcessionBase(BaseModel):
    student_id: UUID
    college_id: UUID
    fee_head_id: Optional[UUID] = None
    fee_sub_head_id: Optional[UUID] = None
    amount: Optional[Decimal] = None
    percent: Optional[Decimal] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof_file: Optional[str] = None
    status: Optional[str] = "pending"
    meta: Optional[dict] = None


class ConcessionCreate(ConcessionBase):
    pass


class ConcessionUpdate(BaseModel):
    id: UUID
    amount: Optional[Decimal] = None
    percent: Optional[Decimal] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    proof_file: Optional[str] = None
    status: Optional[str] = None
    meta: Optional[dict] = None


class ConcessionResponse(ConcessionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConcessionAuditResponse(BaseModel):
    concession_id: UUID
    action: str
    performed_by: Optional[UUID] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
