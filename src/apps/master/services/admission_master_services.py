from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from common.models.master.admission_masters import AdmissionType, SeatQuota, DocumentType
from uuid import UUID

# --- Admission Type Service ---
async def create_admission_type(db: AsyncSession, name: str, code: str = None, description: str = None) -> AdmissionType:
    new_type = AdmissionType(name=name, code=code, description=description)
    db.add(new_type)
    await db.commit()
    await db.refresh(new_type)
    return new_type

async def get_all_admission_types(db: AsyncSession) -> List[AdmissionType]:
    result = await db.execute(select(AdmissionType).where(AdmissionType.is_active == True))
    return result.scalars().all()

async def get_admission_type_by_id(db: AsyncSession, type_id: UUID) -> Optional[AdmissionType]:
    result = await db.execute(select(AdmissionType).where(AdmissionType.id == type_id))
    return result.scalar_one_or_none()

async def delete_admission_type(db: AsyncSession, type_id: UUID) -> bool:
    admission_type = await get_admission_type_by_id(db, type_id)
    if admission_type:
        admission_type.is_active = False
        await db.commit()
        return True
    return False

# --- Seat Quota Service ---
async def create_seat_quota(db: AsyncSession, name: str, code: str = None, description: str = None) -> SeatQuota:
    new_quota = SeatQuota(name=name, code=code, description=description)
    db.add(new_quota)
    await db.commit()
    await db.refresh(new_quota)
    return new_quota

async def get_all_seat_quotas(db: AsyncSession) -> List[SeatQuota]:
    result = await db.execute(select(SeatQuota).where(SeatQuota.is_active == True))
    return result.scalars().all()

async def get_seat_quota_by_id(db: AsyncSession, quota_id: UUID) -> Optional[SeatQuota]:
    result = await db.execute(select(SeatQuota).where(SeatQuota.id == quota_id))
    return result.scalar_one_or_none()

async def delete_seat_quota(db: AsyncSession, quota_id: UUID) -> bool:
    quota = await get_seat_quota_by_id(db, quota_id)
    if quota:
        quota.is_active = False
        await db.commit()
        return True
    return False

# --- Document Type Service ---
async def create_document_type(db: AsyncSession, name: str, code: str = None, is_mandatory: bool = False, description: str = None) -> DocumentType:
    new_doc = DocumentType(name=name, code=code, is_mandatory=is_mandatory, description=description)
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)
    return new_doc

async def get_all_document_types(db: AsyncSession) -> List[DocumentType]:
    result = await db.execute(select(DocumentType).where(DocumentType.is_active == True))
    return result.scalars().all()

async def get_document_type_by_id(db: AsyncSession, doc_id: UUID) -> Optional[DocumentType]:
    result = await db.execute(select(DocumentType).where(DocumentType.id == doc_id))
    return result.scalar_one_or_none()

async def delete_document_type(db: AsyncSession, doc_id: UUID) -> bool:
    doc = await get_document_type_by_id(db, doc_id)
    if doc:
        doc.is_active = False
        await db.commit()
        return True
    return False
