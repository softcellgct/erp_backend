from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


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
    student_name: str = Field(..., max_length=255)
    mobile_number: str
    parent_or_guardian_name: Optional[str] = Field(None, max_length=255)
    aadhar_number: str
    native_place: str = Field(..., max_length=255)
    image_url: str = Field(..., max_length=255)
    gate_pass_no: Optional[str] = Field(None, max_length=50)
    # accept string for reference_type here (match your ReferenceType enum values in app logic)
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


# Read / response schemas with from_attributes to allow SQLAlchemy model -> schema conversion
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
    consultancy_reference: Optional[ConsultancyReferenceRead] = None
    staff_reference: Optional[StaffReferenceRead] = None
    student_reference: Optional[StudentReferenceRead] = None
    other_reference: Optional[OtherReferenceRead] = None

    class Config:
        from_attributes = True
