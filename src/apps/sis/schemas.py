from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from common.models.admission.admission_entry import CategoryEnum, GenderEnum
from common.models.sis.sis_student import BloodGroupEnum, HostelStatusEnum


class SISProfileUpdate(BaseModel):
    blood_group: Optional[BloodGroupEnum] = None
    nationality: Optional[str] = None
    mother_tongue: Optional[str] = None
    email: Optional[str] = None
    whatsapp_number: Optional[str] = None
    differently_abled: Optional[bool] = None
    differently_abled_type: Optional[str] = None
    ex_serviceman_child: Optional[bool] = None
    first_generation_graduate: Optional[bool] = None
    mother_name: Optional[str] = None
    mother_occupation: Optional[str] = None
    father_occupation: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_relation: Optional[str] = None
    guardian_mobile: Optional[str] = None
    register_number: Optional[str] = None
    hostel_status: Optional[HostelStatusEnum] = None
    photo_url: Optional[str] = None


class SISProfileResponse(BaseModel):
    id: UUID
    admission_student_id: UUID
    blood_group: Optional[BloodGroupEnum] = None
    nationality: Optional[str] = None
    mother_tongue: Optional[str] = None
    email: Optional[str] = None
    whatsapp_number: Optional[str] = None
    differently_abled: bool = False
    differently_abled_type: Optional[str] = None
    ex_serviceman_child: bool = False
    first_generation_graduate: bool = False
    mother_name: Optional[str] = None
    mother_occupation: Optional[str] = None
    father_occupation: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_relation: Optional[str] = None
    guardian_mobile: Optional[str] = None
    register_number: Optional[str] = None
    hostel_status: Optional[HostelStatusEnum] = None
    photo_url: Optional[str] = None
    profile_completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EnrollStudentRequest(BaseModel):
    roll_number: Optional[str] = None
    section: Optional[str] = None


class LockFeeRequest(BaseModel):
    """Assign & lock a fee structure during Perfect Entry.

    If ``fee_structure_id`` is omitted the billing service resolves the best
    match for the student's program/quota.
    """
    fee_structure_id: Optional[UUID] = None


class PerfectEntryUpdate(BaseModel):
    # Basic Info (editable, except aadhaar_number which is locked)
    name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[GenderEnum] = None
    blood_group: Optional[BloodGroupEnum] = None
    nationality: Optional[str] = None
    mother_tongue: Optional[str] = None
    hostel_status: Optional[HostelStatusEnum] = None
    register_number: Optional[str] = None

    # Statutory Info
    religion: Optional[str] = None
    community: Optional[str] = None
    caste: Optional[str] = None
    category: Optional[CategoryEnum] = None
    quota_type: Optional[str] = None
    special_quota: Optional[str] = None
    scholarships: Optional[str] = None
    differently_abled: Optional[bool] = None
    differently_abled_type: Optional[str] = None
    ex_serviceman_child: Optional[bool] = None
    first_generation_graduate: Optional[bool] = None

    # Communication / Contact
    student_mobile: Optional[str] = None
    parent_mobile: Optional[str] = None
    door_no: Optional[str] = None
    street_name: Optional[str] = None
    village_name: Optional[str] = None
    taluk: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    parent_address: Optional[str] = None
    permanent_address: Optional[str] = None
    email: Optional[str] = None
    whatsapp_number: Optional[str] = None

    # Parental Info
    father_name: Optional[str] = None
    parent_income: Optional[float] = None
    mother_name: Optional[str] = None
    mother_occupation: Optional[str] = None
    father_occupation: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_relation: Optional[str] = None
    guardian_mobile: Optional[str] = None

    # Bank Account Details
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc_code: Optional[str] = None
    bank_branch_name: Optional[str] = None
    bank_account_holder_name: Optional[str] = None

    # Emergency Contact Info
    emergency_contact_name: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    emergency_contact_mobile: Optional[str] = None

    # Transfer Certificate Info
    tc_number: Optional[str] = None
    tc_date: Optional[datetime] = None
    tc_from_school: Optional[str] = None
    tc_issued_by: Optional[str] = None

    # Counselling Info
    boarding_place: Optional[str] = None
    counselling_date: Optional[datetime] = None
    counselling_number: Optional[str] = None
    allotment_order_number: Optional[str] = None
    counselling_type: Optional[str] = None

    # Government / Institutional IDs
    emis_number: Optional[str] = None
    umis_number: Optional[str] = None
    abc_id: Optional[str] = None

    # Quota / social status extras
    minority_status: Optional[str] = None

    # Contact extras
    alternate_mobile: Optional[str] = None

    # Extended communication address
    comm_address_line2: Optional[str] = None
    comm_country: Optional[str] = None

    # Structured permanent address
    perm_address_line1: Optional[str] = None
    perm_address_line2: Optional[str] = None
    perm_area_street: Optional[str] = None
    perm_city: Optional[str] = None
    perm_district: Optional[str] = None
    perm_state: Optional[str] = None
    perm_country: Optional[str] = None
    perm_pincode: Optional[str] = None

    # Program structure (editable in Perfect Entry — the finalization point).
    # These are FK columns on AdmissionStudentProgramDetails. ``is_lateral_entry``
    # is mirrored onto AdmissionStudent as well.
    institution_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    course_id: Optional[UUID] = None
    academic_year_id: Optional[UUID] = None
    admission_quota_id: Optional[UUID] = None
    is_lateral_entry: Optional[bool] = None

    # Previous academic records — flexible JSON per level (matches the
    # admission_student_previous_academic_details JSON columns).
    sslc: Optional[dict] = None
    hsc: Optional[dict] = None
    diploma: Optional[dict] = None
    degree: Optional[dict] = None


