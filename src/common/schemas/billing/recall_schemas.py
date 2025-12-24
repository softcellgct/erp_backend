from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


class PaymentRecallRequestBase(BaseModel):
    payment_id: UUID
    requested_by: Optional[UUID] = None
    reason: Optional[str] = None
    status: Optional[str] = "requested"
    processed_by: Optional[UUID] = None
    processed_at: Optional[str] = None
    meta: Optional[dict] = None


class PaymentRecallRequestCreate(PaymentRecallRequestBase):
    pass


class PaymentRecallRequestResponse(PaymentRecallRequestBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
