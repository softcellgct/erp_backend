from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime
from decimal import Decimal


class ScholarshipConfigurationCreate(BaseModel):
    institution_id: UUID
    scholarship_type: str  # FG, SC_ST, BC, MBC, STAFF_REFERRAL, MERIT_BASED, NEED_BASED, CUSTOM
    amount: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    fee_head_id: Optional[UUID] = None
    description: Optional[str] = None
    is_active: bool = True
    reduce_from_tuition: bool = False
    meta: Optional[dict] = None


class ScholarshipConfigurationUpdate(BaseModel):
    amount: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    fee_head_id: Optional[UUID] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    reduce_from_tuition: Optional[bool] = None
    meta: Optional[dict] = None


class ScholarshipConfigurationResponse(BaseModel):
    id: UUID
    institution_id: UUID
    scholarship_type: str
    amount: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    fee_head_id: Optional[UUID] = None
    description: Optional[str] = None
    is_active: bool
    reduce_from_tuition: bool
    meta: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StaffReferralConcessionCreate(BaseModel):
    staff_id: UUID
    student_id: UUID
    institution_id: UUID
    concession_amount: Optional[Decimal] = None
    concession_percentage: Optional[Decimal] = None
    fee_head_id: Optional[UUID] = None
    notes: Optional[str] = None
    meta: Optional[dict] = None


class StaffReferralConcessionUpdate(BaseModel):
    concession_amount: Optional[Decimal] = None
    concession_percentage: Optional[Decimal] = None
    fee_head_id: Optional[UUID] = None
    is_applied: Optional[bool] = None
    applied_at: Optional[str] = None
    notes: Optional[str] = None
    meta: Optional[dict] = None


class StaffReferralConcessionResponse(BaseModel):
    id: UUID
    staff_id: UUID
    student_id: UUID
    institution_id: UUID
    concession_amount: Decimal
    concession_percentage: Optional[Decimal] = None
    fee_head_id: Optional[UUID] = None
    is_applied: bool
    applied_at: Optional[str] = None
    notes: Optional[str] = None
    meta: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    # Nested summary fields
    staff_name: Optional[str] = None
    student_name: Optional[str] = None
    fee_head_name: Optional[str] = None

    class Config:
        from_attributes = True
