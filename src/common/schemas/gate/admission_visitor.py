from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from common.models.gate.visitor_model import VisitStatus


class ConsultancyReferenceCreate(BaseModel):
    consultancy_id: UUID
    reference_staff_1: str = Field(..., max_length=255)
    reference_staff_2: Optional[str] = Field(None, max_length=255)
    reference_staff_3: Optional[str] = Field(None, max_length=255)
    contact_number: str = Field(..., max_length=20)


class StaffReferenceCreate(BaseModel):
    staff_name: str = Field(..., max_length=255)
    department: str = Field(..., max_length=255)
    contact_number: str = Field(..., max_length=20)


class StudentReferenceCreate(BaseModel):
    student_name: str = Field(..., max_length=255)
    course: str = Field(..., max_length=255)
    contact_number: str = Field(..., max_length=20)


class OtherReferenceCreate(BaseModel):
    description: str = Field(..., max_length=255)


class AdmissionVisitorBase(BaseModel):
    institution_id: UUID
    student_name: str = Field(..., max_length=255)
    mobile_number: str
    parent_or_guardian_name: Optional[str] = Field(None, max_length=255)
    aadhar_number: str
    native_place: str = Field(..., max_length=255)
    image_url: str = Field(..., max_length=255)
    gate_pass_no: Optional[str] = Field(None, max_length=50)
    reference_type: str
    vehicle: bool = False
    vehicle_number: Optional[str] = Field(None, max_length=50)


class AdmissionVisitorCreate(AdmissionVisitorBase):
    consultancy_reference: Optional[ConsultancyReferenceCreate] = None
    staff_reference: Optional[StaffReferenceCreate] = None
    student_reference: Optional[StudentReferenceCreate] = None
    other_reference: Optional[OtherReferenceCreate] = None


class AdmissionVisitorUpdate(BaseModel):
    id: UUID
    institution_id: Optional[UUID] = None
    student_name: Optional[str] = Field(None, max_length=255)
    mobile_number: Optional[str] = None
    parent_or_guardian_name: Optional[str] = Field(None, max_length=255)
    aadhar_number: Optional[str] = None
    native_place: Optional[str] = Field(None, max_length=255)
    reference_type: Optional[str] = None
    image_url: Optional[str] = Field(None, max_length=255)
    vehicle: Optional[bool] = None
    vehicle_number: Optional[str] = Field(None, max_length=50)
    consultancy_reference: Optional[ConsultancyReferenceCreate] = None
    staff_reference: Optional[StaffReferenceCreate] = None
    student_reference: Optional[StudentReferenceCreate] = None
    other_reference: Optional[OtherReferenceCreate] = None


class ConsultancyReferenceRead(ConsultancyReferenceCreate):
    class Config:
        from_attributes = True


class StaffReferenceRead(StaffReferenceCreate):
    class Config:
        from_attributes = True


class StudentReferenceRead(StudentReferenceCreate):
    class Config:
        from_attributes = True


class OtherReferenceRead(OtherReferenceCreate):
    class Config:
        from_attributes = True


class AdmissionVisitorRead(AdmissionVisitorBase):
    id: Optional[UUID] = None
    visit_status: VisitStatus = VisitStatus.CHECKED_IN
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    check_out_remarks: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    consultancy_reference: Optional[ConsultancyReferenceRead] = None
    staff_reference: Optional[StaffReferenceRead] = None
    student_reference: Optional[StudentReferenceRead] = None
    other_reference: Optional[OtherReferenceRead] = None

    class Config:
        from_attributes = True


class AdmissionVisitorPassOutRequest(BaseModel):
    check_out_time: Optional[datetime] = None
    remarks: Optional[str] = Field(None, max_length=255)


class AdmissionVisitorPassOutResponse(BaseModel):
    visitor: AdmissionVisitorRead
    already_checked_out: bool = False


class AdmissionVisitorReportSummary(BaseModel):
    total_entries: int = 0
    total_exits: int = 0
    inside_campus: int = 0


class AdmissionVisitorReportItem(BaseModel):
    id: UUID
    gate_pass_no: str
    student_name: str
    mobile_number: str
    parent_or_guardian_name: Optional[str] = None
    native_place: str
    institution_id: UUID
    institution_name: Optional[str] = None
    reference_type: str
    visit_status: VisitStatus
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    check_out_remarks: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdmissionVisitorReportResponse(BaseModel):
    items: list[AdmissionVisitorReportItem]
    total: int
    page: int
    size: int
    pages: int
    summary: AdmissionVisitorReportSummary