class RollToken(BaseModel):
    type: str
    digits: Optional[int] = None        # academic_year: 4 or 2
    value: Optional[str] = None         # literal
    padding: Optional[int] = None       # running_number
    start: Optional[int] = None         # running_number
    reset_scope: Optional[str] = None   # running_number


class RollFilters(BaseModel):
    institution_id: Optional[str] = None
    department_id: Optional[str] = None
    course_id: Optional[str] = None
    academic_year_id: Optional[str] = None
    quota: Optional[str] = None
    section: Optional[str] = None


class RollTemplateUpsert(BaseModel):
    institution_id: Optional[UUID] = None
    department_id: UUID
    course_id: Optional[UUID] = None
    academic_year_id: UUID
    name: Optional[str] = None
    tokens: List[RollToken]
    separator: Optional[str] = ""


class RollPreviewRequest(BaseModel):
    filters: RollFilters = RollFilters()
    tokens: List[RollToken]
    separator: Optional[str] = ""
    only_unassigned: bool = True


class RollCommitRequest(RollPreviewRequest):
    save_template: bool = False
    template_name: Optional[str] = None


class ClassCreate(BaseModel):
    course_id: UUID
    academic_year_id: Optional[UUID] = None
    section_name: str
    capacity: Optional[int] = None
    institution_id: Optional[UUID] = None


class ClassUpdate(BaseModel):
    section_name: Optional[str] = None
    capacity: Optional[int] = None
    is_active: Optional[bool] = None


class AssignClassRequest(BaseModel):
    class_id: UUID
    student_ids: List[UUID]


class UnassignRequest(BaseModel):
    student_ids: List[UUID]


class SISStudentListItem(BaseModel):
    id: UUID
    enquiry_number: str
    application_number: Optional[str] = None
    name: str
    roll_number: Optional[str] = None
    section: Optional[str] = None
    current_semester: Optional[int] = None
    enrolled_at: Optional[datetime] = None
    is_sem1_active: bool = False
    department_name: Optional[str] = None
    course_title: Optional[str] = None
    academic_year_name: Optional[str] = None
    student_mobile: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    sis_profile: Optional[SISProfileResponse] = None
    profile_completion: int = 0

    class Config:
        from_attributes = True
