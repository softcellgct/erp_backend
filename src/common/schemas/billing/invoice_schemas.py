from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime


class InvoiceLineItemBase(BaseModel):
    fee_head_id: Optional[UUID] = None
    description: str = Field(..., max_length=255)
    amount: float = Field(...)
    discount_amount: Optional[float] = 0.0
    tax_amount: Optional[float] = 0.0


class InvoiceLineItemCreate(InvoiceLineItemBase):
    pass



from common.schemas.billing.fee_head_schemas import FeeHeadResponse

class InvoiceLineItemResponse(InvoiceLineItemBase):
    id: UUID
    invoice_id: UUID
    fee_head: Optional[FeeHeadResponse] = None

    class Config:
        from_attributes = True


class PaymentBase(BaseModel):
    amount: float
    payment_method: str
    transaction_id: Optional[str] = None
    receipt_number: Optional[str] = None
    notes: Optional[str] = None


class PaymentCreate(PaymentBase):
    pass


class PaymentResponse(PaymentBase):
    id: UUID
    invoice_id: UUID
    payment_date: datetime

    class Config:
        from_attributes = True


class InvoiceBase(BaseModel):
    student_id: UUID
    institution_id: UUID
    issue_date: date
    due_date: date
    notes: Optional[str] = None
    amount: Optional[float] = None  # optional override
    line_items: Optional[List[InvoiceLineItemCreate]] = None


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(BaseModel):
    id: UUID
    notes: Optional[str] = None
    due_date: Optional[date] = None


class InvoiceResponse(InvoiceBase):
    id: UUID
    invoice_number: str
    paid_amount: float
    balance_due: float
    status: str
    created_at: datetime
    updated_at: datetime
    line_items: Optional[List[InvoiceLineItemResponse]] = None
    payments: Optional[List[PaymentResponse]] = None

    class Config:
        from_attributes = True
