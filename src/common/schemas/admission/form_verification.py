"""
Pydantic Schemas for Admission Form Verification
"""
from uuid import UUID
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum


class VerificationStatusEnum(str, Enum):
    PENDING = "PENDING"
    FORM_PRINTED = "FORM_PRINTED"
    APPLICATION_RECEIVED = "APPLICATION_RECEIVED"
    CERTIFICATES_RECEIVED = "CERTIFICATES_RECEIVED"
    VERIFIED = "VERIFIED"
    PROVISIONALLY_ALLOTTED = "PROVISIONALLY_ALLOTTED"
    REJECTED = "REJECTED"


# ========================
# Base Schemas
# ========================


class AdmissionFormVerificationBase(BaseModel):
    """Base schema for form verification"""

    certificate_verified: bool = False
    verification_remarks: Optional[str] = None
    documents_checked: Optional[str] = None


# ========================
# Create/Update Schemas
# ========================


class AdmissionFormVerificationCreate(AdmissionFormVerificationBase):
    """Schema for creating form verification"""

    student_id: UUID


class AdmissionFormVerificationUpdate(BaseModel):
    """Schema for updating form verification"""

    form_printed: Optional[bool] = None
    certificate_verified: Optional[bool] = None
    status: Optional[VerificationStatusEnum] = None
    verification_remarks: Optional[str] = None
    documents_checked: Optional[str] = None


class PrintFormRequest(BaseModel):
    """Schema for print form request"""

    pass  # No additional data needed


class VerifyCertificateRequest(BaseModel):
    """Schema for certificate verification request"""

    certificate_verified: bool
    verification_remarks: Optional[str] = None
    documents_checked: Optional[str] = None


# ========================
# Response Schemas
# ========================


class AdmissionFormVerificationResponse(AdmissionFormVerificationBase):
    """Response schema for form verification"""

    id: UUID
    student_id: UUID
    status: VerificationStatusEnum
    form_printed: bool
    form_printed_at: Optional[datetime]
    form_printed_by: Optional[UUID]
    application_received: bool
    application_received_at: Optional[datetime]
    application_received_by: Optional[UUID]
    certificate_verified_at: Optional[datetime]
    certificate_verified_by: Optional[UUID]
    provisionally_allotted: bool
    provisionally_allotted_at: Optional[datetime]
    provisionally_allotted_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========================
# Submitted Certificate Schemas
# ========================


class SubmittedCertificateBase(BaseModel):
    """Base schema for submitted certificate"""

    is_received: bool = False
    is_verified: bool = False
    remarks: Optional[str] = None


class SubmittedCertificateCreate(SubmittedCertificateBase):
    """Schema for creating submitted certificate"""

    form_verification_id: UUID
    required_certificate_id: UUID
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[str] = None


class SubmittedCertificateUpdate(BaseModel):
    """Schema for updating submitted certificate"""

    is_received: Optional[bool] = None
    is_verified: Optional[bool] = None
    remarks: Optional[str] = None


class SubmittedCertificateResponse(SubmittedCertificateBase):
    """Response schema for submitted certificate"""

    id: UUID
    form_verification_id: UUID
    required_certificate_id: UUID
    file_name: Optional[str]
    file_type: Optional[str]
    file_size: Optional[str]
    received_at: Optional[datetime]
    received_by: Optional[UUID]
    verified_at: Optional[datetime]
    verified_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
