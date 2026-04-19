"""Pydantic schemas for Gate -> Admission Visitor APIs.

These schemas now map to the dedicated `admission_gate_entries` table.
The external JSON contract remains backward-compatible with existing frontend keys.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VisitStatus(str, Enum):
    PENDING = "PENDING"
    CHECKED_IN = "CHECKED_IN"
    CHECKED_OUT = "CHECKED_OUT"
    CANCELLED = "CANCELLED"


class ReferenceType(str, Enum):
    CONSULTANCY = "consultancy"
    STAFF = "staff"
    STUDENT = "student"
    OTHER = "other"
    DIRECT_ADMISSION = "direct_admission"


class ConsultancyReferenceCreate(BaseModel):
    consultancy_id: UUID
    reference_staff_1: Optional[str] = None
    reference_staff_2: Optional[str] = None
    reference_staff_3: Optional[str] = None


class ConsultancyReferenceRead(BaseModel):
    id: UUID
    consultancy_id: UUID
    consultancy_name: Optional[str] = None
    reference_staff_1: Optional[str] = None
    reference_staff_2: Optional[str] = None
    reference_staff_3: Optional[str] = None

    class Config:
        from_attributes = True


class StaffReferenceCreate(BaseModel):
    staff_id: UUID


class StaffReferenceRead(BaseModel):
    id: UUID
    staff_id: UUID
    staff_name: Optional[str] = None

    class Config:
        from_attributes = True


class StudentReferenceCreate(BaseModel):
    student_name: str
    roll_number: str
    contact_number: str


class StudentReferenceRead(BaseModel):
    id: UUID
    student_name: str
    roll_number: str
    contact_number: str

    class Config:
        from_attributes = True


class OtherReferenceCreate(BaseModel):
    description: Optional[str] = None


class OtherReferenceRead(BaseModel):
    id: UUID
    description: Optional[str] = None

    class Config:
        from_attributes = True


class AdmissionVisitorBase(BaseModel):
    student_name: str
    mobile_number: Optional[str] = None
    parent_or_guardian_name: Optional[str] = None
    aadhar_number: Optional[str] = None
    native_place: Optional[str] = None
    image_url: Optional[str] = None
    gate_pass_no: Optional[str] = None
    reference_type: Optional[str] = None
    vehicle: Optional[bool] = False
    vehicle_number: Optional[str] = None
    institution_id: Optional[UUID] = None


class AdmissionVisitorCreate(AdmissionVisitorBase):
    consultancy_reference: Optional[ConsultancyReferenceCreate] = None
    staff_reference: Optional[StaffReferenceCreate] = None
    student_reference: Optional[StudentReferenceCreate] = None
    other_reference: Optional[OtherReferenceCreate] = None


class AdmissionVisitorUpdate(BaseModel):
    student_name: Optional[str] = None
    mobile_number: Optional[str] = None
    parent_or_guardian_name: Optional[str] = None
    aadhar_number: Optional[str] = None
    native_place: Optional[str] = None
    image_url: Optional[str] = None
    gate_pass_no: Optional[str] = None
    reference_type: Optional[str] = None
    vehicle: Optional[bool] = None
    vehicle_number: Optional[str] = None
    visit_status: Optional[VisitStatus] = None
    check_out_remarks: Optional[str] = None


class AdmissionVisitorRead(BaseModel):
    id: Optional[UUID] = None
    institution_id: Optional[UUID] = None
    institution_name: Optional[str] = None

    student_name: str
    mobile_number: Optional[str] = None
    parent_or_guardian_name: Optional[str] = None
    aadhar_number: Optional[str] = None
    gate_pass_no: Optional[str] = Field(None, validation_alias="gate_pass_number")

    native_place: Optional[str] = None
    image_url: Optional[str] = None
    reference_type: Optional[str] = None
    vehicle: Optional[bool] = False
    vehicle_number: Optional[str] = None
    visit_status: Optional[VisitStatus] = None
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    check_out_remarks: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status: Optional[str] = None

    consultancy_reference: Optional[ConsultancyReferenceRead] = None
    staff_reference: Optional[StaffReferenceRead] = None
    student_reference: Optional[StudentReferenceRead] = None
    other_reference: Optional[OtherReferenceRead] = None

    class Config:
        from_attributes = True
        populate_by_name = True


class AdmissionVisitorPassOutRequest(BaseModel):
    check_out_time: Optional[datetime] = None
    remarks: Optional[str] = None


class AdmissionVisitorPassOutResponse(BaseModel):
    visitor: AdmissionVisitorRead
    already_checked_out: bool = False


class AdmissionVisitorReportItem(BaseModel):
    id: Optional[UUID] = None
    institution_id: Optional[UUID] = None
    image_url: Optional[str] = None
    gate_pass_no: Optional[str] = None
    student_name: Optional[str] = None
    mobile_number: Optional[str] = None
    parent_or_guardian_name: Optional[str] = None
    native_place: Optional[str] = None
    institution_name: Optional[str] = None
    reference_type: Optional[str] = None
    reference_detail: Optional[str] = None
    vehicle: Optional[bool] = False
    vehicle_number: Optional[str] = None
    visit_status: Optional[str] = None
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    check_out_remarks: Optional[str] = None


class AdmissionVisitorReportSummary(BaseModel):
    total_entries: int = 0
    total_exits: int = 0
    inside_campus: int = 0


class AdmissionVisitorReportResponse(BaseModel):
    items: list[AdmissionVisitorReportItem]
    summary: AdmissionVisitorReportSummary
    total: int
    page: int
    size: int
    pages: int
