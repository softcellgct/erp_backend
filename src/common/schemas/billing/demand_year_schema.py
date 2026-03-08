from typing import List
from uuid import UUID
from pydantic import BaseModel, Field


class CreateYearDemandRequest(BaseModel):
    """Request schema for creating year/semester-specific demands"""
    student_ids: List[UUID] = Field(..., description="List of student UUIDs")
    fee_structure_id: UUID = Field(..., description="Fee structure UUID")
    year: str | None = Field(default=None, description="Academic year (e.g., '1', '2', '3')")
    semester: int | None = Field(default=None, description="Semester number (e.g., 1, 2, 3)")


class CreateYearDemandResponse(BaseModel):
    """Response schema for year-specific demand creation"""
    created_count: int = Field(..., description="Number of demand items created")
    total_amount: float = Field(..., description="Total amount of demands created")
    invoice_count: int = Field(..., description="Number of invoices created")
    message: str = Field(..., description="Success message")
