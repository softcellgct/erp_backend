"""
Pydantic Schemas for Admission Required Certificates Master
"""
from uuid import UUID
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AdmissionRequiredCertificatesBase(BaseModel):
    """Base schema for admission required certificates"""

    document_type_id: UUID
    is_mandatory: bool = False
    description: Optional[str] = None
    is_active: bool = True


class AdmissionRequiredCertificatesCreate(AdmissionRequiredCertificatesBase):
    """Schema for creating admission required certificates"""

    pass


class AdmissionRequiredCertificatesUpdate(BaseModel):
    """Schema for updating admission required certificates"""

    is_mandatory: Optional[bool] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class AdmissionRequiredCertificatesResponse(AdmissionRequiredCertificatesBase):
    """Response schema for admission required certificates"""

    id: UUID
    created_at: datetime
    updated_at: datetime

    # Include related data
    class DocumentTypeInfo(BaseModel):
        id: UUID
        name: str
        code: Optional[str]
        is_mandatory: bool

        class Config:
            from_attributes = True

    document_type_info: Optional[DocumentTypeInfo] = None

    class Config:
        from_attributes = True


class AdmissionRequiredCertificatesListResponse(BaseModel):
    """List response schema with related data"""

    id: UUID
    document_type_id: UUID
    is_mandatory: bool
    is_active: bool
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Include nested relationships
    class DocumentTypeNested(BaseModel):
        id: UUID
        name: str
        code: Optional[str] = None

        class Config:
            from_attributes = True

    document_type: Optional[DocumentTypeNested] = None

    class Config:
        from_attributes = True
