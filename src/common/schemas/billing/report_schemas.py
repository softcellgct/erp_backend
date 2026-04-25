from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional
from decimal import Decimal
from datetime import date

class StudentFeeReportRecord(BaseModel):
    student_id: UUID
    student_name: Optional[str] = "Unknown"
    application_number: Optional[str] = None
    roll_number: Optional[str] = None
    section: Optional[str] = None
    batch_name: Optional[str] = None
    college_name: Optional[str] = None
    department_name: Optional[str] = None
    total_fee: Decimal
    paid_amount: Decimal
    pending_amount: Decimal
    status: str

class StudentFeeReportResponse(BaseModel):
    items: List[StudentFeeReportRecord]
    total_students: int
    total_paid: Decimal
    total_pending: Decimal
    
    class Config:
        from_attributes = True

class CollectionReportRecord(BaseModel):
    id: str
    date: str
    mode: str
    amount: Decimal
    receipt_number: Optional[str] = None
    student_name: Optional[str] = None
    application_number: Optional[str] = None
    batch: Optional[str] = None
    college: Optional[str] = None
    department: Optional[str] = None
    counter: Optional[str] = None
    status: str
    paymentType: str

class CollectionReportResponse(BaseModel):
    items: List[CollectionReportRecord]
    total_amount: Decimal
    total_transactions: int
    record_count: int

class GeneralLedgerRecord(BaseModel):
    entry_date: str
    entry_type: str  # Debit / Credit
    source: str
    reference: Optional[str] = None
    student_name: Optional[str] = "Unknown"
    description: Optional[str] = None
    debit: Decimal
    credit: Decimal
    running_balance: Decimal

class GeneralLedgerResponse(BaseModel):
    entries: List[GeneralLedgerRecord]
    opening_balance: Decimal
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal
