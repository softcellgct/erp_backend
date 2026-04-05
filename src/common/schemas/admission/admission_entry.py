"""
Pydantic Schemas for Admission Management System
"""
from uuid import UUID
from common.models.admission.admission_entry import AdmissionStatusEnum
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Union
from datetime import date, datetime
from enum import Enum


class GenderEnum(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"





class PreviousAcademicLevelEnum(str, Enum):
    TENTH = "10th"
    TWELFTH = "12th"
    DIPLOMA = "Diploma"
    DEGREE = "Degree"


class CategoryEnum(str, Enum):
    GENERAL = "General"
    OBC = "OBC"
    SC = "SC"
    ST = "ST"
    MBC = "MBC"
    DNC = "DNC"
    OTHERS = "Others"


# ========================
# Base Schemas
# ========================

class SSLCDetailsBase(BaseModel):
    """Base schema for SSLC (10th) details"""
    register_number: Optional[str] = None
    school_name: Optional[str] = None
    school_block: Optional[str] = None
    school_district: Optional[str] = None
    board: Optional[str] = None  # State Board, CBSE, ICSE, etc.
    year_of_passing: Optional[str] = None
    marks: Optional[float] = None
    total_marks: Optional[float] = None
    percentage: Optional[float] = None


class HSCSubjectMarkBase(BaseModel):
    """Base schema for individual HSC subject marks"""
    subject_name: str
    subject_variant: Optional[str] = None  # e.g., Vocational, Practical
    total_marks: float
    obtained_marks: float


class HSCSubjectMarkCreate(HSCSubjectMarkBase):
    """Schema for creating HSC subject mark"""
    pass


class HSCSubjectMarkResponse(HSCSubjectMarkBase):
    """Schema for HSC subject mark response"""
    id: UUID

    class Config:
        from_attributes = True


class HSCDetailsBase(BaseModel):
    """Base schema for HSC (12th) details"""
    register_number: Optional[str] = None
    school_name: Optional[str] = None
    school_block: Optional[str] = None
    school_district: Optional[str] = None
    board: Optional[str] = None  # State Board, CBSE, ICSE, etc.
    year_of_passing: Optional[str] = None
    total_marks: Optional[float] = None
    obtained_marks: Optional[float] = None
    percentage: Optional[float] = None
    
    # Subject-wise marks (legacy aggregate columns)
    maths_mark: Optional[float] = None
    physics_mark: Optional[float] = None
    chemistry_mark: Optional[float] = None
    pcm_percentage: Optional[float] = None
    cutoff_mark: Optional[float] = None
    
    # School details
    school_address: Optional[str] = None
    medium_of_study: Optional[str] = None


class DiplomaDetailsBase(BaseModel):
    """Base schema for Diploma details"""
    college_name: Optional[str] = None
    department: Optional[str] = None
    register_number: Optional[str] = None
    year_of_passing: Optional[str] = None
    percentage: Optional[float] = None
    cgpa: Optional[float] = None


class PGDetailsBase(BaseModel):
    """Base schema for PG/Degree details"""
    degree_name: Optional[str] = None
    department: Optional[str] = None
    college_name: Optional[str] = None
    register_number: Optional[str] = None
    year_of_passing: Optional[str] = None
    percentage: Optional[float] = None
    cgpa: Optional[float] = None


class AdmissionPersonalDetailsSection(BaseModel):
    name: Optional[str] = None
    father_name: Optional[str] = None
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    student_mobile: Optional[str] = None
    parent_mobile: Optional[str] = None
    aadhaar_number: Optional[str] = None
    religion: Optional[str] = None
    community: Optional[str] = None
    caste: Optional[str] = None
    parent_income: Optional[float] = None
    door_no: Optional[str] = None
    street_name: Optional[str] = None
    village_name: Optional[str] = None
    taluk: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    parent_address: Optional[str] = None
    permanent_address: Optional[str] = None


class AdmissionProgramDetailsSection(BaseModel):
    campus: Optional[str] = None
    institution_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    course_id: Optional[UUID] = None
    academic_year_id: Optional[UUID] = None
    year: Optional[str] = None
    branch: Optional[str] = None
    previous_academic_level: Optional[PreviousAcademicLevelEnum] = None
    is_lateral_entry: Optional[bool] = None
    admission_quota_id: Optional[Union[UUID, str]] = None
    category: Optional[CategoryEnum] = None
    quota_type: Optional[str] = None
    special_quota: Optional[str] = None
    scholarships: Optional[str] = None
    boarding_place: Optional[str] = None
    admission_type_id: Optional[Union[UUID, str]] = None


class AdmissionPreviousAcademicDetailsSection(BaseModel):
    sslc: Optional[dict] = None
    hsc: Optional[dict] = None
    diploma: Optional[dict] = None
    degree: Optional[dict] = None


class AdmissionStudentBase(BaseModel):
    """Base schema for admission student"""
    # Enquiry Number
    enquiry_number: Optional[str] = None
    
    # Gate Pass and Reference
    gate_entry_id: Optional[UUID] = None
    
    # Category and Quota
    admission_quota_id: Optional[Union[UUID, str]] = None
    category: Optional[CategoryEnum] = None
    quota_type: Optional[str] = Field(None, max_length=50)
    special_quota: Optional[str] = Field(None, max_length=100)
    scholarships: Optional[str] = Field(None, max_length=200)
    boarding_place: Optional[str] = Field(None, max_length=200)
    admission_type_id: Optional[Union[UUID, str]] = None
    academic_year_id: Optional[UUID] = None
    application_number: Optional[str] = Field(None, max_length=20)
    roll_number: Optional[str] = Field(None, max_length=50)
    section: Optional[str] = Field(None, max_length=20)
    current_semester: Optional[int] = None
    is_sem1_active: Optional[bool] = False
    enrolled_at: Optional[datetime] = None

    status: Optional[AdmissionStatusEnum] = Field(default=AdmissionStatusEnum.ENQUIRED)


# ========================
# Create Schemas
# ========================

class SSLCDetailsCreate(SSLCDetailsBase):
    """Schema for creating SSLC details"""
    pass


class HSCDetailsCreate(HSCDetailsBase):
    """Schema for creating HSC details"""
    subject_marks: Optional[List[HSCSubjectMarkCreate]] = None


class DiplomaDetailsCreate(DiplomaDetailsBase):
    """Schema for creating Diploma details"""
    pass


class PGDetailsCreate(PGDetailsBase):
    """Schema for creating PG details"""
    pass


class AdmissionStudentCreate(AdmissionStudentBase):
    """Schema for creating admission student with nested academic details"""
    visitor_id: Optional[UUID] = None
    personal_details: Optional[AdmissionPersonalDetailsSection] = None
    program_details: Optional[AdmissionProgramDetailsSection] = None
    previous_academic_details: Optional[AdmissionPreviousAcademicDetailsSection] = None
    documents_submitted: Optional[List[str]] = None


class AdmissionStudentGrantAdmission(AdmissionStudentBase):
    """Schema for granting admission with visitor_id"""
    visitor_id: Optional[UUID] = None  # Admission visitor ID for granting admission
    personal_details: Optional[AdmissionPersonalDetailsSection] = None
    program_details: Optional[AdmissionProgramDetailsSection] = None
    previous_academic_details: Optional[AdmissionPreviousAcademicDetailsSection] = None


# ========================
# Update Schemas
# ========================

class SSLCDetailsUpdate(BaseModel):
    """Schema for updating SSLC details"""
    register_number: Optional[str] = None
    school_name: Optional[str] = None
    school_block: Optional[str] = None
    school_district: Optional[str] = None
    board: Optional[str] = None
    year_of_passing: Optional[str] = None
    marks: Optional[float] = None
    total_marks: Optional[float] = None
    percentage: Optional[float] = None


class HSCDetailsUpdate(BaseModel):
    """Schema for updating HSC details"""
    register_number: Optional[str] = None
    school_name: Optional[str] = None
    school_block: Optional[str] = None
    school_district: Optional[str] = None
    board: Optional[str] = None
    year_of_passing: Optional[str] = None
    total_marks: Optional[float] = None
    obtained_marks: Optional[float] = None
    percentage: Optional[float] = None
    maths_mark: Optional[float] = None
    physics_mark: Optional[float] = None
    chemistry_mark: Optional[float] = None
    pcm_percentage: Optional[float] = None
    cutoff_mark: Optional[float] = None
    school_address: Optional[str] = None
    medium_of_study: Optional[str] = None
    subject_marks: Optional[List[HSCSubjectMarkCreate]] = None


class DiplomaDetailsUpdate(BaseModel):
    """Schema for updating Diploma details"""
    college_name: Optional[str] = None
    department: Optional[str] = None
    register_number: Optional[str] = None
    year_of_passing: Optional[str] = None
    percentage: Optional[float] = None
    cgpa: Optional[float] = None


class PGDetailsUpdate(BaseModel):
    """Schema for updating PG details"""
    degree_name: Optional[str] = None
    department: Optional[str] = None
    college_name: Optional[str] = None
    register_number: Optional[str] = None
    year_of_passing: Optional[str] = None
    percentage: Optional[float] = None
    cgpa: Optional[float] = None


class AdmissionStudentUpdate(BaseModel):
    """Schema for updating admission student"""
    id: UUID
    gate_pass_number: Optional[str] = None
    reference_type: Optional[str] = None
    gate_entry_id: Optional[UUID] = None
    visitor_id: Optional[UUID] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    father_name: Optional[str] = Field(None, max_length=200)
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    student_mobile: Optional[str] = Field(None, max_length=15)
    parent_mobile: Optional[str] = Field(None, max_length=15)
    aadhaar_number: Optional[str] = Field(None, min_length=12, max_length=12)
    religion: Optional[str] = Field(None, max_length=50)
    community: Optional[str] = Field(None, max_length=50)
    caste: Optional[str] = Field(None, max_length=50)
    parent_income: Optional[float] = None
    door_no: Optional[str] = Field(None, max_length=50)
    street_name: Optional[str] = Field(None, max_length=200)
    village_name: Optional[str] = Field(None, max_length=100)
    taluk: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=10)
    parent_address: Optional[str] = None
    permanent_address: Optional[str] = None
    campus: Optional[str] = Field(None, max_length=200)
    institution_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    course_id: Optional[UUID] = None
    year: Optional[str] = Field(None, max_length=20)
    branch: Optional[str] = Field(None, max_length=200)
    previous_academic_level: Optional[PreviousAcademicLevelEnum] = None
    is_lateral_entry: Optional[bool] = None
    has_vehicle: Optional[bool] = None
    vehicle_number: Optional[str] = Field(None, max_length=20)
    admission_quota_id: Optional[Union[UUID, str]] = None
    category: Optional[CategoryEnum] = None
    quota_type: Optional[str] = Field(None, max_length=50)
    special_quota: Optional[str] = Field(None, max_length=100)
    scholarships: Optional[str] = Field(None, max_length=200)
    boarding_place: Optional[str] = Field(None, max_length=200)
    admission_type_id: Optional[Union[UUID, str]] = None
    academic_year_id: Optional[UUID] = None

    status: Optional[AdmissionStatusEnum] = Field(default=AdmissionStatusEnum.ENQUIRED)

    personal_details: Optional[AdmissionPersonalDetailsSection] = None
    program_details: Optional[AdmissionProgramDetailsSection] = None
    previous_academic_details: Optional[AdmissionPreviousAcademicDetailsSection] = None

    sslc_details: Optional[SSLCDetailsUpdate] = None
    hsc_details: Optional[HSCDetailsUpdate] = None
    diploma_details: Optional[DiplomaDetailsUpdate] = None
    pg_details: Optional[PGDetailsUpdate] = None
    documents_submitted: Optional[List[str]] = None


