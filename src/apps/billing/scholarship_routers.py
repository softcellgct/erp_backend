"""
Scholarship management routes:
- CRUD for student scholarships
- Certificate submission & review
- Multi-receipt bulk generation
- Dashboard
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from components.db.db import get_db_session
from common.models.billing.scholarship import (
    StudentScholarship,
    ScholarshipTypeEnum,
    CertificateStatusEnum,
)
from common.models.billing.fee_structure import FeeStructure
from common.models.billing.application_fees import Invoice, Payment, PaymentStatusEnum, InvoiceStatusHistory
from common.models.admission.admission_entry import AdmissionStudent
from common.schemas.billing.scholarship_schemas import (
    StudentScholarshipCreate,
    MultiReceiptRequest,
    MultiReceiptResponse,
    ScholarshipDashboardResponse,
)
from logs.logging import logger

router = APIRouter()


def _enrich_scholarship_response(sch: StudentScholarship) -> dict:
    """Convert scholarship ORM to dict with student info."""
    data = {
        "id": sch.id,
        "student_id": sch.student_id,
        "institution_id": sch.institution_id,
        "fee_structure_id": sch.fee_structure_id,
        "academic_year_id": sch.academic_year_id,
        "scholarship_type": sch.scholarship_type.value if hasattr(sch.scholarship_type, "value") else str(sch.scholarship_type),
        "certificate_status": sch.certificate_status.value if hasattr(sch.certificate_status, "value") else str(sch.certificate_status),
        "certificate_file": sch.certificate_file,
        "submitted_at": sch.submitted_at,
        "reviewed_at": sch.reviewed_at,
        "approved_at": sch.approved_at,
        "reviewed_by": sch.reviewed_by,
        "amount": float(sch.amount),
        "amount_received": sch.amount_received,
        "amount_received_at": sch.amount_received_at,
        "receipt_id": sch.receipt_id,
        "rejection_reason": sch.rejection_reason,
        "meta": sch.meta,
        "created_at": sch.created_at,
        "updated_at": sch.updated_at,
    }
    if sch.student:
        data["student_name"] = sch.getattr(student.personal_details, "name", None) if getattr(student, "personal_details", None) else getattr(student, "name", None)
        data["application_number"] = sch.student.application_number
        data["department_name"] = getattr(sch.student, "department_name", None)
        data["course_title"] = getattr(sch.student, "course_title", None)
    return data


# ── Create ────────────────────────────────────────────
@router.post("/", tags=["Billing - Scholarships"])
async def create_scholarship(
    payload: StudentScholarshipCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a scholarship record. Auto-resolves amount from fee structure if available."""
    # Validate student exists
    student = (await db.execute(
        select(AdmissionStudent).where(AdmissionStudent.id == payload.student_id)
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Resolve amount from fee structure if not provided
    amount = payload.amount
    fs_id = payload.fee_structure_id or student.fee_structure_id

    if fs_id and amount == 0:
        fs = (await db.execute(select(FeeStructure).where(FeeStructure.id == fs_id))).scalar_one_or_none()
        if fs:
            if payload.scholarship_type == "FG" and fs.fg_amount:
                amount = fs.fg_amount
            elif payload.scholarship_type == "SC_ST" and fs.sc_st_amount:
                amount = fs.sc_st_amount

    sch = StudentScholarship(
        student_id=payload.student_id,
        institution_id=payload.institution_id,
        fee_structure_id=fs_id,
        academic_year_id=payload.academic_year_id or student.academic_year_id,
        scholarship_type=ScholarshipTypeEnum(payload.scholarship_type),
        certificate_status=CertificateStatusEnum.NOT_SUBMITTED,
        amount=amount,
        certificate_file=payload.certificate_file,
        meta=payload.meta,
    )
    db.add(sch)
    await db.commit()
    await db.refresh(sch)
    return _enrich_scholarship_response(sch)


# ── List ──────────────────────────────────────────────
@router.get("/", tags=["Billing - Scholarships"])
async def list_scholarships(
    institution_id: Optional[str] = None,
    scholarship_type: Optional[str] = None,
    certificate_status: Optional[str] = None,
    academic_year_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(StudentScholarship).where(StudentScholarship.deleted_at.is_(None))
    if institution_id:
        stmt = stmt.where(StudentScholarship.institution_id == institution_id)
    if scholarship_type:
        stmt = stmt.where(StudentScholarship.scholarship_type == scholarship_type)
    if certificate_status:
        stmt = stmt.where(StudentScholarship.certificate_status == certificate_status)
    if academic_year_id:
        stmt = stmt.where(StudentScholarship.academic_year_id == academic_year_id)

    # Count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(StudentScholarship.created_at.desc())
    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return {
        "items": [_enrich_scholarship_response(s) for s in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if size else 1,
    }


# ── Get one ───────────────────────────────────────────
@router.get("/{scholarship_id}", tags=["Billing - Scholarships"])
async def get_scholarship(scholarship_id: str, db: AsyncSession = Depends(get_db_session)):
    sch = (await db.execute(
        select(StudentScholarship).where(StudentScholarship.id == scholarship_id)
    )).scalar_one_or_none()
    if not sch:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    return _enrich_scholarship_response(sch)


# ── Submit Certificate ────────────────────────────────
@router.patch("/{scholarship_id}/submit-certificate", tags=["Billing - Scholarships"])
async def submit_certificate(
    scholarship_id: str,
    certificate_file: str = None,
    db: AsyncSession = Depends(get_db_session),
):
    sch = (await db.execute(
        select(StudentScholarship).where(StudentScholarship.id == scholarship_id)
    )).scalar_one_or_none()
    if not sch:
        raise HTTPException(status_code=404, detail="Scholarship not found")

    if certificate_file:
        sch.certificate_file = certificate_file
    sch.certificate_status = CertificateStatusEnum.SUBMITTED
    sch.submitted_at = datetime.utcnow()
    await db.commit()
    await db.refresh(sch)
    return _enrich_scholarship_response(sch)


# ── Review (Approve / Reject) ────────────────────────
@router.patch("/{scholarship_id}/review", tags=["Billing - Scholarships"])
async def review_certificate(
    scholarship_id: str,
    approve: bool = True,
    reviewer_id: Optional[str] = None,
    rejection_reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    sch = (await db.execute(
        select(StudentScholarship).where(StudentScholarship.id == scholarship_id)
    )).scalar_one_or_none()
    if not sch:
        raise HTTPException(status_code=404, detail="Scholarship not found")

    if approve:
        sch.certificate_status = CertificateStatusEnum.APPROVED
        sch.approved_at = datetime.utcnow()
    else:
        sch.certificate_status = CertificateStatusEnum.REJECTED
        sch.rejection_reason = rejection_reason

    sch.reviewed_at = datetime.utcnow()
    if reviewer_id:
        sch.reviewed_by = reviewer_id

    await db.commit()
    await db.refresh(sch)
    return _enrich_scholarship_response(sch)


# ── Mark Amount Received ──────────────────────────────
@router.patch("/{scholarship_id}/mark-amount-received", tags=["Billing - Scholarships"])
async def mark_amount_received(
    scholarship_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    sch = (await db.execute(
        select(StudentScholarship).where(StudentScholarship.id == scholarship_id)
    )).scalar_one_or_none()
    if not sch:
        raise HTTPException(status_code=404, detail="Scholarship not found")

    if sch.certificate_status != CertificateStatusEnum.APPROVED:
        raise HTTPException(status_code=400, detail="Certificate must be APPROVED first")

    sch.amount_received = True
    sch.amount_received_at = datetime.utcnow()
    await db.commit()
    await db.refresh(sch)
    return _enrich_scholarship_response(sch)


# ── Multi-Receipt Generation ─────────────────────────
@router.post("/multi-receipt", tags=["Billing - Scholarships"])
async def generate_multi_receipts(
    payload: MultiReceiptRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Bulk generate scholarship receipts for all qualifying students:
    - certificate_status = APPROVED
    - amount_received = True
    - receipt_id IS NULL (not yet processed)
    
    For each student: applies the scholarship amount as a payment
    against their outstanding invoices.
    """
    from sqlalchemy import text

    stmt = select(StudentScholarship).where(
        StudentScholarship.institution_id == payload.institution_id,
        StudentScholarship.scholarship_type == payload.scholarship_type,
        StudentScholarship.certificate_status == CertificateStatusEnum.APPROVED.value,
        StudentScholarship.amount_received == True,
        StudentScholarship.receipt_id.is_(None),
        StudentScholarship.deleted_at.is_(None),
    )
    if payload.academic_year_id:
        stmt = stmt.where(StudentScholarship.academic_year_id == payload.academic_year_id)
    if payload.student_ids:
        stmt = stmt.where(StudentScholarship.student_id.in_(payload.student_ids))

    result = await db.execute(stmt)
    scholarships = result.scalars().all()

    if not scholarships:
        return MultiReceiptResponse(
            processed_count=0, total_amount=0, receipt_numbers=[], failed_count=0
        )

    processed = 0
    total_amount = Decimal(0)
    receipt_numbers = []
    failures = []

    for sch in scholarships:
        try:
            # Find the student's outstanding invoices
            inv_stmt = select(Invoice).where(
                Invoice.student_id == sch.student_id,
                Invoice.status.in_([PaymentStatusEnum.PENDING, PaymentStatusEnum.PARTIAL]),
                Invoice.deleted_at.is_(None) if hasattr(Invoice, 'deleted_at') else True,
            ).order_by(Invoice.issue_date.asc())
            inv_result = await db.execute(inv_stmt)
            invoices = inv_result.scalars().all()

            remaining = Decimal(str(sch.amount))
            if remaining <= 0:
                continue

            # Generate a receipt number for the scholarship
            today_str = datetime.utcnow().strftime("%Y%m%d")
            type_code = sch.scholarship_type.value if hasattr(sch.scholarship_type, 'value') else str(sch.scholarship_type)
            seq_result = await db.execute(
                text("SELECT COUNT(*) FROM payments WHERE receipt_number LIKE :prefix"),
                {"prefix": f"SCH-{type_code}-{today_str}-%"},
            )
            seq = (seq_result.scalar() or 0) + 1
            receipt_number = f"SCH-{type_code}-{today_str}-{seq:04d}"

            # Apply payment across invoices until scholarship amount exhausted
            payment_created = False
            for invoice in invoices:
                if remaining <= 0:
                    break
                balance = Decimal(str(invoice.balance_due or 0))
                if balance <= 0:
                    continue

                pay_amount = min(remaining, balance)
                payment = Payment(
                    invoice_id=invoice.id,
                    amount=pay_amount,
                    payment_method="SCHOLARSHIP",
                    receipt_number=receipt_number if not payment_created else f"{receipt_number}-{invoice.invoice_number}",
                    notes=f"{type_code} Scholarship - Auto-generated multi-receipt",
                )
                db.add(payment)
                await db.flush()

                # Update invoice
                old_status = invoice.status
                invoice.paid_amount = (invoice.paid_amount or Decimal(0)) + pay_amount
                invoice.balance_due = max(Decimal(0), invoice.amount - invoice.paid_amount)
                if invoice.paid_amount >= invoice.amount:
                    invoice.status = PaymentStatusEnum.PAID
                elif invoice.paid_amount > 0:
                    invoice.status = PaymentStatusEnum.PARTIAL

                db.add(InvoiceStatusHistory(
                    invoice_id=invoice.id,
                    from_status=old_status,
                    to_status=invoice.status,
                    remarks=f"{type_code} scholarship multi-receipt",
                ))

                remaining -= pay_amount
                payment_created = True

                # Link the first payment to the scholarship record
                if sch.receipt_id is None:
                    sch.receipt_id = payment.id

            if payment_created:
                processed += 1
                total_amount += Decimal(str(sch.amount)) - remaining
                receipt_numbers.append(receipt_number)

        except Exception as e:
            logger.error(f"Multi-receipt failed for scholarship {sch.id}: {e}")
            failures.append({"scholarship_id": str(sch.id), "error": str(e)})

    if processed > 0:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=f"Commit failed: {e}")

    return MultiReceiptResponse(
        processed_count=processed,
        total_amount=total_amount,
        receipt_numbers=receipt_numbers,
        failed_count=len(failures),
        failed_details=failures if failures else None,
    )


# ── Dashboard ─────────────────────────────────────────
@router.get("/dashboard/summary", tags=["Billing - Scholarships"])
async def scholarship_dashboard(
    institution_id: Optional[str] = None,
    academic_year_id: Optional[str] = None,
    scholarship_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    base = select(StudentScholarship).where(StudentScholarship.deleted_at.is_(None))
    if institution_id:
        base = base.where(StudentScholarship.institution_id == institution_id)
    if academic_year_id:
        base = base.where(StudentScholarship.academic_year_id == academic_year_id)
    if scholarship_type:
        base = base.where(StudentScholarship.scholarship_type == scholarship_type)

    result = await db.execute(base)
    all_records = result.scalars().all()

    counts = {s.value: 0 for s in CertificateStatusEnum}
    amount_received_count = 0
    receipts_count = 0
    total_amt = Decimal(0)

    for r in all_records:
        status_val = r.certificate_status.value if hasattr(r.certificate_status, 'value') else str(r.certificate_status)
        if status_val in counts:
            counts[status_val] += 1
        if r.amount_received:
            amount_received_count += 1
        if r.receipt_id:
            receipts_count += 1
        total_amt += Decimal(str(r.amount or 0))

    return ScholarshipDashboardResponse(
        not_submitted=counts.get("NOT_SUBMITTED", 0),
        submitted=counts.get("SUBMITTED", 0),
        under_review=counts.get("UNDER_REVIEW", 0),
        approved=counts.get("APPROVED", 0),
        rejected=counts.get("REJECTED", 0),
        amount_received=amount_received_count,
        receipts_generated=receipts_count,
        total_amount=total_amt,
    )
