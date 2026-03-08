"""
Finance API routers — Semester demand generation, invoice generation,
bulk receipt processing, and student fee visibility.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from components.db.db import get_db_session
from apps.billing.finance_service import finance_service
from common.schemas.billing.bulk_receipt_schemas import (
    BulkReceiptCreate,
    BulkReceiptResponse,
    GenerateBulkReceiptRequest,
    GenerateBulkReceiptResponse,
)

router = APIRouter()


# ── Semester-wise Demand Generation ───────────────────


@router.post(
    "/demands/generate",
    tags=["Finance - Demands"],
    summary="Generate semester/year-wise demand batch for matching students",
)
async def generate_demands(
    payload: dict,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Generate demand items for students matching filters.

    Required fields:
    - institution_id (UUID)
    - fee_structure_id (UUID)

    Optional:
    - semester (int): target semester number
    - year (int): target academic year number
    - filters (dict): department_id, degree_id, batch, admission_type_id, etc.
    - name (str): batch name
    - apply_concessions (bool): default true
    """
    try:
        result = await finance_service.generate_demand_batch(
            db=db,
            fee_structure_id=payload["fee_structure_id"],
            institution_id=payload["institution_id"],
            semester=payload.get("semester"),
            year=payload.get("year"),
            filters=payload.get("filters"),
            name=payload.get("name"),
            apply_concessions=payload.get("apply_concessions", True),
        )
        return result
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required field: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/demands",
    tags=["Finance - Demands"],
    summary="List demand items with filters",
)
async def list_demands(
    institution_id: UUID,
    student_id: UUID | None = None,
    batch_id: UUID | None = None,
    semester: int | None = None,
    year: int | None = None,
    payer_type: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await finance_service.list_demands(
            db=db,
            institution_id=institution_id,
            student_id=student_id,
            batch_id=batch_id,
            semester=semester,
            year=year,
            payer_type=payer_type,
            status=status,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Invoice Generation ────────────────────────────────


@router.post(
    "/invoices/generate",
    tags=["Finance - Invoices"],
    summary="Generate invoices from pending demand items",
)
async def generate_invoices(
    payload: dict,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Generate invoices from pending demands.

    Optional fields:
    - batch_id (UUID): only process demands from this batch
    - student_id (UUID): only process this student's demands
    - payer_type (str): STUDENT, GOVERNMENT, or SCHOLARSHIP
    """
    try:
        result = await finance_service.generate_invoices_from_demands(
            db=db,
            batch_id=payload.get("batch_id"),
            student_id=payload.get("student_id"),
            payer_type=payload.get("payer_type"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Student Fee Visibility ────────────────────────────


@router.get(
    "/students/{student_id}/fees",
    tags=["Finance - Student Fees"],
    summary="Get student fee summary (student portal view)",
)
async def get_student_fees(
    student_id: UUID,
    include_government: bool = False,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Returns fee summary for a student.

    - Student portal: include_government=False (default) — only STUDENT fees
    - Admin portal: include_government=True — all fee types
    """
    try:
        return await finance_service.get_student_fees(
            db=db,
            student_id=student_id,
            include_government=include_government,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Bulk Receipts ─────────────────────────────────────


@router.post(
    "/bulk-receipts",
    tags=["Finance - Bulk Receipts"],
    summary="Create a bulk receipt with manual invoice mapping",
)
async def create_bulk_receipt(
    payload: BulkReceiptCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a bulk receipt and apply payments to specified invoices.
    Used for government/scholarship payments covering multiple students.
    """
    try:
        return await finance_service.create_bulk_receipt(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/bulk-receipts/generate",
    tags=["Finance - Bulk Receipts"],
    summary="Auto-generate bulk receipt from unpaid government invoices",
)
async def generate_bulk_receipt(
    payload: GenerateBulkReceiptRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Find all unpaid government/scholarship invoices matching the fee
    structure and create a single bulk payment covering them all.
    """
    try:
        return await finance_service.generate_bulk_receipt(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/bulk-receipts",
    tags=["Finance - Bulk Receipts"],
    summary="List bulk receipts for an institution",
)
async def list_bulk_receipts(
    institution_id: UUID,
    payer_type: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await finance_service.list_bulk_receipts(
            db=db,
            institution_id=institution_id,
            payer_type=payer_type,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/bulk-receipts/{receipt_id}",
    tags=["Finance - Bulk Receipts"],
    summary="Get bulk receipt details",
)
async def get_bulk_receipt(
    receipt_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await finance_service.get_bulk_receipt(db, receipt_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
