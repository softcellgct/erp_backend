from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class StudentScholarshipCreate(BaseModel):
    student_id: UUID
    institution_id: UUID
    fee_structure_id: Optional[UUID] = None
    academic_year_id: Optional[UUID] = None
    scholarship_type: str  # FG, SC_ST, BC, MBC, CUSTOM
    amount: Decimal = 0
    certificate_file: Optional[str] = None
    meta: Optional[dict] = None


class StudentScholarshipUpdate(BaseModel):
    certificate_status: Optional[str] = None
    certificate_file: Optional[str] = None
    amount: Optional[Decimal] = None
    amount_received: Optional[bool] = None
    rejection_reason: Optional[str] = None
    meta: Optional[dict] = None


class StudentScholarshipResponse(BaseModel):
    id: UUID
    student_id: UUID
    institution_id: UUID
    fee_structure_id: Optional[UUID] = None
    academic_year_id: Optional[UUID] = None
    scholarship_type: str
    certificate_status: str
    certificate_file: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = None
    amount: Decimal
    amount_received: bool
    amount_received_at: Optional[datetime] = None
    receipt_id: Optional[UUID] = None
    rejection_reason: Optional[str] = None
    meta: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    # Nested summary fields (populated in route)
    student_name: Optional[str] = None
    application_number: Optional[str] = None
    department_name: Optional[str] = None
    course_title: Optional[str] = None

    class Config:
        from_attributes = True


class MultiReceiptRequest(BaseModel):
    institution_id: UUID
    scholarship_type: str  # FG, SC_ST, etc.
    academic_year_id: Optional[UUID] = None
    student_ids: Optional[List[UUID]] = None  # If empty, process all qualifying


class MultiReceiptResponse(BaseModel):
    processed_count: int
    total_amount: Decimal
    receipt_numbers: List[str]
    failed_count: int
    failed_details: Optional[List[dict]] = None


class ScholarshipDashboardResponse(BaseModel):
    not_submitted: int
    submitted: int
    under_review: int
    approved: int
    rejected: int
    amount_received: int
    receipts_generated: int
    total_amount: Decimal
