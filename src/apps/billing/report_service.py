from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional, List, Any
from sqlalchemy import func, select, and_, or_, literal, Date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.models.billing.application_fees import Invoice, Payment, InvoiceLineItem, FeeHead
from common.models.billing.cash_counter import CashCounter
from common.models.admission.admission_entry import (
    AdmissionStudent,
    AdmissionStudentProgramDetails,
    AdmissionStudentPersonalDetails,
)
from common.models.master.institution import Institution, Department
from common.models.master.annual_task import AcademicYear

class BillingReportService:
    async def get_general_ledger(
        self,
        db: AsyncSession,
        institution_id: UUID,
        department_id: UUID | None = None,
        academic_year_id: UUID | None = None,
        degree_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        student_id: UUID | None = None,
        search: Optional[str] = None,
    ):
        # Base filter logic (applied to everything)
        def apply_common_filters(stmt, model, current_student_id):
            # This assumes AdmissionStudent and AdmissionStudentProgramDetails are already joined
            if department_id:
                stmt = stmt.where(AdmissionStudentProgramDetails.department_id == department_id)
            if academic_year_id:
                stmt = stmt.where(AdmissionStudentProgramDetails.academic_year_id == academic_year_id)
            if degree_id:
                stmt = stmt.where(AdmissionStudentProgramDetails.course_id == degree_id)
            if student_id:
                stmt = stmt.where(current_student_id == student_id)
            if search:
                search_filter = or_(
                    AdmissionStudent.name.ilike(f"%{search}%"),
                    AdmissionStudent.application_number.ilike(f"%{search}%")
                )
                stmt = stmt.where(search_filter)
            return stmt

        # 1. Opening Balance Calculation
        # Sum of Invoices
        opening_debits_stmt = select(func.sum(Invoice.amount)).join(AdmissionStudent, Invoice.student_id == AdmissionStudent.id).join(AdmissionStudentProgramDetails, AdmissionStudent.id == AdmissionStudentProgramDetails.admission_student_id)
        opening_debits_stmt = opening_debits_stmt.where(Invoice.institution_id == institution_id)
        opening_debits_stmt = apply_common_filters(opening_debits_stmt, Invoice, Invoice.student_id)
        if start_date:
            opening_debits_stmt = opening_debits_stmt.where(Invoice.issue_date < start_date)
            
        # Sum of Payments
        opening_credits_stmt = select(func.sum(Payment.amount)).join(Invoice, Payment.invoice_id == Invoice.id).join(AdmissionStudent, Invoice.student_id == AdmissionStudent.id).join(AdmissionStudentProgramDetails, AdmissionStudent.id == AdmissionStudentProgramDetails.admission_student_id)
        opening_credits_stmt = opening_credits_stmt.where(Invoice.institution_id == institution_id)
        opening_credits_stmt = apply_common_filters(opening_credits_stmt, Payment, Invoice.student_id)
        if start_date:
            opening_credits_stmt = opening_credits_stmt.where(func.cast(Payment.payment_date, Date) < start_date)

        opening_debits = (await db.execute(opening_debits_stmt)).scalar() or 0
        opening_credits = (await db.execute(opening_credits_stmt)).scalar() or 0
        
        opening_balance = Decimal(str(opening_debits)) - Decimal(str(opening_credits))

        # 2. Main Transactions (within date range)
        debits_stmt = select(
            Invoice.issue_date.label("date"),
            literal("Invoice").label("type"),
            literal("Invoice").label("source"),
            Invoice.invoice_number.label("reference"),
            AdmissionStudent.name.label("student_name"),
            Invoice.notes.label("description"),
            Invoice.amount.label("debit"),
            literal(Decimal("0")).label("credit")
        ).join(AdmissionStudent, Invoice.student_id == AdmissionStudent.id).join(AdmissionStudentProgramDetails, AdmissionStudent.id == AdmissionStudentProgramDetails.admission_student_id)
        
        debits_stmt = debits_stmt.where(Invoice.institution_id == institution_id)
        debits_stmt = apply_common_filters(debits_stmt, Invoice, Invoice.student_id)
        if start_date:
            debits_stmt = debits_stmt.where(Invoice.issue_date >= start_date)
        if end_date:
            debits_stmt = debits_stmt.where(Invoice.issue_date <= end_date)
            
        credits_stmt = select(
            func.cast(Payment.payment_date, Date).label("date"),
            literal("Payment").label("type"),
            literal("Receipt").label("source"),
            Payment.receipt_number.label("reference"),
            AdmissionStudent.name.label("student_name"),
            Payment.notes.label("description"),
            literal(Decimal("0")).label("debit"),
            Payment.amount.label("credit")
        ).join(Invoice, Payment.invoice_id == Invoice.id).join(AdmissionStudent, Invoice.student_id == AdmissionStudent.id).join(AdmissionStudentProgramDetails, AdmissionStudent.id == AdmissionStudentProgramDetails.admission_student_id)
        
        credits_stmt = credits_stmt.where(Invoice.institution_id == institution_id)
        credits_stmt = apply_common_filters(credits_stmt, Payment, Invoice.student_id)
        if start_date:
            credits_stmt = credits_stmt.where(func.cast(Payment.payment_date, Date) >= start_date)
        if end_date:
            credits_stmt = credits_stmt.where(func.cast(Payment.payment_date, Date) <= end_date)
            
        # Combine and execute
        from sqlalchemy import union_all, text
        combined = union_all(debits_stmt, credits_stmt).alias("ledger")
        main_stmt = select(combined).order_by(text("date"))
        
        result = await db.execute(main_stmt)
        rows = result.all()
        
        entries = []
        current_balance = opening_balance
        total_debit = Decimal("0")
        total_credit = Decimal("0")
        
        for row in rows:
            debit = Decimal(str(row.debit))
            credit = Decimal(str(row.credit))
            current_balance = current_balance + debit - credit
            total_debit += debit
            total_credit += credit
            
            entries.append({
                "entry_date": row.date.isoformat() if row.date else None,
                "entry_type": row.type,
                "source": row.source,
                "reference": row.reference,
                "student_name": row.student_name,
                "description": row.description,
                "debit": debit,
                "credit": credit,
                "running_balance": current_balance
            })
            
        return {
            "opening_balance": opening_balance,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": current_balance,
            "entries": entries
        }

    async def get_collection_report(
        self,
        db: AsyncSession,
        institution_id: UUID | None = None,
        department_id: UUID | None = None,
        academic_year_id: UUID | None = None,
        payment_mode: str | None = None,
        fee_head_id: UUID | None = None,
        cash_counter_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        search: str | None = None,
    ):
        # Base query for payments
        stmt = (
            select(
                Payment.id,
                Payment.amount,
                Payment.payment_method,
                Payment.payment_date,
                Payment.receipt_number,
                Payment.transaction_id,
                AdmissionStudent.name.label("student_name"),
                AdmissionStudent.application_number,
                AcademicYear.year_name.label("batch_name"),
                Institution.name.label("college_name"),
                Department.name.label("department_name"),
                CashCounter.name.label("counter_name"),
            )
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .join(AdmissionStudent, Invoice.student_id == AdmissionStudent.id)
            .outerjoin(AdmissionStudentProgramDetails, AdmissionStudent.id == AdmissionStudentProgramDetails.admission_student_id)
            .outerjoin(AcademicYear, AdmissionStudentProgramDetails.academic_year_id == AcademicYear.id)
            .outerjoin(Institution, Invoice.institution_id == Institution.id)
            .outerjoin(Department, AdmissionStudentProgramDetails.department_id == Department.id)
            .outerjoin(CashCounter, Payment.cash_counter_id == CashCounter.id)
        )

        filters = []
        if institution_id:
            filters.append(Invoice.institution_id == institution_id)
        if department_id:
            filters.append(AdmissionStudentProgramDetails.department_id == department_id)
        if academic_year_id:
            filters.append(AdmissionStudentProgramDetails.academic_year_id == academic_year_id)
        if payment_mode and payment_mode != "All":
            filters.append(Payment.payment_method == payment_mode)
        if cash_counter_id:
            filters.append(Payment.cash_counter_id == cash_counter_id)
        if start_date:
            # Payment.payment_date is DateTime, compare with start of day
            filters.append(Payment.payment_date >= datetime.combine(start_date, datetime.min.time()))
        if end_date:
            filters.append(Payment.payment_date <= datetime.combine(end_date, datetime.max.time()))
        
        if fee_head_id:
            # Join with line items if fee_head_id is provided
            # Note: One payment might cover multiple heads, but here we filter if ANY line item matches
            stmt = stmt.join(InvoiceLineItem, Invoice.id == InvoiceLineItem.invoice_id)
            filters.append(InvoiceLineItem.fee_head_id == fee_head_id)

        if search:
            search_pattern = f"%{search}%"
            filters.append(
                or_(
                    Payment.receipt_number.ilike(search_pattern),
                    AdmissionStudent.application_number.ilike(search_pattern),
                    AdmissionStudent.name.ilike(search_pattern),
                    Institution.name.ilike(search_pattern),
                )
            )

        if filters:
            stmt = stmt.where(and_(*filters))

        stmt = stmt.order_by(Payment.payment_date.desc())
        
        result = await db.execute(stmt)
        rows = result.all()

        # Grouping and aggregation (Optional, but let's return raw data for now and see)
        # Actually the frontend wants summary rows. 
        # But wait, if I aggregate in SQL, I can't easily get student names.
        # The screenshot shows a list of collections.
        
        items = []
        for row in rows:
            # We need to get "Payment Type" (Fee Head). 
            # If multiple heads, we can list them or pick first.
            # Let's fetch heads for this payment's invoice.
            # To be efficient, we should have joined them or use another query.
            
            # For now, let's just return the raw rows.
            items.append({
                "id": str(row.id),
                "date": row.payment_date.date().isoformat() if row.payment_date else None,
                "mode": row.payment_method,
                "amount": float(row.amount),
                "receipt_number": row.receipt_number,
                "student_name": row.student_name,
                "application_number": row.application_number,
                "batch": row.batch_name,
                "college": row.college_name,
                "department": row.department_name,
                "counter": row.counter_name,
                "status": "success", # Payment exists = success
                "paymentType": "Fees", # Placeholder or derived
            })

        return items

    async def get_collection_summary(
        self,
        db: AsyncSession,
        **kwargs
    ):
        items = await self.get_collection_report(db, **kwargs)
        total_amount = sum(item["amount"] for item in items)
        total_transactions = len(items)
        
        return {
            "total_amount": total_amount,
            "total_transactions": total_transactions,
            "record_count": len(items),
            "items": items
        }

    async def get_student_fee_report(
        self,
        db: AsyncSession,
        institution_id: UUID | None = None,
        department_id: UUID | None = None,
        academic_year_id: UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        search: str | None = None,
    ):
        # Subquery for paid amount per student
        paid_subquery = (
            select(
                Invoice.student_id,
                func.sum(Payment.amount).label("total_paid")
            )
            .join(Payment, Invoice.id == Payment.invoice_id)
            .group_by(Invoice.student_id)
        ).subquery()

        # Subquery for total fee per student
        fee_subquery = (
            select(
                Invoice.student_id,
                func.sum(Invoice.amount).label("total_fee")
            )
            .group_by(Invoice.student_id)
        ).subquery()

        # Main query for students with their fee summaries
        stmt = (
            select(
                AdmissionStudent.id,
                AdmissionStudent.name.label("student_name"),
                AdmissionStudent.application_number,
                AdmissionStudent.roll_number,
                AdmissionStudent.section,
                AcademicYear.year_name.label("batch_name"),
                Institution.name.label("college_name"),
                Department.name.label("department_name"),
                func.coalesce(fee_subquery.c.total_fee, 0).label("total_fee"),
                func.coalesce(paid_subquery.c.total_paid, 0).label("paid_amount"),
            )
            .outerjoin(AdmissionStudentProgramDetails, AdmissionStudent.id == AdmissionStudentProgramDetails.admission_student_id)
            .outerjoin(AcademicYear, AdmissionStudentProgramDetails.academic_year_id == AcademicYear.id)
            .outerjoin(Institution, AdmissionStudentProgramDetails.institution_id == Institution.id)
            .outerjoin(Department, AdmissionStudentProgramDetails.department_id == Department.id)
            .outerjoin(fee_subquery, AdmissionStudent.id == fee_subquery.c.student_id)
            .outerjoin(paid_subquery, AdmissionStudent.id == paid_subquery.c.student_id)
        )

        filters = []
        if institution_id:
            filters.append(AdmissionStudentProgramDetails.institution_id == institution_id)
        if department_id:
            filters.append(AdmissionStudentProgramDetails.department_id == department_id)
        if academic_year_id:
            filters.append(AdmissionStudentProgramDetails.academic_year_id == academic_year_id)
        
        if search:
            search_pattern = f"%{search}%"
            filters.append(
                or_(
                    AdmissionStudent.application_number.ilike(search_pattern),
                    AdmissionStudent.name.ilike(search_pattern),
                    AdmissionStudent.roll_number.ilike(search_pattern),
                )
            )

        if filters:
            stmt = stmt.where(and_(*filters))

        result = await db.execute(stmt)
        rows = result.all()

        items = []
        total_paid = Decimal(0)
        total_pending = Decimal(0)

        for row in rows:
            pending = Decimal(row.total_fee) - Decimal(row.paid_amount)
            
            # Determine status
            status = "Pending"
            if row.paid_amount > 0:
                status = "Active"
            if pending <= 0 and row.total_fee > 0:
                status = "Cleared"

            items.append({
                "student_id": row.id,
                "student_name": row.student_name,
                "application_number": row.application_number,
                "roll_number": row.roll_number,
                "section": row.section,
                "batch_name": row.batch_name,
                "college_name": row.college_name,
                "department_name": row.department_name,
                "total_fee": float(row.total_fee),
                "paid_amount": float(row.paid_amount),
                "pending_amount": float(pending),
                "status": status
            })
            total_paid += Decimal(str(row.paid_amount))
            total_pending += pending

        return {
            "items": items,
            "total_students": len(items),
            "total_paid": float(total_paid),
            "total_pending": float(total_pending)
        }

