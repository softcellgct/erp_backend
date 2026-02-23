"""
Pydantic Schemas for Department Change Requests
"""
from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class DepartmentChangeStatusEnum(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ========================
# Base Schemas
# ========================


class DepartmentChangeRequestBase(BaseModel):
    """Base schema for department change request"""

    reason: str = Field(..., min_length=10, max_length=1000, description="Reason for department change")


# ========================
# Create/Update Schemas
# ========================


class DepartmentChangeRequestCreate(DepartmentChangeRequestBase):
    """Schema for creating department change request"""

    student_id: UUID
    current_department_id: UUID
    requested_department_id: UUID


class DepartmentChangeRequestUpdate(BaseModel):
    """Schema for updating department change request"""

    reason: Optional[str] = Field(None, min_length=10, max_length=1000)
    status: Optional[DepartmentChangeStatusEnum] = None
    remarks: Optional[str] = None


class ApproveRejectRequest(BaseModel):
    """Schema for approving/rejecting department change request"""

    remarks: Optional[str] = Field(None, max_length=500, description="Admin remarks")


# ========================
# Response Schemas
# ========================


class DepartmentInfo(BaseModel):
    """Simple department info for response"""

    id: UUID
    name: str
    code: Optional[str] = None

    class Config:
        from_attributes = True


class StudentInfo(BaseModel):
    """Simple student info for response"""

    id: UUID
    name: str
    application_number: Optional[str] = None
    register_number: Optional[str] = None

    class Config:
        from_attributes = True


class DepartmentChangeRequestResponse(DepartmentChangeRequestBase):
    """Response schema for department change request"""

    id: UUID
    student_id: UUID
    current_department_id: UUID
    requested_department_id: UUID
    status: DepartmentChangeStatusEnum
    requested_by: UUID
    requested_at: datetime
    reviewed_by: Optional[UUID]
    reviewed_at: Optional[datetime]
    remarks: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Nested relationships
    student: Optional[StudentInfo] = None
    current_department: Optional[DepartmentInfo] = None
    requested_department: Optional[DepartmentInfo] = None

    class Config:
        from_attributes = True


class DepartmentChangeRequestListResponse(BaseModel):
    """Response schema for list of department change requests"""

    items: list[DepartmentChangeRequestResponse]
    total: int
    page: int
    size: int
    pages: int