class BookAdmissionRequest(BaseModel):
    pass


class BookAdmissionResponse(BaseModel):
    """Response schema for book admission endpoint - returns only essential data"""
    id: UUID
    application_number: str
    status: str
    enquiry_number: str
    name: str


class UpdateCourseRequest(BaseModel):
    course_id: UUID
    fee_structure_id: UUID
    department_id: Optional[UUID] = None # Optional if inferred or explicit
    # We might need institution_id if transferring campus, but let's stick to course for now.


class AssignRollNumberRequest(BaseModel):
    roll_number: str = Field(..., min_length=1, max_length=50)


class AssignSectionRequest(BaseModel):
    section: str = Field(..., min_length=1, max_length=20)


class ActivateSem1Request(BaseModel):
    roll_number: Optional[str] = Field(None, min_length=1, max_length=50)
    section: Optional[str] = Field(None, min_length=1, max_length=20)


class SetFeeStructureLockRequest(BaseModel):
    fee_structure_id: Optional[UUID] = None


# ========================
# Response Schemas
# ========================

class SSLCDetailsResponse(SSLCDetailsBase):
    """Schema for SSLC details response"""
    id: UUID
    student_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HSCDetailsResponse(HSCDetailsBase):
    """Schema for HSC details response"""
    id: UUID
    student_id: UUID
    created_at: datetime
    updated_at: datetime
    subject_marks: Optional[List[HSCSubjectMarkResponse]] = []

    class Config:
        from_attributes = True


