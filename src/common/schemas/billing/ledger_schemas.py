from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LedgerEntryResponse(BaseModel):
    entry_date: datetime
    entry_type: str
    source: str
    source_id: Optional[UUID] = None
    reference: Optional[str] = None
    description: str
    student_id: Optional[UUID] = None
    student_name: Optional[str] = None
    debit: float = 0.0
    credit: float = 0.0
    running_balance: float = 0.0


class LedgerResponse(BaseModel):
    institution_id: UUID
    student_id: Optional[UUID] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    filters: Dict[str, Any] = Field(default_factory=dict)
    opening_balance: float = 0.0
    total_debit: float = 0.0
    total_credit: float = 0.0
    closing_balance: float = 0.0
    entries: List[LedgerEntryResponse] = Field(default_factory=list)
