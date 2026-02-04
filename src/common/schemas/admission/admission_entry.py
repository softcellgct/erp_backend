"""
Pydantic Schemas for Admission Management System
"""
from uuid import UUID
from common.models.admission.admission_entry import AdmissionStatusEnum, AdmissionTypeEnum
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class GenderEnum(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"


class AdmissionQuotaEnum(str, Enum):
    MANAGEMENT = "Management"
    GOVERNMENT = "Government"


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
    year_of_passing: Optional[str] = None
    marks: Optional[float] = None
    total_marks: Optional[float] = None
    percentage: Optional[float] = None


class HSCDetailsBase(BaseModel):
    """Base schema for HSC (12th) details"""
    register_number: Optional[str] = None
    school_name: Optional[str] = None
    year_of_passing: Optional[str] = None
    total_marks: Optional[float] = None
    obtained_marks: Optional[float] = None
    percentage: Optional[float] = None
    
    # Subject-wise marks
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


class AdmissionStudentBase(BaseModel):
    """Base schema for admission student"""
    # Enquiry Number
    enquiry_number: Optional[str] = None
    
    # Gate Pass and Reference
    gate_pass_number: Optional[str] = None
    reference_type: Optional[str] = None
    
    # Personal Details
    name: str = Field(..., min_length=1, max_length=200)
    father_name: Optional[str] = Field(None, max_length=200)
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    student_mobile: Optional[str] = Field(None, max_length=15)
    parent_mobile: Optional[str] = Field(None, max_length=15)
    aadhaar_number: Optional[str] = Field(None, min_length=12, max_length=12)
    
    # Religious and Social Details
    religion: Optional[str] = Field(None, max_length=50)
    community: Optional[str] = Field(None, max_length=50)
    caste: Optional[str] = Field(None, max_length=50)
    parent_income: Optional[float] = None
    
    # Address Details
    door_no: Optional[str] = Field(None, max_length=50)
    street_name: Optional[str] = Field(None, max_length=200)
    village_name: Optional[str] = Field(None, max_length=100)
    taluk: Optional[str] = Field(None, max_length=100)
    district: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=10)
    parent_address: Optional[str] = None
    permanent_address: Optional[str] = None
    
    # Degree & Branch Details
    campus: Optional[str] = Field(None, max_length=200)  # Institution name
    institution_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    course_id: Optional[UUID] = None
    year: Optional[str] = Field(None, max_length=20)  # Year of study
    branch: Optional[str] = Field(None, max_length=200)
    
    # Previous Academic Level
    previous_academic_level: Optional[PreviousAcademicLevelEnum] = None
    
    # Vehicle Details
    has_vehicle: Optional[bool] = False
    vehicle_number: Optional[str] = Field(None, max_length=20)
    
    # Category and Quota
    admission_quota: Optional[AdmissionQuotaEnum] = None
    category: Optional[CategoryEnum] = None
    quota_type: Optional[str] = Field(None, max_length=50)
    special_quota: Optional[str] = Field(None, max_length=100)
    scholarships: Optional[str] = Field(None, max_length=200)
    boarding_place: Optional[str] = Field(None, max_length=200)
    admission_type: Optional[AdmissionTypeEnum] = None
    academic_year_id: Optional[UUID] = None
    application_number: Optional[str] = Field(None, max_length=20)

    status: Optional[AdmissionStatusEnum] = None

    @validator('aadhaar_number')
    def validate_aadhaar(cls, v):
        if v and not v.isdigit():
            raise ValueError('Aadhaar number must contain only digits')
        return v

    @validator('student_mobile', 'parent_mobile')
    def validate_mobile(cls, v):
        if v and not v.isdigit():
            raise ValueError('Mobile number must contain only digits')
        if v and len(v) < 10:
            raise ValueError('Mobile number must be at least 10 digits')
        return v

    @validator('pincode')
    def validate_pincode(cls, v):
        if v and not v.isdigit():
            raise ValueError('Pincode must contain only digits')
        return v


# ========================
# Create Schemas
# ========================

class SSLCDetailsCreate(SSLCDetailsBase):
    """Schema for creating SSLC details"""
    pass


class HSCDetailsCreate(HSCDetailsBase):
    """Schema for creating HSC details"""
    pass


class DiplomaDetailsCreate(DiplomaDetailsBase):
    """Schema for creating Diploma details"""
    pass


class PGDetailsCreate(PGDetailsBase):
    """Schema for creating PG details"""
    pass


class AdmissionStudentCreate(AdmissionStudentBase):
    """Schema for creating admission student with nested academic details"""
    sslc_details: Optional[SSLCDetailsCreate] = None
    hsc_details: Optional[HSCDetailsCreate] = None
    diploma_details: Optional[DiplomaDetailsCreate] = None
    pg_details: Optional[PGDetailsCreate] = None


class AdmissionStudentGrantAdmission(AdmissionStudentBase):
    """Schema for granting admission with visitor_id"""
    visitor_id: Optional[UUID] = None  # Admission visitor ID for granting admission
    sslc_details: Optional[SSLCDetailsCreate] = None
    hsc_details: Optional[HSCDetailsCreate] = None
    diploma_details: Optional[DiplomaDetailsCreate] = None
    pg_details: Optional[PGDetailsCreate] = None


# ========================
# Update Schemas
# ========================

class SSLCDetailsUpdate(BaseModel):
    """Schema for updating SSLC details"""
    register_number: Optional[str] = None
    school_name: Optional[str] = None
    year_of_passing: Optional[str] = None
    marks: Optional[float] = None
    total_marks: Optional[float] = None
    percentage: Optional[float] = None


class HSCDetailsUpdate(BaseModel):
    """Schema for updating HSC details"""
    register_number: Optional[str] = None
    school_name: Optional[str] = None
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
    has_vehicle: Optional[bool] = None
    vehicle_number: Optional[str] = Field(None, max_length=20)
    admission_quota: Optional[AdmissionQuotaEnum] = None
    category: Optional[CategoryEnum] = None
    quota_type: Optional[str] = Field(None, max_length=50)
    special_quota: Optional[str] = Field(None, max_length=100)
    scholarships: Optional[str] = Field(None, max_length=200)
    boarding_place: Optional[str] = Field(None, max_length=200)
    admission_type: Optional[AdmissionTypeEnum] = None
    academic_year_id: Optional[UUID] = None

    status: Optional[AdmissionStatusEnum] = None

    sslc_details: Optional[SSLCDetailsUpdate] = None
    hsc_details: Optional[HSCDetailsUpdate] = None
    diploma_details: Optional[DiplomaDetailsUpdate] = None
    pg_details: Optional[PGDetailsUpdate] = None


class BookAdmissionRequest(BaseModel):
    pass

class UpdateCourseRequest(BaseModel):
    course_id: UUID
    fee_structure_id: UUID
    department_id: Optional[UUID] = None # Optional if inferred or explicit
    # We might need institution_id if transferring campus, but let's stick to course for now.


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
