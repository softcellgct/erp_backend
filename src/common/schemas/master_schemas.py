from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import date

# Pydantic Schemas for Request/Response
class InstitutionCreate(BaseModel):
    code: str
    name: str

class InstitutionUpdate(BaseModel):
    id : UUID
    code: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None


class InstitutionResponse(BaseModel):
    id: UUID
    code: str
    name: str
    is_active: bool

class DepartmentCreate(BaseModel):
    code: str
    name: str
    institution_id: UUID

class DepartmentUpdate(BaseModel):
    id: UUID
    code: Optional[str] = None
    name: Optional[str] = None
    institution_id: Optional[UUID] = None
    is_active: Optional[bool] = None

class DepartmentResponse(BaseModel):
    id: UUID
    code: str
    name: str
    institution_id: UUID
    is_active: bool

class CourseCreate(BaseModel):
    code: str
    title: str
    department_id: UUID
    level: str  # "UG" or "PG"
    short_name: Optional[str] = None
    course_duration_years: int
    total_semesters: int

class CourseUpdate(BaseModel):
    id: UUID
    code: Optional[str] = None
    title: Optional[str] = None
    department_id: Optional[UUID] = None
    level: Optional[str] = None
    short_name: Optional[str] = None
    course_duration_years: Optional[int] = None
    total_semesters: Optional[int] = None
    is_active: Optional[bool] = None

class CourseResponse(BaseModel):
    id: UUID
    code: str
    title: str
    department_id: UUID
    level: str
    short_name: Optional[str] = None
    course_duration_years: int
    total_semesters: int
    is_active: bool

class ClassCreate(BaseModel):
    code: str
    title: str
    course_id: UUID

class ClassUpdate(BaseModel):
    id: UUID
    code: Optional[str] = None
    title: Optional[str] = None
    course_id: Optional[UUID] = None
    is_active: Optional[bool] = None

class ClassResponse(BaseModel):
    id: UUID
    code: str
    title: str
    course_id: UUID
    is_active: bool

    course: CourseResponse


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

