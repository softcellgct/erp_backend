from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class FeeStructureItemBase(BaseModel):
    fee_head_id: Optional[UUID] = None
    fee_sub_head_id: UUID
    amount: Decimal
    amount_by_year: Optional[dict] = None  # {"1": 1000, "2": 1000}
    order: Optional[int] = None


class FeeStructureItemCreate(FeeStructureItemBase):
    pass


class FeeStructureItemResponse(FeeStructureItemBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeeStructureBase(BaseModel):
    name: str
    institution_id: UUID
    financial_year_id: Optional[UUID] = None
    admission_year_id: Optional[UUID] = None
    degree_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    course_duration_years: Optional[int] = 1
    fg_applicable: Optional[bool] = False
    sc_st_scholarship: Optional[bool] = False
    batch: Optional[str] = None
    status: Optional[bool] = True
    meta: Optional[dict] = None


class FeeStructureCreate(FeeStructureBase):
    items: Optional[List[FeeStructureItemCreate]] = []


class FeeStructureUpdate(BaseModel):
    id: UUID
    name: Optional[str] = None
    financial_year_id: Optional[UUID] = None
    admission_year_id: Optional[UUID] = None
    degree_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    course_duration_years: Optional[int] = None
    fg_applicable: Optional[bool] = None
    sc_st_scholarship: Optional[bool] = None
    batch: Optional[str] = None
    status: Optional[bool] = None
    items: Optional[List[FeeStructureItemCreate]] = None


class FeeStructureResponse(FeeStructureBase):
    id: UUID
    items: Optional[List[FeeStructureItemResponse]] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeeStructureListResponse(BaseModel):
    id: UUID
    name: str
    institution_id: UUID
    admission_year_id: Optional[UUID] = None
    degree_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    status: bool
    created_at: datetime

    class Config:
        from_attributes = True
