from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date
from typing import Optional

from components.db.db import get_db_session
from apps.billing.report_service import BillingReportService
from common.schemas.billing.report_schemas import (
    CollectionReportResponse,
    StudentFeeReportResponse,
    GeneralLedgerResponse
)

router = APIRouter()
report_service = BillingReportService()

@router.get("/collection", response_model=CollectionReportResponse)
async def get_collection_report(
    institution_id: Optional[UUID] = None,
    department_id: Optional[UUID] = None,
    academic_year_id: Optional[UUID] = None,
    payment_mode: Optional[str] = None,
    fee_head_id: Optional[UUID] = None,
    cash_counter_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await report_service.get_collection_summary(
            db=db,
            institution_id=institution_id,
            department_id=department_id,
            academic_year_id=academic_year_id,
            payment_mode=payment_mode,
            fee_head_id=fee_head_id,
            cash_counter_id=cash_counter_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/student-fees", response_model=StudentFeeReportResponse)
async def get_student_fee_report(
    institution_id: Optional[UUID] = None,
    department_id: Optional[UUID] = None,
    academic_year_id: Optional[UUID] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await report_service.get_student_fee_report(
            db=db,
            institution_id=institution_id,
            department_id=department_id,
            academic_year_id=academic_year_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/general-ledger", response_model=GeneralLedgerResponse)
async def get_general_ledger(
    institution_id: Optional[UUID] = None,
    department_id: Optional[UUID] = None,
    academic_year_id: Optional[UUID] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    student_id: Optional[UUID] = None,
    degree_id: Optional[UUID] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await report_service.get_general_ledger(
            db=db,
            institution_id=institution_id,
            department_id=department_id,
            academic_year_id=academic_year_id,
            degree_id=degree_id,
            start_date=from_date,
            end_date=to_date,
            student_id=student_id,
            search=search,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
