from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

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


# --- School Master Schemas ---
class SchoolMasterBase(BaseModel):
    name: str
    block: Optional[str] = None
    district: Optional[str] = None
    school_address: Optional[str] = None
    pincode: Optional[str] = None
    state: Optional[str] = "Tamil Nadu"

class SchoolMasterCreate(SchoolMasterBase):
    pass

class SchoolMasterUpdate(BaseModel):
    id: UUID
    name: Optional[str] = None
    block: Optional[str] = None
    district: Optional[str] = None
    school_address: Optional[str] = None
    pincode: Optional[str] = None
    state: Optional[str] = None
    is_active: Optional[bool] = None

class SchoolMasterResponse(SchoolMasterBase):
    id: UUID
    is_active: bool

    class Config:
        from_attributes = True


class SchoolMasterPaginatedResponse(BaseModel):
    items: List[SchoolMasterResponse]
    total: int
    page: int
    size: int
    pages: int

class SchoolMasterListResponse(BaseModel):
    """Simple response for dropdown list"""
    id: UUID
    name: str
    block: Optional[str] = None
    district: Optional[str] = None
    pincode: Optional[str] = None

    class Config:
        from_attributes = True

class SchoolListUploadResponse(BaseModel):
    id: UUID
    file_name: str
    record_count: int
    upload_status: str
    created_at: datetime

    class Config:
        from_attributes = True

class SchoolBulkUploadResponse(BaseModel):
    """Response after bulk upload of schools"""
    total_rows: int
    record_count: int  # Number of schools inserted
    skipped: int
    errors: List[str] = []
