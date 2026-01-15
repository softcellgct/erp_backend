from datetime import date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel

from common.schemas.master_schemas import InstitutionResponse

class AcademicYearSchema(BaseModel):
    year_name: str
    from_date: date
    to_date: date
    status: bool
    admission_active: bool
    institution_id: UUID
    department_configs: Optional[list["AcademicYearDepartmentCreate"]] = []

    class Config:
        from_attributes = True

class AcademicYearDepartmentCreate(BaseModel):
    department_id: UUID
    application_fee: float = 0.0
    is_active: bool = True

class AcademicYearDepartmentResponse(BaseModel):
    id: UUID
    department_id: UUID
    application_fee: float
    is_active: bool
    # We can include the full department details if needed, but ID is often sufficient for lists.
    # Let's include name for convenience if possible, but keep it simple for now.
    
    class Config:
        from_attributes = True

class AcademicYearResponse(AcademicYearSchema):
    id: UUID
    institution: InstitutionResponse
    available_departments: list[AcademicYearDepartmentResponse] = []

    class Config:
        from_attributes = True

class UpdateAcademicYearSchema(BaseModel):
    year_name: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    status: Optional[bool] = None
    admission_active: Optional[bool] = None
    institution_id: Optional[UUID] = None
    department_configs: Optional[list[AcademicYearDepartmentCreate]] = None

    class Config:
        from_attributes = True