class DiplomaDetailsResponse(DiplomaDetailsBase):
    """Schema for Diploma details response"""
    id: UUID
    student_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PGDetailsResponse(PGDetailsBase):
    """Schema for PG details response"""
    id: UUID
    student_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AdmissionStudentResponse(AdmissionStudentBase):
    """Schema for admission student response"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    fee_structure_id: Optional[UUID] = None
    is_fee_structure_locked: Optional[bool] = False
    fee_structure_locked_at: Optional[datetime] = None
    fee_structure_locked_by: Optional[UUID] = None
    gate_entry_id: Optional[UUID] = None

    personal_details: Optional[AdmissionPersonalDetailsSection] = None
    program_details: Optional[AdmissionProgramDetailsSection] = None
    previous_academic_details: Optional[AdmissionPreviousAcademicDetailsSection] = None

    # Nested relationships
    sslc_details: Optional[SSLCDetailsResponse] = None
    hsc_details: Optional[HSCDetailsResponse] = None
    diploma_details: Optional[DiplomaDetailsResponse] = None
    pg_details: Optional[PGDetailsResponse] = None

    class Config:
        from_attributes = True


class AdmissionStudentListResponse(BaseModel):
    """Schema for paginated list of admission students"""
    items: List[AdmissionStudentResponse]

    class Config:
        from_attributes = True


class BulkAdmissionStatusUpdateRequest(BaseModel):
    """Schema for bulk admission student status update"""
    student_ids: List[UUID] = Field(default_factory=list)
    new_status: AdmissionStatusEnum


class BulkAdmissionStatusUpdateResult(BaseModel):
    """Schema for each student update result"""
    student_id: UUID
    success: bool
    message: Optional[str] = None


class BulkAdmissionStatusUpdateResponse(BaseModel):
    """Schema for bulk status update response summary"""
    total_requested: int
    updated_count: int
    failed_count: int
    results: List[BulkAdmissionStatusUpdateResult] = Field(default_factory=list)
