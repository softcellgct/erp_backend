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

    class Config:
        from_attributes = True
    

class AcademicYearResponse(AcademicYearSchema):
    id: UUID
    institution: InstitutionResponse

    class Config:
        from_attributes = True

class UpdateAcademicYearSchema(BaseModel):
    year_name: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    status: Optional[bool] = None
    admission_active: Optional[bool] = None
    institution_id: Optional[UUID] = None

    class Config:
        from_attributes = True