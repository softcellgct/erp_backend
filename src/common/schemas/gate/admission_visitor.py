"""
Pydantic schemas for the Gate – Admission Visitor endpoints.

The underlying ORM model is now ``AdmissionStudent`` (after the table
consolidation migration). Column names changed, but the *external* API
contract is preserved through Pydantic v2 ``validation_alias``.

  ┌─────── JSON field name ──────┐  ┌─── ORM attribute (validation_alias) ───┐
  │ student_name                 │→ │ name                                    │
  │ mobile_number                │→ │ student_mobile                          │
  │ parent_or_guardian_name      │→ │ father_name                             │
  │ aadhar_number                │→ │ aadhaar_number                          │
  │ gate_pass_no                 │→ │ gate_pass_number                        │
  │ vehicle                      │→ │ has_vehicle                             │
  └──────────────────────────────┘  └─────────────────────────────────────────┘

``AdmissionVisitorBase`` keeps the *old* JSON names and is used for
Create / Update payloads.  ``gate/services.py._FIELD_MAP`` remaps them
before writing to the DB.

``AdmissionVisitorRead`` is used as the *response* model.  It also
keeps the old JSON names but uses ``validation_alias`` so Pydantic can
read the correct ORM attribute when ``from_attributes = True``.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── value enums ──────────────────────────────────────────────────────
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


# ── reference sub-schemas ────────────────────────────────────────────
class ConsultancyReferenceCreate(BaseModel):
    consultancy_id: UUID
    reference_staff_1: Optional[str] = None
    reference_staff_2: Optional[str] = None
    reference_staff_3: Optional[str] = None

class ConsultancyReferenceRead(BaseModel):
    id: UUID
    consultancy_id: UUID
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


# ── base schema (Create / Update payloads) ───────────────────────────
class AdmissionVisitorBase(BaseModel):
    """JSON field names match the *old* visitor model.
    services.py ``_FIELD_MAP`` translates them before DB write."""

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


# ── read / response schema ───────────────────────────────────────────
class AdmissionVisitorRead(BaseModel):
    """Serialises an ``AdmissionStudent`` ORM row back into the legacy
    JSON shape expected by the frontend.

    ``validation_alias`` tells Pydantic which ORM attribute to read;
    the *field name* is what appears in the JSON output."""

    id: Optional[UUID] = None
    institution_id: Optional[UUID] = None

    # ↓↓ mapped fields ↓↓
    student_name: str = Field(validation_alias="name")
    mobile_number: Optional[str] = Field(None, validation_alias="student_mobile")
    parent_or_guardian_name: Optional[str] = Field(None, validation_alias="father_name")
    aadhar_number: Optional[str] = Field(None, validation_alias="aadhaar_number")
    gate_pass_no: Optional[str] = Field(None, validation_alias="gate_pass_number")
    vehicle: Optional[bool] = Field(False, validation_alias="has_vehicle")

    # ↓↓ unchanged fields ↓↓
    native_place: Optional[str] = None
    image_url: Optional[str] = None
    reference_type: Optional[str] = None
    vehicle_number: Optional[str] = None
    visit_status: Optional[VisitStatus] = None
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    check_out_remarks: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status: Optional[str] = None

    # ↓↓ nested references ↓↓
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
    message: str
    visitor: AdmissionVisitorRead


# ── report schemas ───────────────────────────────────────────────────
class AdmissionVisitorReportItem(BaseModel):
    """Comes from ``_row_to_report_item`` which builds plain dicts
    with the *old* field names – no alias needed here."""

    gate_pass_no: Optional[str] = None
    student_name: Optional[str] = None
    mobile_number: Optional[str] = None
    parent_or_guardian_name: Optional[str] = None
    native_place: Optional[str] = None
    reference_type: Optional[str] = None
    reference_detail: Optional[str] = None
    vehicle: Optional[bool] = False
    vehicle_number: Optional[str] = None
    visit_status: Optional[str] = None
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    check_out_remarks: Optional[str] = None


class AdmissionVisitorReportSummary(BaseModel):
    total_visitors: int = 0
    checked_in: int = 0
    checked_out: int = 0


class AdmissionVisitorReportResponse(BaseModel):
    items: list[AdmissionVisitorReportItem]
    summary: AdmissionVisitorReportSummary
    total: int
    page: int
    size: int
    pages: int
