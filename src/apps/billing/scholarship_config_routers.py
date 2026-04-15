"""
API routes for scholarship configuration and staff referral concession management.
"""
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from components.db.db import get_db_session
from common.schemas.billing.scholarship_config_schemas import (
    ScholarshipConfigurationCreate,
    ScholarshipConfigurationUpdate,
    ScholarshipConfigurationResponse,
    StaffReferralConcessionCreate,
    StaffReferralConcessionUpdate,
    StaffReferralConcessionResponse,
)
from apps.billing.scholarship_config_service import (
    ScholarshipConfigurationService,
    StaffReferralConcessionService,
)
from logs.logging import logger

router = APIRouter(prefix="/scholarship-config", tags=["Scholarship Configuration"])


# ============================================================================
# SCHOLARSHIP CONFIGURATION ROUTES
# ============================================================================

@router.post("/create", response_model=ScholarshipConfigurationResponse)
async def create_scholarship_config(
    payload: ScholarshipConfigurationCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new scholarship configuration."""
    try:
        config = await ScholarshipConfigurationService.create(db, payload)
        await db.commit()
        await db.refresh(config)
        return config
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating scholarship configuration: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{config_id}", response_model=ScholarshipConfigurationResponse)
async def get_scholarship_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Fetch a scholarship configuration by ID."""
    config = await ScholarshipConfigurationService.get_by_id(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Scholarship configuration not found")
    return config


@router.get("/institution/{institution_id}", response_model=list[ScholarshipConfigurationResponse])
async def list_configs_by_institution(
    institution_id: UUID,
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db_session),
):
    """List all scholarship configurations for an institution."""
    configs = await ScholarshipConfigurationService.list_by_institution(
        db,
        institution_id,
        is_active=is_active,
    )
    return configs


@router.patch("/{config_id}", response_model=ScholarshipConfigurationResponse)
async def update_scholarship_config(
    config_id: UUID,
    payload: ScholarshipConfigurationUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update a scholarship configuration."""
    try:
        config = await ScholarshipConfigurationService.update(db, config_id, payload)
        if not config:
            raise HTTPException(status_code=404, detail="Scholarship configuration not found")
        await db.commit()
        await db.refresh(config)
        return config
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating scholarship configuration: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scholarship_config(
    config_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Delete a scholarship configuration."""
    try:
        success = await ScholarshipConfigurationService.delete(db, config_id)
        if not success:
            raise HTTPException(status_code=404, detail="Scholarship configuration not found")
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting scholarship configuration: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# STAFF REFERRAL CONCESSION ROUTES
# ============================================================================

@router.post("/referral/create", response_model=StaffReferralConcessionResponse)
async def create_referral_concession(
    payload: StaffReferralConcessionCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new staff referral concession."""
    try:
        concession = await StaffReferralConcessionService.create(db, payload)
        await db.commit()
        await db.refresh(concession)
        
        # Build response with nested fields
        response = StaffReferralConcessionResponse.from_orm(concession)
        if concession.staff:
            response.staff_name = concession.staff.full_name
        if concession.student:
            response.student_name = concession.student.application_number
        if concession.fee_head:
            response.fee_head_name = concession.fee_head.name
        
        return response
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating staff referral concession: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/referral/{concession_id}", response_model=StaffReferralConcessionResponse)
async def get_referral_concession(
    concession_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Fetch a staff referral concession by ID."""
    concession = await StaffReferralConcessionService.get_by_id(db, concession_id)
    if not concession:
        raise HTTPException(status_code=404, detail="Staff referral concession not found")
    
    response = StaffReferralConcessionResponse.from_orm(concession)
    if concession.staff:
        response.staff_name = concession.staff.full_name
    if concession.student:
        response.student_name = concession.student.application_number
    if concession.fee_head:
        response.fee_head_name = concession.fee_head.name
    
    return response


@router.get("/referral/staff/{staff_id}", response_model=list[StaffReferralConcessionResponse])
async def list_referral_by_staff(
    staff_id: UUID,
    is_applied: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db_session),
):
    """List all referral concessions created by a staff member."""
    concessions = await StaffReferralConcessionService.list_by_staff(
        db,
        staff_id,
        is_applied=is_applied,
    )
    
    results = []
    for concession in concessions:
        response = StaffReferralConcessionResponse.from_orm(concession)
        if concession.staff:
            response.staff_name = concession.staff.full_name
        if concession.student:
            response.student_name = concession.student.application_number
        if concession.fee_head:
            response.fee_head_name = concession.fee_head.name
        results.append(response)
    
    return results


@router.get("/referral/student/{student_id}", response_model=list[StaffReferralConcessionResponse])
async def list_referral_by_student(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """List all referral concessions for a student."""
    concessions = await StaffReferralConcessionService.list_by_student(db, student_id)
    
    results = []
    for concession in concessions:
        response = StaffReferralConcessionResponse.from_orm(concession)
        if concession.staff:
            response.staff_name = concession.staff.full_name
        if concession.student:
            response.student_name = concession.student.application_number
        if concession.fee_head:
            response.fee_head_name = concession.fee_head.name
        results.append(response)
    
    return results


@router.get("/referral/institution/{institution_id}", response_model=list[StaffReferralConcessionResponse])
async def list_referral_by_institution(
    institution_id: UUID,
    is_applied: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db_session),
):
    """List all staff referral concessions for an institution."""
    concessions = await StaffReferralConcessionService.list_by_institution(
        db,
        institution_id,
        is_applied=is_applied,
    )
    
    results = []
    for concession in concessions:
        response = StaffReferralConcessionResponse.from_orm(concession)
        if concession.staff:
            response.staff_name = concession.staff.full_name
        if concession.student:
            response.student_name = concession.student.application_number
        if concession.fee_head:
            response.fee_head_name = concession.fee_head.name
        results.append(response)
    
    return results


@router.patch("/referral/{concession_id}", response_model=StaffReferralConcessionResponse)
async def update_referral_concession(
    concession_id: UUID,
    payload: StaffReferralConcessionUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update a staff referral concession."""
    try:
        concession = await StaffReferralConcessionService.update(db, concession_id, payload)
        if not concession:
            raise HTTPException(status_code=404, detail="Staff referral concession not found")
        await db.commit()
        await db.refresh(concession)
        
        response = StaffReferralConcessionResponse.from_orm(concession)
        if concession.staff:
            response.staff_name = concession.staff.full_name
        if concession.student:
            response.student_name = concession.student.application_number
        if concession.fee_head:
            response.fee_head_name = concession.fee_head.name
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating staff referral concession: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/referral/{concession_id}/apply", response_model=StaffReferralConcessionResponse)
async def apply_referral_concession(
    concession_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Mark a referral concession as applied to invoice."""
    try:
        success = await StaffReferralConcessionService.apply_to_invoice(db, concession_id)
        if not success:
            raise HTTPException(status_code=404, detail="Staff referral concession not found")
        
        await db.commit()
        concession = await StaffReferralConcessionService.get_by_id(db, concession_id)
        
        response = StaffReferralConcessionResponse.from_orm(concession)
        if concession.staff:
            response.staff_name = concession.staff.full_name
        if concession.student:
            response.student_name = concession.student.application_number
        if concession.fee_head:
            response.fee_head_name = concession.fee_head.name
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error applying staff referral concession: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/referral/{concession_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_referral_concession(
    concession_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Delete a staff referral concession."""
    try:
        success = await StaffReferralConcessionService.delete(db, concession_id)
        if not success:
            raise HTTPException(status_code=404, detail="Staff referral concession not found")
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting staff referral concession: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
