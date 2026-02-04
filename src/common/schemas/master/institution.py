from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

# Institution Schemas
class InstitutionCreate(BaseModel):
    code: str
    name: str
    is_active: bool = True

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
    departments: Optional[list["DepartmentResponse"]] = None


# Department Schemas
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


# Course Schemas
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


# Class Schemas
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
    course: Optional[CourseResponse] = None


# Hostel Schemas
class HostelBase(BaseModel):
    name: str
    institution_id: UUID
    code: Optional[str] = None
    is_active: Optional[bool] = True
    meta: Optional[dict] = None

class HostelCreate(HostelBase):
    pass

class HostelUpdate(BaseModel):
    id: UUID
    name: Optional[str] = None
    code: Optional[str] = None
    is_active: Optional[bool] = None
    meta: Optional[dict] = None

class HostelResponse(HostelBase):
    id: UUID
    created_at: Optional[datetime] = None  # Added optional as generic defaults often don't include it if not selected
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
