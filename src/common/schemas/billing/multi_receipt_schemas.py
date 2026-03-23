from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MultiReceiptStudentFilterRequest(BaseModel):
    institution_id: UUID
    fee_head_id: UUID
    fee_sub_head_id: Optional[UUID] = None
    scholarship_type: Optional[str] = None
    scholarship_received_only: bool = True
    academic_year_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    course_id: Optional[UUID] = None
    batch: Optional[str] = None
    gender: Optional[str] = None
    admission_quota_id: Optional[UUID] = None


class EligibleMultiReceiptStudent(BaseModel):
    student_id: UUID
    application_number: Optional[str] = None
    student_name: str
    department_name: Optional[str] = None
    course_name: Optional[str] = None
    academic_year_id: Optional[UUID] = None
    scholarship_type: Optional[str] = None
    outstanding_amount: Decimal


class EligibleMultiReceiptStudentResponse(BaseModel):
    count: int
    students: list[EligibleMultiReceiptStudent]


class GenerateMultiReceiptRequest(BaseModel):
    institution_id: UUID
    fee_head_id: UUID
    fee_sub_head_id: Optional[UUID] = None
    student_ids: list[UUID] = Field(..., min_length=1)
    amount_per_student: Decimal = Field(..., gt=0)
    payer_type: str = "GOVERNMENT"
    payment_method: str = "MULTI_RECEIPT"
    payment_date: Optional[datetime] = None
    description: Optional[str] = None


class MultiReceiptItemResponse(BaseModel):
    student_id: UUID
    student_name: Optional[str] = None
    demand_item_id: Optional[UUID] = None
    invoice_id: Optional[UUID] = None
    payment_id: Optional[UUID] = None
    paid_amount: Decimal


class GenerateMultiReceiptResponse(BaseModel):
    multi_receipt_id: UUID
    receipt_number: str
    student_count: int
    amount_per_student: Decimal
    total_amount: Decimal
    items: list[MultiReceiptItemResponse]
    skipped_students: list[dict] = []


class MultiReceiptSummary(BaseModel):
    id: UUID
    receipt_number: str
    institution_id: UUID
    fee_head_id: Optional[UUID] = None
    fee_sub_head_id: Optional[UUID] = None
    payer_type: str
    student_count: int
    amount_per_student: Decimal
    total_amount: Decimal
    payment_date: datetime
    status: str


class MultiReceiptDetail(BaseModel):
    id: UUID
    receipt_number: str
    institution_id: UUID
    fee_head_id: Optional[UUID] = None
    fee_sub_head_id: Optional[UUID] = None
    payer_type: str
    student_count: int
    amount_per_student: Decimal
    total_amount: Decimal
    payment_date: datetime
    description: Optional[str] = None
    status: str
    items: list[MultiReceiptItemResponse]
