from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, validator
from typing import Optional

class ApplicationFeePaymentRequest(BaseModel):
    student_name: str = Field(..., min_length=1, max_length=255)
    student_mobile: str = Field(..., min_length=10, max_length=15, pattern=r"^\+?[0-9]+$")
    course_id: UUID
    academic_year_id: UUID
    payment_mode: str = Field(..., description="Cash, UPI, Card, etc.")
    remarks: Optional[str] = None
    
    # Optional cash counter ID override if needed (usually taken from user session/context)
    cash_counter_id: Optional[UUID] = None

class ApplicationFeeTransactionResponse(BaseModel):
    id: UUID
    receipt_number: str
    student_name: str
    student_mobile: str
    payment_mode: str
    amount: float
    transaction_date: datetime
    payment_status: str
    course_name: Optional[str] = None # Enriched response
    academic_year_name: Optional[str] = None # Enriched response

    class Config:
        from_attributes = True
