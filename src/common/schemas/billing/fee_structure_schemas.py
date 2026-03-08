from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class FeeHeadMinimal(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class FeeSubHeadMinimal(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class FeeStructureItemBase(BaseModel):
    fee_head_id: Optional[UUID] = None
    fee_sub_head_id: Optional[UUID] = None
    amount: Decimal = 0
    amount_by_year: Optional[dict] = None  # {"1": 1000, "2": 1000}
    amount_by_semester: Optional[dict] = None  # {"1": 500, "2": 500, "3": 500, "4": 500}
    payer_type: Optional[str] = "STUDENT"  # STUDENT | GOVERNMENT | SCHOLARSHIP
    order: Optional[int] = None


class FeeStructureItemCreate(FeeStructureItemBase):
    pass


class FeeStructureItemResponse(FeeStructureItemBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    fee_head: Optional[FeeHeadMinimal] = None
    fee_sub_head: Optional[FeeSubHeadMinimal] = None

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
    semesters_per_year: Optional[int] = 2
    fg_applicable: Optional[bool] = False
    sc_st_scholarship: Optional[bool] = False
    fg_amount: Optional[Decimal] = None
    sc_st_amount: Optional[Decimal] = None
    fg_amount_by_semester: Optional[dict] = None
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
    semesters_per_year: Optional[int] = None
    fg_applicable: Optional[bool] = None
    sc_st_scholarship: Optional[bool] = None
    fg_amount: Optional[Decimal] = None
    sc_st_amount: Optional[Decimal] = None
    fg_amount_by_semester: Optional[dict] = None
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
