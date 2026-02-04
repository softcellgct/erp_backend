from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class CashCounterBase(BaseModel):
    name: str
    code: str
    is_active: bool = True
    institution_id: UUID

class CashCounterCreate(CashCounterBase):
    password: str

class CashCounterUpdate(BaseModel):
    id: UUID
    name: str | None = None
    code: str | None = None
    is_active: bool | None = None
    password: str | None = None

class CashCounterResponse(CashCounterBase):
    id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from common.schemas.billing.invoice_schemas import InvoiceResponse

class StudentDuesResponse(BaseModel):
    student_id: UUID
    application_number: Optional[str] = None
    name: str
    department: Optional[str] = None
    course: Optional[str] = None
    batch: Optional[str] = None # year
    invoices: List[InvoiceResponse]

class CashCounterPaymentRequest(BaseModel):
    invoice_id: UUID
    amount: float
    payment_method: str = "Cash"
    notes: Optional[str] = None
