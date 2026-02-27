"""
API Routers for Required Certificates (backed by DocumentType).

After the table consolidation, `admission_required_certificates` was merged
into `document_types`.  The `is_mandatory`, `description`, and `is_active`
columns already exist on DocumentType, so this router now queries
DocumentType directly.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from fastapi_pagination import Page, Params, add_pagination
from fastapi_pagination.ext.sqlalchemy import paginate

from common.models.master.admission_masters import DocumentType
from common.schemas.master.admission_required_certificates import (
    RequiredCertificateCreate,
    RequiredCertificateUpdate,
    RequiredCertificateResponse,
)
from components.db.db import get_db_session


required_certificates_router = APIRouter(
    prefix="/required-certificates", tags=["Master - Required Certificates"]
)


# ========================
# List all required certificates (active document types)
# ========================
@required_certificates_router.get(
    "", response_model=Page[RequiredCertificateResponse]
)
async def list_required_certificates(
    is_active: bool | None = None,
    is_mandatory: bool | None = None,
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_db_session),
):
    """Get all required certificate configurations (document types)."""
    query = select(DocumentType)

    if is_active is not None:
        query = query.where(DocumentType.is_active == is_active)
    if is_mandatory is not None:
        query = query.where(DocumentType.is_mandatory == is_mandatory)

    query = query.order_by(DocumentType.created_at.desc())
    params = Params(page=page, size=size)
    return await paginate(db, query, params=params)


# ========================
# Create required certificate
# ========================
@required_certificates_router.post(
    "", status_code=status.HTTP_201_CREATED,
    response_model=RequiredCertificateResponse,
)
async def create_required_certificate(
    data: RequiredCertificateCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new document-type / required-certificate entry."""
    # Duplicate name check
    existing = await db.execute(
        select(DocumentType).where(DocumentType.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="A document type with this name already exists",
        )

    new_record = DocumentType(**data.dict())
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)
    return new_record


# ========================
# Get required certificate by ID
# ========================
@required_certificates_router.get(
    "/{id}", response_model=RequiredCertificateResponse
)
async def get_required_certificate(
    id: UUID, db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(
        select(DocumentType).where(DocumentType.id == id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Required certificate not found")
    return record


# ========================
# Update required certificate
# ========================
@required_certificates_router.put(
    "/{id}", response_model=RequiredCertificateResponse
)
async def update_required_certificate(
    id: UUID,
    data: RequiredCertificateUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(DocumentType).where(DocumentType.id == id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Required certificate not found")

    for field, value in data.dict(exclude_unset=True).items():
        setattr(record, field, value)

    await db.commit()
    await db.refresh(record)
    return record


# ========================
# Delete required certificate
# ========================
@required_certificates_router.delete(
    "/{id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_required_certificate(
    id: UUID, db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(
        select(DocumentType).where(DocumentType.id == id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Required certificate not found")

    await db.delete(record)
    await db.commit()
    return None


add_pagination(required_certificates_router)
