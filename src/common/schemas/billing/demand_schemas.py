from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


class DemandFilterSchema(BaseModel):
    # Primary canonical filters (ID-based where possible)
    admission_year_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    degree_id: Optional[UUID] = None
    batch: Optional[str] = None
    gender: Optional[str] = None
    admission_quota_id: Optional[UUID] = None
    category: Optional[str] = None
    quota_type: Optional[str] = None  # Sports, etc.
    special_quota: Optional[str] = None
    scholarships: Optional[str] = None
    boarding_place: Optional[str] = None  # Hostel logic if needed

    # Optional multi-value variants for broad filter support
    department_ids: Optional[List[UUID]] = None
    degree_ids: Optional[List[UUID]] = None
    batches: Optional[List[str]] = None
    genders: Optional[List[str]] = None

    # Backward-compatibility keys from older payloads/UI
    department: Optional[str] = None
    course: Optional[str] = None
    admission_quota: Optional[str] = None


class DemandItemBase(BaseModel):
    student_id: UUID
    fee_structure_item_id: Optional[UUID] = None
    fee_structure_id: Optional[UUID] = None
    amount: float
    status: Optional[str] = "pending"


class DemandBatchCreate(BaseModel):
    name: Optional[str] = None
    institution_id: UUID
    admission_year_id: Optional[UUID] = None
    fee_structure_id: UUID
    filters: Optional[DemandFilterSchema] = None
    apply_to_students: Optional[List[UUID]] = None


class DemandPreviewResponse(BaseModel):
    # canonical keys
    student_count: int = 0
    total_amount: float = 0.0
    # backward-compatible aliases currently used by UI
    count: int = 0
    total: float = 0.0
    message: str
    sample_students: List[Dict[str, Any]] = Field(default_factory=list)


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
