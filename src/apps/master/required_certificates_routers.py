"""
API Routers for Admission Required Certificates Master
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List
from fastapi_pagination import Page, Params, add_pagination
from fastapi_pagination.ext.sqlalchemy import paginate


from common.models.master.admission_masters import (
    AdmissionRequiredCertificates,
    DocumentType,
)
from common.schemas.master.admission_required_certificates import (
    AdmissionRequiredCertificatesCreate,
    AdmissionRequiredCertificatesUpdate,
    AdmissionRequiredCertificatesListResponse,
)
from components.db.db import get_db_session


required_certificates_router = APIRouter(
    prefix="/required-certificates", tags=["Master - Required Certificates"]
)


# ========================
# List all required certificates with filters
# ========================
@required_certificates_router.get(
    "", response_model=Page[AdmissionRequiredCertificatesListResponse]
)
async def list_required_certificates(
    is_active: bool | None = None,
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get all required certificates with filters, including related document type data
    """
    query = select(AdmissionRequiredCertificates).options(
        selectinload(AdmissionRequiredCertificates.document_type)
    )

    if is_active is not None:
        query = query.where(AdmissionRequiredCertificates.is_active == is_active)

    query = query.order_by(AdmissionRequiredCertificates.created_at.desc())

    # Provide pagination params explicitly
    params = Params(page=page, size=size)
    return await paginate(db, query, params=params)


# ========================
# Create required certificate
# ========================
@required_certificates_router.post(
    "", status_code=status.HTTP_201_CREATED
)
async def create_required_certificate(
    data: AdmissionRequiredCertificatesCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a new required certificate
    """
    # Check if document type exists
    doc_type_result = await db.execute(
        select(DocumentType).where(DocumentType.id == data.document_type_id)
    )
    if not doc_type_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Document type not found")

    # Check if already exists
    existing = await db.execute(
        select(AdmissionRequiredCertificates).where(
            AdmissionRequiredCertificates.document_type_id == data.document_type_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="This certificate requirement already exists"
        )

    new_record = AdmissionRequiredCertificates(**data.dict())
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)

    return new_record


# ========================
# Get required certificate by ID
# ========================
@required_certificates_router.get("/{id}", response_model=AdmissionRequiredCertificatesListResponse)
async def get_required_certificate(
    id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """
    Get a specific required certificate
    """
    result = await db.execute(
        select(AdmissionRequiredCertificates).where(AdmissionRequiredCertificates.id == id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Required certificate not found")

    return record


# ========================
# Update required certificate
# ========================
@required_certificates_router.put(
    "/{id}", response_model=AdmissionRequiredCertificatesListResponse
)
async def update_required_certificate(
    id: UUID,
    data: AdmissionRequiredCertificatesUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update a required certificate
    """
    result = await db.execute(
        select(AdmissionRequiredCertificates).where(AdmissionRequiredCertificates.id == id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Required certificate not found")

    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)

    await db.commit()
    await db.refresh(record)

    return record


# ========================
# Delete required certificate
# ========================
@required_certificates_router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_required_certificate(
    id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """
    Delete a required certificate
    """
    result = await db.execute(
        select(AdmissionRequiredCertificates).where(AdmissionRequiredCertificates.id == id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Required certificate not found")

    await db.delete(record)
    await db.commit()

    return None


add_pagination(required_certificates_router)