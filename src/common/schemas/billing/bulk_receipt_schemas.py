from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BulkReceiptItemCreate(BaseModel):
    student_id: UUID
    invoice_id: UUID
    amount: float = Field(..., gt=0)


class BulkReceiptCreate(BaseModel):
    institution_id: UUID
    payer_type: str = "GOVERNMENT"  # GOVERNMENT | SCHOLARSHIP
    amount: float = Field(..., gt=0)
    payment_date: Optional[datetime] = None
    reference_number: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    items: List[BulkReceiptItemCreate] = Field(..., min_length=1)


class BulkReceiptItemResponse(BaseModel):
    id: UUID
    bulk_receipt_id: UUID
    invoice_id: UUID
    student_id: UUID
    amount: float
    created_at: datetime

    class Config:
        from_attributes = True


class BulkReceiptResponse(BaseModel):
    id: UUID
    institution_id: UUID
    payer_type: str
    amount: float
    payment_date: datetime
    reference_number: str
    description: Optional[str] = None
    status: str
    items: List[BulkReceiptItemResponse] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True


class BulkReceiptListResponse(BaseModel):
    id: UUID
    institution_id: UUID
    payer_type: str
    amount: float
    payment_date: datetime
    reference_number: str
    status: str
    item_count: Optional[int] = 0
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateBulkReceiptRequest(BaseModel):
    """
    Auto-generate a bulk receipt by finding all unpaid GOVERNMENT/SCHOLARSHIP
    invoices matching the given filters, and creating a single bulk payment.
    """
    institution_id: UUID
    fee_structure_id: UUID
    payer_type: str = "GOVERNMENT"
    semester: Optional[int] = None
    year: Optional[int] = None
    reference_number: str = Field(..., min_length=1, max_length=200)
    payment_date: Optional[datetime] = None
    description: Optional[str] = None


class GenerateBulkReceiptResponse(BaseModel):
    bulk_receipt_id: UUID
    student_count: int
    total_amount: float
    invoice_count: int
    message: str
