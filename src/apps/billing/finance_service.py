"""
Finance Service — Semester-wise demand generation, invoice generation
with payer_type awareness, and bulk receipt processing.

Extends the existing BillingService with new capabilities.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.models.billing.application_fees import (
    Invoice,
    InvoiceLineItem,
    InvoiceStatusHistory,
    Payment,
    PaymentStatusEnum,
)
from common.models.billing.bulk_receipt import BulkReceipt, BulkReceiptItem
from common.models.billing.demand import DemandBatch, DemandItem
from common.models.billing.fee_structure import (
    FeeStructure,
    FeeStructureItem,
    PayerTypeEnum,
)
from common.models.billing.concession import Concession
from logs.logging import logger


class FinanceService:
    """
    Handles semester-wise demand generation, payer-type-aware invoice
    creation, and bulk receipt (government payment) processing.
    """

    # ── Helpers ────────────────────────────────────────

    async def _generate_invoice_number(
        self, db: AsyncSession, institution_id: UUID
    ) -> str:
        from sqlalchemy import text

        today = datetime.utcnow().strftime("%Y%m%d")
        prefix = f"{institution_id.hex[:6].upper()}-{today}-"
        result = await db.execute(
            text(
                "SELECT invoice_number FROM invoices "
                "WHERE invoice_number LIKE :prefix "
                "ORDER BY invoice_number DESC LIMIT 1"
            ),
            {"prefix": f"{prefix}%"},
        )
        last = result.scalar_one_or_none()
        if not last:
            seq = 1
        else:
            try:
                seq = int(last.split("-")[-1]) + 1
            except Exception:
                seq = 1
        return f"{prefix}{seq:04d}"

    async def _get_student_concessions(
        self, db: AsyncSession, student_id: UUID
    ) -> list[Concession]:
        stmt = select(Concession).where(
            Concession.student_id == student_id,
            Concession.status == "approved",
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def _apply_concession(
        self,
        amount: float,
        concessions: list[Concession],
        fee_head_id: UUID | None,
        fee_sub_head_id: UUID | None,
    ) -> float:
        """Apply matching approved concessions to reduce amount."""
        for conc in concessions:
            head_match = conc.fee_head_id is None or conc.fee_head_id == fee_head_id
            sub_match = (
                conc.fee_sub_head_id is None
                or conc.fee_sub_head_id == fee_sub_head_id
            )
            if head_match and sub_match:
                if conc.percent and float(conc.percent) > 0:
                    amount -= amount * (float(conc.percent) / 100)
                elif conc.amount and float(conc.amount) > 0:
                    amount -= float(conc.amount)
        return max(0.0, round(amount, 2))

    # ── Semester-wise Demand Generation ────────────────

    async def generate_demand_batch(
        self,
        db: AsyncSession,
        fee_structure_id: UUID,
        institution_id: UUID,
        semester: int | None = None,
        year: int | None = None,
        filters: dict | None = None,
        name: str | None = None,
        apply_concessions: bool = True,
    ) -> dict:
        """
        Generate demand items for students matching filters, based on a
        fee structure. Supports semester-wise and year-wise breakdowns.

        If *semester* is provided, only that semester's amount is used.
        If *year* is provided (without semester), all semesters for that year
        are generated. If neither, all configured amounts are generated.
        """
        from common.models.admission.admission_entry import AdmissionStudent

        # 1. Load fee structure with items
        fs_stmt = (
            select(FeeStructure)
            .options(
                selectinload(FeeStructure.items).selectinload(FeeStructureItem.fee_head),
                selectinload(FeeStructure.items).selectinload(FeeStructureItem.fee_sub_head),
            )
            .where(
                FeeStructure.id == fee_structure_id,
                FeeStructure.institution_id == institution_id,
            )
        )
        fs_result = await db.execute(fs_stmt)
        fs = fs_result.scalar_one_or_none()
        if not fs:
            raise ValueError("Fee structure not found for this institution")

        # 2. Resolve matching students
        student_ids = await self._students_matching_filters(
            db, filters=filters, institution_id=institution_id
        )
        if not student_ids:
            return {
                "batch_id": None,
                "created_count": 0,
                "total_amount": 0.0,
                "student_count": 0,
                "message": "No students found matching criteria",
            }

        semesters_per_year = fs.semesters_per_year or 2

        # 3. Create batch
        batch_name = name or (
            f"Demand - Sem {semester}"
            if semester
            else f"Demand - Year {year}"
            if year
            else f"Demand Batch - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        )
        batch = DemandBatch(
            name=batch_name,
            institution_id=institution_id,
            fee_structure_id=fee_structure_id,
            filters={
                "semester": semester,
                "year": year,
                **(filters or {}),
            },
            status="generated",
            generated_at=datetime.utcnow(),
        )
        db.add(batch)
        await db.flush()

        # 4. Generate demands per student per item
        created_count = 0
        total_amount = 0.0
        skipped_duplicate = 0
        skipped_zero_amount = 0

        for student_id in student_ids:
            concessions = []
            if apply_concessions:
                concessions = await self._get_student_concessions(db, student_id)

            for item in fs.items:
                head_name = item.fee_head.name if item.fee_head else "Fee"
                sub_name = item.fee_sub_head.name if item.fee_sub_head else ""
                payer_type = item.payer_type or PayerTypeEnum.STUDENT

                demands_for_item = self._resolve_item_amounts(
                    item=item,
                    semester=semester,
                    year=year,
                    semesters_per_year=semesters_per_year,
                    head_name=head_name,
                    sub_name=sub_name,
                )

                for (amt, sem_num, year_num, desc) in demands_for_item:
                    if amt <= 0:
                        continue

                    # Apply concessions (only for STUDENT payer type)
                    final_amount = amt
                    if payer_type == PayerTypeEnum.STUDENT and concessions:
                        final_amount = self._apply_concession(
                            amt, concessions, item.fee_head_id, item.fee_sub_head_id
                        )

                    if final_amount <= 0:
                        skipped_zero_amount += 1
                        continue

                    # Duplicate check
                    exists = await self._demand_exists(
                        db, student_id, item.id, sem_num, year_num, batch.id
                    )
                    if exists:
                        skipped_duplicate += 1
                        continue

                    di = DemandItem(
                        batch_id=batch.id,
                        student_id=student_id,
                        fee_structure_id=fs.id,
                        fee_structure_item_id=item.id,
                        amount=final_amount,
                        fee_head_id=item.fee_head_id,
                        fee_sub_head_id=item.fee_sub_head_id,
                        semester=sem_num,
                        year=year_num,
                        payer_type=payer_type,
                        description=desc,
                        status="pending",
                    )
                    db.add(di)
                    created_count += 1
                    total_amount += final_amount

        await db.commit()

        logger.info(
            "demand_batch_generated batch_id={} created={} skipped_duplicate={} skipped_zero={} students={} total={}",
            batch.id, created_count, skipped_duplicate, skipped_zero_amount, len(student_ids), total_amount,
        )

        return {
            "batch_id": batch.id,
            "created_count": created_count,
            "skipped_count": skipped_duplicate + skipped_zero_amount,
            "skipped_duplicate": skipped_duplicate,
            "skipped_zero_amount": skipped_zero_amount,
            "student_count": len(student_ids),
            "total_amount": round(total_amount, 2),
            "message": f"Created {created_count} demand items for {len(student_ids)} students",
        }

    def _resolve_item_amounts(
        self,
        item: FeeStructureItem,
        semester: int | None,
        year: int | None,
        semesters_per_year: int,
        head_name: str,
        sub_name: str,
    ) -> list[tuple[float, int | None, int | None, str]]:
        """
        Return a list of (amount, semester_num, year_num, description) tuples
        for the given item, filtered by semester/year if provided.
        """
        results: list[tuple[float, int | None, int | None, str]] = []
        label = f"{head_name} - {sub_name}" if sub_name else head_name

        # --- Semester-based ---
        if item.amount_by_semester:
            for sem_str, sem_amt in item.amount_by_semester.items():
                sem_num = int(sem_str)
                year_num = ((sem_num - 1) // semesters_per_year) + 1
                amt = float(sem_amt or 0)

                if semester is not None and sem_num != semester:
                    continue
                if year is not None and year_num != year:
                    continue

                results.append(
                    (amt, sem_num, year_num, f"{label} - Sem {sem_num}")
                )

        # --- Year-based ---
        elif item.amount_by_year:
            for year_str, year_amt in item.amount_by_year.items():
                yr = int(year_str)
                amt = float(year_amt or 0)

                if year is not None and yr != year:
                    continue
                if semester is not None:
                    # If semester filter given but item is year-based,
                    # generate only if it matches the year derived from semester
                    target_year = ((semester - 1) // semesters_per_year) + 1
                    if yr != target_year:
                        continue

                results.append(
                    (amt, None, yr, f"{label} - Year {yr}")
                )

        # --- Flat amount ---
        else:
            amt = float(item.amount or 0)
            if amt > 0:
                if semester is not None or year is not None:
                    target_year = year or (
                        ((semester - 1) // semesters_per_year) + 1
                        if semester
                        else 1
                    )
                    if target_year != 1:
                        return results
                results.append((amt, semester, year or 1, label))

        return results

    async def _demand_exists(
        self,
        db: AsyncSession,
        student_id: UUID,
        fee_structure_item_id: UUID,
        semester: int | None,
        year: int | None,
        exclude_batch_id: UUID | None = None,
    ) -> bool:
        """Check if a matching pending demand already exists."""
        stmt = select(func.count(DemandItem.id)).where(
            DemandItem.student_id == student_id,
            DemandItem.fee_structure_item_id == fee_structure_item_id,
            DemandItem.status.in_(["pending", "invoiced"]),
        )
        if semester is not None:
            stmt = stmt.where(DemandItem.semester == semester)
        if year is not None:
            stmt = stmt.where(DemandItem.year == year)
        result = await db.execute(stmt)
        return (result.scalar() or 0) > 0

    async def _students_matching_filters(
        self,
        db: AsyncSession,
        filters: dict | None,
        institution_id: UUID | None = None,
    ) -> list[UUID]:
        """Resolve student IDs matching the given filters."""
        from common.models.admission.admission_entry import AdmissionStudent
        from common.models.master.institution import Course, Department
        from common.models.master.admission_masters import SeatQuota

        filters = filters or {}
        stmt = select(AdmissionStudent.id).where(
            AdmissionStudent.deleted_at.is_(None)
        )

        if institution_id:
            stmt = stmt.where(AdmissionStudent.institution_id == institution_id)

        if filters.get("department_id"):
            stmt = stmt.where(
                AdmissionStudent.department_id == filters["department_id"]
            )
        if filters.get("degree_id") or filters.get("course_id"):
            course_id = filters.get("degree_id") or filters.get("course_id")
            stmt = stmt.where(AdmissionStudent.course_id == course_id)
        if filters.get("admission_type_id"):
            stmt = stmt.where(
                AdmissionStudent.admission_type_id == filters["admission_type_id"]
            )
        if filters.get("batch"):
            stmt = stmt.where(AdmissionStudent.year == filters["batch"])
        if filters.get("admission_year_id") or filters.get("academic_year_id"):
            ay_id = filters.get("admission_year_id") or filters.get("academic_year_id")
            stmt = stmt.where(AdmissionStudent.academic_year_id == ay_id)
        if filters.get("admission_quota_id"):
            stmt = stmt.where(
                AdmissionStudent.admission_quota_id == filters["admission_quota_id"]
            )
        if filters.get("gender"):
            stmt = stmt.where(AdmissionStudent.gender == filters["gender"])

        stmt = stmt.distinct()
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ── Invoice Generation from Demands ────────────────

    async def generate_invoices_from_demands(
        self,
        db: AsyncSession,
        batch_id: UUID | None = None,
        student_id: UUID | None = None,
        payer_type: str | None = None,
    ) -> dict:
        """
        Generate invoices from pending demand items. Groups demands by
        (student_id, payer_type) and creates one invoice per group.
        """
        from common.models.admission.admission_entry import AdmissionStudent

        stmt = select(DemandItem).where(
            DemandItem.status == "pending",
            DemandItem.invoice_id.is_(None),
        )
        if batch_id:
            stmt = stmt.where(DemandItem.batch_id == batch_id)
        if student_id:
            stmt = stmt.where(DemandItem.student_id == student_id)
        if payer_type:
            stmt = stmt.where(DemandItem.payer_type == payer_type)

        result = await db.execute(stmt)
        demands = list(result.scalars().all())

        if not demands:
            return {
                "invoice_count": 0,
                "total_amount": 0.0,
                "message": "No pending demands found",
            }

        # Group by (student_id, payer_type)
        groups: dict[tuple[UUID, str], list[DemandItem]] = {}
        for d in demands:
            key = (d.student_id, d.payer_type.value if d.payer_type else "STUDENT")
            groups.setdefault(key, []).append(d)

        invoice_count = 0
        total_amount = 0.0

        for (sid, pt), group_demands in groups.items():
            # Get student for institution_id
            stu_stmt = select(AdmissionStudent).where(AdmissionStudent.id == sid)
            stu_res = await db.execute(stu_stmt)
            student = stu_res.scalar_one_or_none()
            if not student:
                continue

            inv_total = sum(float(d.amount) for d in group_demands)
            invoice_number = await self._generate_invoice_number(
                db, student.institution_id
            )

            invoice = Invoice(
                institution_id=student.institution_id,
                student_id=sid,
                invoice_number=invoice_number,
                amount=Decimal(str(round(inv_total, 2))),
                paid_amount=Decimal("0"),
                balance_due=Decimal(str(round(inv_total, 2))),
                status=PaymentStatusEnum.PENDING,
                issue_date=date.today(),
                due_date=date.today(),
            )
            db.add(invoice)
            await db.flush()

            for d in group_demands:
                line = InvoiceLineItem(
                    invoice_id=invoice.id,
                    fee_head_id=d.fee_head_id,
                    description=d.description or "Fee",
                    amount=Decimal(str(d.amount)),
                    net_amount=Decimal(str(d.amount)),
                )
                db.add(line)
                d.invoice_id = invoice.id
                d.status = "invoiced"
                db.add(d)

            invoice_count += 1
            total_amount += inv_total

        await db.commit()

        return {
            "invoice_count": invoice_count,
            "total_amount": round(total_amount, 2),
            "message": f"Created {invoice_count} invoices totalling {total_amount}",
        }

    # ── Student Fee Visibility ─────────────────────────

    async def get_student_fees(
        self,
        db: AsyncSession,
        student_id: UUID,
        include_government: bool = False,
    ) -> dict:
        """
        Get fee summary for a student. By default only shows STUDENT
        payer_type demands/invoices (for student portal). Admin portal
        passes include_government=True.
        """
        from common.models.admission.admission_entry import AdmissionStudent

        stu_stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
        stu_res = await db.execute(stu_stmt)
        student = stu_res.scalar_one_or_none()
        if not student:
            raise ValueError("Student not found")

        # Demands
        demand_stmt = select(DemandItem).where(
            DemandItem.student_id == student_id,
            DemandItem.deleted_at.is_(None),
        )
        if not include_government:
            demand_stmt = demand_stmt.where(
                DemandItem.payer_type == PayerTypeEnum.STUDENT
            )
        demand_res = await db.execute(demand_stmt)
        demands = list(demand_res.scalars().all())

        # Invoices
        invoice_ids = {d.invoice_id for d in demands if d.invoice_id}
        invoices = []
        if invoice_ids:
            inv_stmt = (
                select(Invoice)
                .options(
                    selectinload(Invoice.line_items),
                    selectinload(Invoice.payments),
                )
                .where(Invoice.id.in_(invoice_ids))
                .order_by(Invoice.issue_date.desc())
            )
            inv_res = await db.execute(inv_stmt)
            invoices = list(inv_res.scalars().all())

        total_demand = sum(float(d.amount) for d in demands)
        total_paid = sum(
            float(inv.paid_amount or 0)
            for inv in invoices
        )
        balance = total_demand - total_paid

        return {
            "student_id": student.id,
            "name": student.name,
            "total_demand": round(total_demand, 2),
            "total_paid": round(total_paid, 2),
            "balance_due": round(max(0, balance), 2),
            "demands": [
                {
                    "id": d.id,
                    "description": d.description,
                    "amount": float(d.amount),
                    "semester": d.semester,
                    "year": d.year,
                    "status": d.status,
                    "payer_type": d.payer_type.value if d.payer_type else "STUDENT",
                    "fee_head_id": d.fee_head_id,
                    "fee_sub_head_id": d.fee_sub_head_id,
                }
                for d in demands
            ],
            "invoices": [
                {
                    "id": inv.id,
                    "invoice_number": inv.invoice_number,
                    "amount": float(inv.amount),
                    "paid_amount": float(inv.paid_amount or 0),
                    "balance_due": float(inv.balance_due or 0),
                    "status": inv.status.value,
                    "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
                }
                for inv in invoices
            ],
        }

    # ── Bulk Receipt Processing ────────────────────────

    async def create_bulk_receipt(
        self, db: AsyncSession, payload
    ) -> dict:
        """
        Create a bulk receipt and apply payments to each linked invoice.
        Used for government or scholarship payments that cover many students.
        """
        data = payload.dict(exclude_unset=True)
        items_data = data.pop("items", [])
        payer_type_str = data.get("payer_type", "GOVERNMENT")

        try:
            payer_type = PayerTypeEnum(payer_type_str)
        except ValueError:
            raise ValueError(f"Invalid payer_type: {payer_type_str}")

        # Validate total
        item_total = sum(float(it["amount"]) for it in items_data)
        receipt_amount = float(data["amount"])
        if abs(item_total - receipt_amount) > 0.01:
            raise ValueError(
                f"Item amounts ({item_total}) don't match receipt amount ({receipt_amount})"
            )

        bulk_receipt = BulkReceipt(
            institution_id=data["institution_id"],
            payer_type=payer_type,
            amount=Decimal(str(receipt_amount)),
            payment_date=data.get("payment_date") or datetime.utcnow(),
            reference_number=data["reference_number"],
            description=data.get("description"),
            status="processed",
        )
        db.add(bulk_receipt)
        await db.flush()

        applied_count = 0
        for it in items_data:
            invoice_id = it["invoice_id"]
            student_id = it["student_id"]
            amount = Decimal(str(it["amount"]))

            # Create receipt item
            bri = BulkReceiptItem(
                bulk_receipt_id=bulk_receipt.id,
                invoice_id=invoice_id,
                student_id=student_id,
                amount=amount,
            )
            db.add(bri)

            # Apply payment to invoice
            inv_stmt = select(Invoice).where(Invoice.id == invoice_id)
            inv_res = await db.execute(inv_stmt)
            invoice = inv_res.scalar_one_or_none()
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found")

            payment = Payment(
                invoice_id=invoice.id,
                amount=amount,
                payment_method="BULK_RECEIPT",
                receipt_number=data["reference_number"],
                notes=f"Bulk receipt: {bulk_receipt.id}",
            )
            db.add(payment)

            old_status = invoice.status
            invoice.paid_amount = (invoice.paid_amount or Decimal("0")) + amount
            invoice.balance_due = max(
                Decimal("0"), invoice.amount - invoice.paid_amount
            )
            if invoice.paid_amount >= invoice.amount:
                invoice.status = PaymentStatusEnum.PAID
            elif invoice.paid_amount > 0:
                invoice.status = PaymentStatusEnum.PARTIAL

            db.add(
                InvoiceStatusHistory(
                    invoice_id=invoice.id,
                    from_status=old_status,
                    to_status=invoice.status,
                    remarks=f"Bulk receipt payment: {data['reference_number']}",
                )
            )
            applied_count += 1

        await db.commit()

        logger.info(
            "bulk_receipt_created id={} ref={} amount={} items={}",
            bulk_receipt.id, data["reference_number"], receipt_amount, applied_count,
        )

        return {
            "bulk_receipt_id": bulk_receipt.id,
            "reference_number": data["reference_number"],
            "total_amount": receipt_amount,
            "applied_count": applied_count,
            "message": f"Bulk receipt processed: {applied_count} invoices paid",
        }

    async def generate_bulk_receipt(
        self, db: AsyncSession, payload
    ) -> dict:
        """
        Auto-generate a bulk receipt by finding all unpaid government/scholarship
        invoices for students matching the fee structure, and applying payments.
        """
        data = payload.dict(exclude_unset=True)
        institution_id = data["institution_id"]
        fee_structure_id = data["fee_structure_id"]
        payer_type_str = data.get("payer_type", "GOVERNMENT")

        try:
            payer_type = PayerTypeEnum(payer_type_str)
        except ValueError:
            raise ValueError(f"Invalid payer_type: {payer_type_str}")

        # 1. Invoice any pending demands first for this payer type
        pending_stmt = (
            select(DemandItem)
            .where(
                DemandItem.fee_structure_id == fee_structure_id,
                DemandItem.payer_type == payer_type,
                DemandItem.status == "pending",
                DemandItem.invoice_id.is_(None),
            )
        )
        if data.get("semester"):
            pending_stmt = pending_stmt.where(DemandItem.semester == data["semester"])
        if data.get("year"):
            pending_stmt = pending_stmt.where(DemandItem.year == data["year"])

        pending_res = await db.execute(pending_stmt)
        if pending_res.scalars().first():
            # Generate invoices for these pending demands
            await self.generate_invoices_from_demands(db, payer_type=payer_type_str)

        # 2. Find all demand items with matching payer_type that are invoiced but unpaid
        stmt = (
            select(DemandItem)
            .where(
                DemandItem.fee_structure_id == fee_structure_id,
                DemandItem.payer_type == payer_type,
                DemandItem.status == "invoiced",
                DemandItem.invoice_id.isnot(None),
            )
        )
        if data.get("semester"):
            stmt = stmt.where(DemandItem.semester == data["semester"])
        if data.get("year"):
            stmt = stmt.where(DemandItem.year == data["year"])

        result = await db.execute(stmt)
        demands = list(result.scalars().all())

        if not demands:
            raise ValueError("No unpaid government/scholarship invoices found")

        # Group by invoice and calculate amounts
        invoice_amounts: dict[UUID, dict] = {}
        for d in demands:
            if d.invoice_id not in invoice_amounts:
                invoice_amounts[d.invoice_id] = {
                    "invoice_id": d.invoice_id,
                    "student_id": d.student_id,
                    "amount": 0.0,
                }
            invoice_amounts[d.invoice_id]["amount"] += float(d.amount)

        total_amount = sum(v["amount"] for v in invoice_amounts.values())
        items_data = list(invoice_amounts.values())

        # Check each invoice's remaining balance and cap the amount
        for item in items_data:
            inv_stmt = select(Invoice).where(Invoice.id == item["invoice_id"])
            inv_res = await db.execute(inv_stmt)
            invoice = inv_res.scalar_one_or_none()
            if invoice:
                remaining = float(invoice.balance_due or invoice.amount)
                item["amount"] = min(item["amount"], remaining)

        total_amount = sum(it["amount"] for it in items_data if it["amount"] > 0)
        items_data = [it for it in items_data if it["amount"] > 0]

        if not items_data:
            raise ValueError("All matching invoices are already fully paid")

        # Create the bulk receipt
        from common.schemas.billing.bulk_receipt_schemas import BulkReceiptCreate, BulkReceiptItemCreate

        receipt_payload = BulkReceiptCreate(
            institution_id=institution_id,
            payer_type=payer_type_str,
            amount=round(total_amount, 2),
            payment_date=data.get("payment_date"),
            reference_number=data["reference_number"],
            description=data.get("description"),
            items=[
                BulkReceiptItemCreate(
                    student_id=it["student_id"],
                    invoice_id=it["invoice_id"],
                    amount=round(it["amount"], 2),
                )
                for it in items_data
            ],
        )

        result = await self.create_bulk_receipt(db, receipt_payload)
        result["student_count"] = len(set(it["student_id"] for it in items_data))
        result["invoice_count"] = len(items_data)
        return result

    async def list_bulk_receipts(
        self,
        db: AsyncSession,
        institution_id: UUID,
        payer_type: str | None = None,
    ) -> list:
        stmt = select(BulkReceipt).where(
            BulkReceipt.institution_id == institution_id,
        ).order_by(BulkReceipt.created_at.desc())

        if payer_type:
            stmt = stmt.where(BulkReceipt.payer_type == payer_type)

        result = await db.execute(stmt)
        receipts = list(result.scalars().all())
        return [
            {
                "id": r.id,
                "institution_id": r.institution_id,
                "payer_type": r.payer_type.value,
                "amount": float(r.amount),
                "payment_date": r.payment_date,
                "reference_number": r.reference_number,
                "description": r.description,
                "status": r.status,
                "item_count": len(r.items) if r.items else 0,
                "created_at": r.created_at,
            }
            for r in receipts
        ]

    async def get_bulk_receipt(self, db: AsyncSession, receipt_id: UUID) -> dict:
        stmt = (
            select(BulkReceipt)
            .options(selectinload(BulkReceipt.items))
            .where(BulkReceipt.id == receipt_id)
        )
        result = await db.execute(stmt)
        receipt = result.scalar_one_or_none()
        if not receipt:
            raise ValueError("Bulk receipt not found")

        return {
            "id": receipt.id,
            "institution_id": receipt.institution_id,
            "payer_type": receipt.payer_type.value,
            "amount": float(receipt.amount),
            "payment_date": receipt.payment_date,
            "reference_number": receipt.reference_number,
            "description": receipt.description,
            "status": receipt.status,
            "created_at": receipt.created_at,
            "items": [
                {
                    "id": item.id,
                    "invoice_id": item.invoice_id,
                    "student_id": item.student_id,
                    "amount": float(item.amount),
                    "created_at": item.created_at,
                }
                for item in (receipt.items or [])
            ],
        }

    # ── Demand Listing ─────────────────────────────────

    async def list_demands(
        self,
        db: AsyncSession,
        institution_id: UUID,
        student_id: UUID | None = None,
        batch_id: UUID | None = None,
        semester: int | None = None,
        year: int | None = None,
        payer_type: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        """List demand items with optional filters."""
        from common.models.admission.admission_entry import AdmissionStudent

        stmt = (
            select(DemandItem, AdmissionStudent.name)
            .join(AdmissionStudent, DemandItem.student_id == AdmissionStudent.id)
            .where(DemandItem.deleted_at.is_(None))
        )

        # Filter by institution via student
        stmt = stmt.where(AdmissionStudent.institution_id == institution_id)

        if student_id:
            stmt = stmt.where(DemandItem.student_id == student_id)
        if batch_id:
            stmt = stmt.where(DemandItem.batch_id == batch_id)
        if semester is not None:
            stmt = stmt.where(DemandItem.semester == semester)
        if year is not None:
            stmt = stmt.where(DemandItem.year == year)
        if payer_type:
            stmt = stmt.where(DemandItem.payer_type == payer_type)
        if status:
            stmt = stmt.where(DemandItem.status == status)

        stmt = stmt.order_by(DemandItem.created_at.desc())
        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": d.id,
                "student_id": d.student_id,
                "student_name": name,
                "description": d.description,
                "amount": float(d.amount),
                "semester": d.semester,
                "year": d.year,
                "status": d.status,
                "payer_type": d.payer_type.value if d.payer_type else "STUDENT",
                "invoice_id": d.invoice_id,
                "fee_head_id": d.fee_head_id,
                "fee_sub_head_id": d.fee_sub_head_id,
                "batch_id": d.batch_id,
                "created_at": d.created_at,
            }
            for d, name in rows
        ]


finance_service = FinanceService()
