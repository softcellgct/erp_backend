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

class ConcessionRuleBase(BaseModel):
    institution_id: UUID
    rule_name: str
    condition_metric: str
    operator: str
    threshold_value: Decimal
    concession_percent: Optional[Decimal] = None
    target_fee_head_id: Optional[UUID] = None
    is_active: bool = True

class ConcessionRuleCreate(ConcessionRuleBase):
    pass

class ConcessionRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    condition_metric: Optional[str] = None
    operator: Optional[str] = None
    threshold_value: Optional[Decimal] = None
    concession_percent: Optional[Decimal] = None
    target_fee_head_id: Optional[UUID] = None
    is_active: Optional[bool] = None

class ConcessionRuleResponse(ConcessionRuleBase):
    id: UUID
    class Config:
        orm_mode = True
        from_attributes = True

