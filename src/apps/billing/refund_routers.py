"""
Refund management routes:
- Initiate refund (cancel receipt + partial refund)
- Approve refund  
- Process refund (creates cancellation fee receipt, records refund)
- List & detail
"""
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from components.db.db import get_db_session
from common.models.billing.refund import Refund, RefundStatusEnum, RefundMethodEnum
from common.models.billing.application_fees import (
    Invoice,
    InvoiceLineItem,
    Payment,
    PaymentStatusEnum,
    InvoiceStatusHistory,
)
from common.models.admission.admission_entry import AdmissionStudent, AdmissionStatusEnum
from common.schemas.billing.refund_schemas import (
    RefundInitiateRequest,
    RefundApproveRequest,
    RefundProcessRequest,
    RefundResponse,
)
from apps.billing.services import billing_service
from logs.logging import logger

router = APIRouter()


def _enrich_refund(r: Refund) -> dict:
    data = {
        "id": r.id,
        "student_id": r.student_id,
        "institution_id": r.institution_id,
        "original_payment_id": r.original_payment_id,
        "original_invoice_id": r.original_invoice_id,
        "original_amount": float(r.original_amount),
        "cancellation_fee": float(r.cancellation_fee),
        "refund_amount": float(r.refund_amount),
        "refund_method": r.refund_method.value if hasattr(r.refund_method, "value") else r.refund_method,
        "refund_reference": r.refund_reference,
        "cancellation_receipt_number": r.cancellation_receipt_number,
        "refund_receipt_number": r.refund_receipt_number,
        "status": r.status.value if hasattr(r.status, "value") else str(r.status),
        "reason": r.reason,
        "initiated_by": r.initiated_by,
        "approved_by": r.approved_by,
        "processed_at": r.processed_at,
        "meta": r.meta,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }
    if r.student:
        data["student_name"] = r.student.name
        data["application_number"] = r.student.application_number
    return data


