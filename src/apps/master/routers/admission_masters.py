from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from components.db.db import get_db_session
from apps.master.services.admission_master_services import (
    create_admission_type, get_all_admission_types, delete_admission_type,
    create_seat_quota, get_all_seat_quotas, delete_seat_quota,
    create_document_type, get_all_document_types, delete_document_type
)
from common.schemas.master.admission_masters import (
    AdmissionTypeCreate, AdmissionTypeResponse, SeatQuotaCreate, SeatQuotaResponse, DocumentTypeCreate, DocumentTypeResponse
)

router = APIRouter(tags=["Admission Masters"])

# --- Admission Type Endpoints ---
@router.post("/admission-types", response_model=AdmissionTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_new_admission_type(
    item: AdmissionTypeCreate,
    db: AsyncSession = Depends(get_db_session)
):
    return await create_admission_type(db, item.name, item.code, item.description)

@router.get("/admission-types", response_model=List[AdmissionTypeResponse])
async def read_admission_types(db: AsyncSession = Depends(get_db_session)):
    return await get_all_admission_types(db)

@router.delete("/admission-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_admission_type(type_id: UUID, db: AsyncSession = Depends(get_db_session)):
    success = await delete_admission_type(db, type_id)
    if not success:
        raise HTTPException(status_code=404, detail="Admission Type not found")

# --- Seat Quota Endpoints ---
@router.post("/seat-quotas", response_model=SeatQuotaResponse, status_code=status.HTTP_201_CREATED)
async def create_new_seat_quota(
    item: SeatQuotaCreate,
    db: AsyncSession = Depends(get_db_session)
):
    return await create_seat_quota(db, item.name, item.code, item.description)

@router.get("/seat-quotas", response_model=List[SeatQuotaResponse])
async def read_seat_quotas(db: AsyncSession = Depends(get_db_session)):
    return await get_all_seat_quotas(db)

@router.delete("/seat-quotas/{quota_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_seat_quota(quota_id: UUID, db: AsyncSession = Depends(get_db_session)):
    success = await delete_seat_quota(db, quota_id)
    if not success:
        raise HTTPException(status_code=404, detail="Seat Quota not found")

# --- Document Type Endpoints ---
@router.post("/document-types", response_model=DocumentTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_new_document_type(
    item: DocumentTypeCreate,
    db: AsyncSession = Depends(get_db_session)
):
    return await create_document_type(db, item.name, item.code, item.is_mandatory, item.description)

@router.get("/document-types", response_model=List[DocumentTypeResponse])
async def read_document_types(db: AsyncSession = Depends(get_db_session)):
    return await get_all_document_types(db)

@router.delete("/document-types/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_document_type(doc_id: UUID, db: AsyncSession = Depends(get_db_session)):
    success = await delete_document_type(db, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document Type not found")
