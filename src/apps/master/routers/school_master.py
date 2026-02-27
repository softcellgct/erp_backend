"""
School Master API Routes - CRUD + CSV/Excel bulk upload for school list
"""
from fastapi import APIRouter, Depends, UploadFile, File, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from components.db.db import get_db_session
from components.middleware import is_superadmin
from apps.master.services.school_master import SchoolMasterService
from common.schemas.master.admission_masters import (
    SchoolMasterCreate,
    SchoolMasterUpdate,
    SchoolMasterResponse,
    SchoolMasterListResponse,
    SchoolBulkUploadResponse,
)

school_router = APIRouter(tags=["School Master"])


@school_router.get("/schools", response_model=List[SchoolMasterResponse])
@is_superadmin
async def list_schools(
    request: Request,
    search: Optional[str] = None,
    block: Optional[str] = None,
    district: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
):
    """Get paginated list of schools with optional search and filters."""
    return await SchoolMasterService(db).list_schools(search, block, district, skip, limit)


@school_router.get("/schools/list", response_model=List[SchoolMasterListResponse])
@is_superadmin
async def list_schools_dropdown(
    request: Request,
    block: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Get simple school list for dropdown (id, name, block)."""
    return await SchoolMasterService(db).list_schools_dropdown(block)


@school_router.get("/schools/blocks", response_model=List[str])
@is_superadmin
async def list_school_blocks(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """Get distinct school blocks for filter dropdown."""
    return await SchoolMasterService(db).list_blocks()


@school_router.post(
    "/schools",
    response_model=SchoolMasterResponse,
    status_code=status.HTTP_201_CREATED,
)
@is_superadmin
async def create_school(
    request: Request,
    data: SchoolMasterCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a single school entry."""
    return await SchoolMasterService(db).create_school(data)


@school_router.put("/schools/{school_id}", response_model=SchoolMasterResponse)
@is_superadmin
async def update_school(
    request: Request,
    school_id: UUID,
    data: SchoolMasterUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update a school entry."""
    return await SchoolMasterService(db).update_school(school_id, data)


@school_router.delete("/schools/{school_id}", status_code=status.HTTP_204_NO_CONTENT)
@is_superadmin
async def delete_school(
    request: Request,
    school_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Soft delete a school entry."""
    await SchoolMasterService(db).delete_school(school_id)


@school_router.post("/schools/upload", response_model=SchoolBulkUploadResponse)
@is_superadmin
async def upload_school_list(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Upload a CSV, Excel, or PDF file containing school list.
    
    For CSV/Excel:
    Expected columns: name (or school_name), block (or block_name), district, school_address, pincode, state
    At minimum, 'name' or 'school_name' column is required.
    
    For PDF (Tamil Nadu format):
    Expected columns: S NO, DISTRICT, BLOCK NAME, SCHOOL NAME, SCHOOL ADDRESS, PINCODE
    
    Supported formats: .csv, .xlsx, .xls, .pdf
    """
    return await SchoolMasterService(db).bulk_upload_schools(file)
