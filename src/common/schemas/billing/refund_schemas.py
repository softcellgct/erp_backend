from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime
from decimal import Decimal


class RefundInitiateRequest(BaseModel):
    student_id: UUID
    payment_id: UUID
    cancellation_fee: Decimal
    reason: Optional[str] = None
    refund_method: Optional[str] = None  # CASH, BANK_TRANSFER, UPI, CHEQUE
    refund_reference: Optional[str] = None


class RefundApproveRequest(BaseModel):
    approved_by: Optional[UUID] = None


class RefundProcessRequest(BaseModel):
    refund_method: Optional[str] = None
    refund_reference: Optional[str] = None


class RefundResponse(BaseModel):
    id: UUID
    student_id: UUID
    institution_id: UUID
    original_payment_id: UUID
    original_invoice_id: UUID
    original_amount: Decimal
    cancellation_fee: Decimal
    refund_amount: Decimal
    refund_method: Optional[str] = None
    refund_reference: Optional[str] = None
    cancellation_receipt_number: Optional[str] = None
    refund_receipt_number: Optional[str] = None
    status: str
    reason: Optional[str] = None
    initiated_by: Optional[UUID] = None
    approved_by: Optional[UUID] = None
    processed_at: Optional[datetime] = None
    meta: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    # Nested summary fields
    student_name: Optional[str] = None
    application_number: Optional[str] = None

    class Config:
        from_attributes = True