# ── Initiate Refund ───────────────────────────────────
@router.post("/initiate", tags=["Billing - Refunds"])
async def initiate_refund(
    payload: RefundInitiateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Initiate a refund for a student's payment.
    Operator specifies the cancellation fee (amount retained by college).
    Refund amount = original payment - cancellation fee.
    """
    # Validate student
    student = (await db.execute(
        select(AdmissionStudent).where(AdmissionStudent.id == payload.student_id)
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Validate payment
    payment = (await db.execute(
        select(Payment).where(Payment.id == payload.payment_id)
    )).scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Validate cancellation fee
    original_amount = Decimal(str(payment.amount))
    cancellation_fee = Decimal(str(payload.cancellation_fee))
    if cancellation_fee < 0:
        raise HTTPException(status_code=400, detail="Cancellation fee cannot be negative")
    if cancellation_fee > original_amount:
        raise HTTPException(status_code=400, detail="Cancellation fee cannot exceed original payment")

    refund_amount = original_amount - cancellation_fee

    # Check for existing active refund on this payment
    existing = (await db.execute(
        select(Refund).where(
            Refund.original_payment_id == payload.payment_id,
            Refund.status.notin_([RefundStatusEnum.REJECTED.value, RefundStatusEnum.COMPLETED.value]),
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="An active refund request already exists for this payment")

    refund = Refund(
        student_id=payload.student_id,
        institution_id=student.institution_id,
        original_payment_id=payload.payment_id,
        original_invoice_id=payment.invoice_id,
        original_amount=original_amount,
        cancellation_fee=cancellation_fee,
        refund_amount=refund_amount,
        refund_method=RefundMethodEnum(payload.refund_method) if payload.refund_method else None,
        refund_reference=payload.refund_reference,
        status=RefundStatusEnum.INITIATED,
        reason=payload.reason,
    )
    db.add(refund)
    await db.commit()
    await db.refresh(refund)
    return _enrich_refund(refund)


# ── Approve Refund ────────────────────────────────────
@router.post("/{refund_id}/approve", tags=["Billing - Refunds"])
async def approve_refund(
    refund_id: str,
    payload: RefundApproveRequest = None,
    db: AsyncSession = Depends(get_db_session),
):
    refund = (await db.execute(
        select(Refund).where(Refund.id == refund_id)
    )).scalar_one_or_none()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")

    if refund.status != RefundStatusEnum.INITIATED:
        raise HTTPException(status_code=400, detail=f"Cannot approve refund in {refund.status.value} status")

    refund.status = RefundStatusEnum.APPROVED
    if payload and payload.approved_by:
        refund.approved_by = payload.approved_by
    await db.commit()
    await db.refresh(refund)
    return _enrich_refund(refund)


# ── Process Refund ────────────────────────────────────
@router.post("/{refund_id}/process", tags=["Billing - Refunds"])
async def process_refund(
    refund_id: str,
    payload: RefundProcessRequest = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Execute the refund:
    1. Cancel the original invoice
    2. If cancellation_fee > 0: create new invoice + payment for cancellation fee
    3. Record refund receipt numbers
    4. Update student status to WITHDRAWN
    """
    refund = (await db.execute(
        select(Refund).where(Refund.id == refund_id)
    )).scalar_one_or_none()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")

    if refund.status != RefundStatusEnum.APPROVED:
        raise HTTPException(status_code=400, detail=f"Refund must be APPROVED to process (current: {refund.status.value})")

    try:
        # 1. Cancel the original invoice
        original_invoice = (await db.execute(
            select(Invoice).where(Invoice.id == refund.original_invoice_id)
        )).scalar_one_or_none()

        if original_invoice:
            old_status = original_invoice.status
            original_invoice.status = PaymentStatusEnum.CANCELLED
            db.add(InvoiceStatusHistory(
                invoice_id=original_invoice.id,
                from_status=old_status,
                to_status=PaymentStatusEnum.CANCELLED,
                remarks=f"Cancelled for refund #{refund_id}",
            ))

        # Update refund method if provided
        if payload:
            if payload.refund_method:
                refund.refund_method = RefundMethodEnum(payload.refund_method)
            if payload.refund_reference:
                refund.refund_reference = payload.refund_reference

        # 2. Generate receipt numbers
        today_str = datetime.utcnow().strftime("%Y%m%d")
        inst_hex = str(refund.institution_id.hex[:6]).upper()

        # Cancellation fee receipt
        if refund.cancellation_fee > 0:
            seq_result = await db.execute(
                text("SELECT COUNT(*) FROM refunds WHERE cancellation_receipt_number LIKE :prefix"),
                {"prefix": f"CAN-{inst_hex}-{today_str}-%"},
            )
            cancel_seq = (seq_result.scalar() or 0) + 1
            cancel_receipt = f"CAN-{inst_hex}-{today_str}-{cancel_seq:04d}"
            refund.cancellation_receipt_number = cancel_receipt

            # Create a new invoice for the cancellation fee (already paid)
            cancel_invoice_number = await billing_service._generate_invoice_number(db, refund.institution_id)
            cancel_invoice = Invoice(
                institution_id=refund.institution_id,
                student_id=refund.student_id,
                invoice_number=cancel_invoice_number,
                amount=refund.cancellation_fee,
                paid_amount=refund.cancellation_fee,
                balance_due=0,
                status=PaymentStatusEnum.PAID,
                issue_date=date.today(),
                due_date=date.today(),
                notes=f"Cancellation fee retained from refund #{refund_id}",
            )
            db.add(cancel_invoice)
            await db.flush()

            # Line item
            db.add(InvoiceLineItem(
                invoice_id=cancel_invoice.id,
                description="Admission Cancellation Fee",
                amount=refund.cancellation_fee,
                net_amount=refund.cancellation_fee,
            ))

            # Payment record for cancellation fee
            cancel_payment = Payment(
                invoice_id=cancel_invoice.id,
                amount=refund.cancellation_fee,
                payment_method="ADJUSTMENT",
                receipt_number=cancel_receipt,
                notes=f"Cancellation fee from refund #{refund_id}",
            )
            db.add(cancel_payment)

        # Refund receipt
        seq_result = await db.execute(
            text("SELECT COUNT(*) FROM refunds WHERE refund_receipt_number LIKE :prefix"),
            {"prefix": f"REF-{inst_hex}-{today_str}-%"},
        )
        ref_seq = (seq_result.scalar() or 0) + 1
        refund.refund_receipt_number = f"REF-{inst_hex}-{today_str}-{ref_seq:04d}"

        # 3. Update refund status
        refund.status = RefundStatusEnum.PROCESSED
        refund.processed_at = datetime.utcnow()

        # 4. Update student status to WITHDRAWN
        student = (await db.execute(
            select(AdmissionStudent).where(AdmissionStudent.id == refund.student_id)
        )).scalar_one_or_none()
        if student:
            student.status = AdmissionStatusEnum.WITHDRAWN

        await db.commit()
        await db.refresh(refund)
        return _enrich_refund(refund)

    except Exception as e:
        await db.rollback()
        logger.error(f"Refund processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ── Complete Refund ───────────────────────────────────
@router.post("/{refund_id}/complete", tags=["Billing - Refunds"])
async def complete_refund(
    refund_id: str,
    refund_reference: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Mark a processed refund as completed (money handed over to student)."""
    refund = (await db.execute(
        select(Refund).where(Refund.id == refund_id)
    )).scalar_one_or_none()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")

    if refund.status != RefundStatusEnum.PROCESSED:
        raise HTTPException(status_code=400, detail=f"Refund must be PROCESSED to complete")

    refund.status = RefundStatusEnum.COMPLETED
    if refund_reference:
        refund.refund_reference = refund_reference
    await db.commit()
    await db.refresh(refund)
    return _enrich_refund(refund)


# ── Reject Refund ─────────────────────────────────────
@router.post("/{refund_id}/reject", tags=["Billing - Refunds"])
async def reject_refund(
    refund_id: str,
    reason: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    refund = (await db.execute(
        select(Refund).where(Refund.id == refund_id)
    )).scalar_one_or_none()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")

    if refund.status not in (RefundStatusEnum.INITIATED, RefundStatusEnum.APPROVED):
        raise HTTPException(status_code=400, detail="Cannot reject refund in current status")

    refund.status = RefundStatusEnum.REJECTED
    if reason:
        refund.reason = reason
    await db.commit()
    await db.refresh(refund)
    return _enrich_refund(refund)


# ── List Refunds ──────────────────────────────────────
@router.get("/", tags=["Billing - Refunds"])
async def list_refunds(
    institution_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(Refund).where(Refund.deleted_at.is_(None))
    if institution_id:
        stmt = stmt.where(Refund.institution_id == institution_id)
    if status:
        stmt = stmt.where(Refund.status == status)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(Refund.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return {
        "items": [_enrich_refund(r) for r in items],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if size else 1,
    }


# ── Get Refund Detail ────────────────────────────────
@router.get("/{refund_id}", tags=["Billing - Refunds"])
async def get_refund(refund_id: str, db: AsyncSession = Depends(get_db_session)):
    refund = (await db.execute(
        select(Refund).where(Refund.id == refund_id)
    )).scalar_one_or_none()
    if not refund:
        raise HTTPException(status_code=404, detail="Refund not found")
    return _enrich_refund(refund)
