from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime
from typing import Optional


class FinancialYearBase(BaseModel):
    name: str
    start_date: date
    end_date: date
    # institution_id: Optional[UUID] = None
    # academic_year_id: Optional[UUID] = None
    active: Optional[bool] = False


class FinancialYearCreate(FinancialYearBase):
    pass


class FinancialYearUpdate(BaseModel):
    id: UUID
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    # institution_id: Optional[UUID] = None
    # academic_year_id: Optional[UUID] = None
    active: Optional[bool] = None


class FinancialYearResponse(FinancialYearBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
