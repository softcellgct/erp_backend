from pydantic import BaseModel
from typing import Optional
from uuid import UUID

# --- Admission Type Schemas ---
class AdmissionTypeBase(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None

class AdmissionTypeCreate(AdmissionTypeBase):
    pass

class AdmissionTypeUpdate(AdmissionTypeBase):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class AdmissionTypeResponse(AdmissionTypeBase):
    id: UUID
    is_active: bool

    class Config:
        from_attributes = True

# --- Seat Quota Schemas ---
class SeatQuotaBase(BaseModel):
    name: str
    code: Optional[str] = None
    description: Optional[str] = None

class SeatQuotaCreate(SeatQuotaBase):
    pass

class SeatQuotaUpdate(SeatQuotaBase):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class SeatQuotaResponse(SeatQuotaBase):
    id: UUID
    is_active: bool

    class Config:
        from_attributes = True

# --- Document Type Schemas ---
class DocumentTypeBase(BaseModel):
    name: str
    code: Optional[str] = None
    is_mandatory: Optional[bool] = False
    description: Optional[str] = None

class DocumentTypeCreate(DocumentTypeBase):
    pass

class DocumentTypeUpdate(DocumentTypeBase):
    name: Optional[str] = None
    is_active: Optional[bool] = None

class DocumentTypeResponse(DocumentTypeBase):
    id: UUID
    is_active: bool

    class Config:
        from_attributes = True
