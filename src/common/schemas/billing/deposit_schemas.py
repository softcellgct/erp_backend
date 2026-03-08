from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DepositReceiptItem(BaseModel):
    """Individual deposit receipt entry."""
    date: datetime
    amount: Decimal = Field(..., decimal_places=2)
    payment_method: str
    receipt_number: Optional[str] = None
    notes: Optional[str] = None


class DepositAdjustmentItem(BaseModel):
    """Record of deposit application to invoice."""
    date: datetime
    amount: Decimal = Field(..., decimal_places=2)
    invoice_id: UUID
    applied_by: Optional[UUID] = None


class StudentDepositCreate(BaseModel):
    """Schema for recording a new deposit."""
    amount: Decimal = Field(..., decimal_places=2, gt=0)
    payment_method: str = Field(..., min_length=1, max_length=50)
    transaction_id: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "amount": "5000.00",
                "payment_method": "bank_transfer",
                "transaction_id": "TRF-2026-00123",
                "notes": "Advance payment before fee structure lock"
            }
        }


class StudentDepositUpdate(BaseModel):
    """Schema for updating deposit information."""
    notes: Optional[str] = None


class DepositRefundCreate(BaseModel):
    """Schema for requesting deposit refund."""
    amount: Decimal = Field(..., decimal_places=2, gt=0)
    refund_method: str = Field(..., min_length=1, max_length=50)
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "amount": "2000.00",
                "refund_method": "bank_transfer",
                "notes": "Student requested partial refund"
            }
        }


class ApplyDepositToInvoiceRequest(BaseModel):
    """Schema for applying deposit to specific invoice."""
    amount_to_apply: Decimal = Field(..., decimal_places=2, gt=0)


class StudentDepositResponse(BaseModel):
    """Complete student deposit response."""
    id: UUID
    student_id: UUID
    institution_id: UUID
    application_number: Optional[str] = None
    total_deposited: Decimal = Field(..., decimal_places=2)
    used_amount: Decimal = Field(..., decimal_places=2)
    refunds_issued: Decimal = Field(..., decimal_places=2)
    available_balance: Decimal = Field(..., decimal_places=2)
    status: str
    notes: Optional[str] = None
    deposit_receipts: Optional[List[Dict[str, Any]]] = None
    adjustment_history: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "student_id": "550e8400-e29b-41d4-a716-446655440001",
                "institution_id": "550e8400-e29b-41d4-a716-446655440002",
                "application_number": "APP-2026-001",
                "total_deposited": "5000.00",
                "used_amount": "2500.00",
                "refunds_issued": "0.00",
                "available_balance": "2500.00",
                "status": "ACTIVE",
                "notes": "Advance payment recorded",
                "created_at": "2026-03-08T10:00:00",
                "updated_at": "2026-03-08T10:00:00"
            }
        }


class StudentDepositSummary(BaseModel):
    """Summary view for deposits list."""
    id: UUID
    student_id: UUID
    application_number: Optional[str] = None
    student_name: Optional[str] = None
    total_deposited: Decimal = Field(..., decimal_places=2)
    available_balance: Decimal = Field(..., decimal_places=2)
    status: str
    created_at: datetime


class PaginatedDepositList(BaseModel):
    """Paginated response for deposits list."""
    items: List[StudentDepositSummary]
    page: int
    size: int
    total: int
    pages: int


class DepositHistoryResponse(BaseModel):
    """Response showing deposit history."""
    deposit: StudentDepositResponse
    receipt_history: List[DepositReceiptItem] = Field(default_factory=list)
    adjustment_history: List[DepositAdjustmentItem] = Field(default_factory=list)
    pending_refunds: List[Dict[str, Any]] = Field(default_factory=list)

    class Config:
        from_attributes = True


class DepositRefundResponse(BaseModel):
    """Response for refund request."""
    refund_id: UUID
    deposit_id: UUID
    student_id: UUID
    amount: Decimal = Field(..., decimal_places=2)
    refund_method: str
    refund_reference: Optional[str] = None
    status: str
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
