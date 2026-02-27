"""
Pydantic Schemas for Required Certificates (backed by DocumentType).

After consolidation, `admission_required_certificates` was merged into
`document_types`.  These schemas are the API contract for the
/required-certificates endpoints.
"""
from uuid import UUID
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RequiredCertificateCreate(BaseModel):
    """Create a new document-type / required-certificate entry."""
    name: str
    code: Optional[str] = None
    is_mandatory: bool = False
    description: Optional[str] = None
    is_active: bool = True


class RequiredCertificateUpdate(BaseModel):
    """Update an existing document-type / required-certificate."""
    name: Optional[str] = None
    code: Optional[str] = None
    is_mandatory: Optional[bool] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RequiredCertificateResponse(BaseModel):
    """Response schema — maps directly to DocumentType columns."""
    id: UUID
    name: str
    code: Optional[str] = None
    is_mandatory: bool
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
