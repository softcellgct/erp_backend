from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel


class DemandFilterSchema(BaseModel):
    institution_id: UUID
    department: Optional[str] = None
    course: Optional[str] = None
    batch: Optional[str] = None  # Maps to 'year' or 'batch' field in student/fee structure
    admission_quota: Optional[str] = None  # Government, Management
    category: Optional[str] = None  # BC, MBC, SC, etc.
    gender: Optional[str] = None
    quota_type: Optional[str] = None  # Sports, etc.
    special_quota: Optional[str] = None
    scholarships: Optional[str] = None
    boarding_place: Optional[str] = None  # Hostel logic if needed


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
    fee_structure_id: UUID
    filters: DemandFilterSchema
    apply_to_students: Optional[List[UUID]] = None


class DemandPreviewResponse(BaseModel):
    student_count: int
    total_amount: float
    message: str
    sample_students: List[Dict[str, Any]] = []


class DemandBatchResponse(BaseModel):
    id: UUID
    name: str
    institution_id: UUID
    admission_year_id: Optional[UUID] = None
    fee_structure_id: Optional[UUID] = None
    filters: Optional[Dict[str, Any]] = None
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


class BulkMiscellaneousFeeRequest(BaseModel):
    student_ids: List[UUID]
    fee_head_id: Optional[UUID] = None
    amount: float
    description: str
