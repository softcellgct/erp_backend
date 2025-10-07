from pydantic import BaseModel
from typing import Optional
from uuid import UUID

# Pydantic Schemas for Request/Response
class InstitutionCreate(BaseModel):
    code: str
    name: str

class InstitutionUpdate(BaseModel):
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

class CourseUpdate(BaseModel):
    code: Optional[str] = None
    title: Optional[str] = None
    department_id: Optional[UUID] = None
    is_active: Optional[bool] = None

class CourseResponse(BaseModel):
    id: UUID
    code: str
    title: str
    department_id: UUID
    is_active: bool

class ClassCreate(BaseModel):
    code: str
    title: str
    course_id: UUID

class ClassUpdate(BaseModel):
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