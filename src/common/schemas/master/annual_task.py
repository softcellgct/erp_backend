from datetime import date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from common.schemas.master.institution import InstitutionResponse

class AcademicYearSchema(BaseModel):
    year_name: str
    from_date: date
    to_date: date
    status: bool
    admission_active: bool
    institution_id: UUID
    course_configs: Optional[list["AcademicYearCourseCreate"]] = []

    class Config:
        from_attributes = True

class AcademicYearCourseCreate(BaseModel):
    course_id: UUID
    application_fee: float = 0.0
    is_active: bool = True

class AcademicYearCourseResponse(BaseModel):
    id: UUID
    course_id: UUID
    application_fee: float
    is_active: bool
    
    class Config:
        from_attributes = True

class AcademicYearResponse(AcademicYearSchema):
    id: UUID
    institution: InstitutionResponse
    available_courses: list[AcademicYearCourseResponse] = []

    class Config:
        from_attributes = True

class UpdateAcademicYearSchema(BaseModel):
    id: UUID
    year_name: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    status: Optional[bool] = None
    admission_active: Optional[bool] = None
    institution_id: Optional[UUID] = None
    course_configs: Optional[list[AcademicYearCourseCreate]] = None

    class Config:
        from_attributes = True


# Semester Period Schemas
class SemesterPeriodCreate(BaseModel):
    name: str
    short_name: str
    type: str  # e.g., "Semester"
    from_date: date
    to_date: date
    academic_year_id: UUID

class SemesterPeriodUpdate(BaseModel):
    id: UUID
    name: Optional[str] = None
    short_name: Optional[str] = None
    type: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    academic_year_id: Optional[UUID] = None
    is_active: Optional[bool] = None

class SemesterPeriodResponse(BaseModel):
    id: UUID
    name: str
    short_name: str
    type: str
    from_date: date
    to_date: date
    academic_year_id: UUID
    is_active: bool
    
    class Config:
        from_attributes = True