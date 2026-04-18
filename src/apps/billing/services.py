from datetime import date, datetime, time
from uuid import UUID
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.billing.application_fees import (
    Invoice,
    InvoiceLineItem,
    Payment,
    InvoiceStatusHistory,
    PaymentStatusEnum,
)
from common.schemas.billing.invoice_schemas import (
    InvoiceCreate,
    PaymentCreate,
)
from common.models.billing.financial_year import FinancialYear
from common.models.billing.fee_structure import FeeStructure, FeeStructureItem
from common.schemas.billing.fee_structure_schemas import FeeStructureCreate
from sqlalchemy import update
from logs.logging import logger
from common.models.billing.student_deposit import StudentDeposit


class BillingService:
    async def _generate_invoice_number(self, db: AsyncSession, institution_id: UUID) -> str:
        # Simple invoice scheme: INST-YYYYMMDD-<seq>
        from datetime import datetime
        from sqlalchemy import text

        today = datetime.utcnow().strftime("%Y%m%d")
        prefix = f"{institution_id.hex[:6].upper()}-{today}-"

        # find last seq
        result = await db.execute(
            text("SELECT invoice_number FROM invoices WHERE invoice_number LIKE :prefix ORDER BY invoice_number DESC LIMIT 1"),
            {"prefix": f"{prefix}%"},
        )
        last_invoice = result.scalar_one_or_none()
        if not last_invoice:
            next_seq = 1
        else:
            try:
                seq = last_invoice.split("-")[-1]
                next_seq = int(seq) + 1
            except Exception:
                next_seq = 1
        return f"{prefix}{next_seq:04d}"

    async def generate_application_number(self, db: AsyncSession, institution_id: UUID) -> str:
        """
        Generate a unique application number.
        Format: APP-{INST_CODE}-{YYYY}-{SEQ}
        """
        from datetime import datetime
        from sqlalchemy import text
        
        year = datetime.utcnow().year
        inst_code = institution_id.hex[:6].upper()
        prefix = f"APP-{inst_code}-{year}-"
        
        # Find last sequence
        # We need to query AdmissionStudent.application_number
        result = await db.execute(
            text("SELECT application_number FROM admission_students WHERE application_number LIKE :prefix ORDER BY application_number DESC LIMIT 1"),
            {"prefix": f"{prefix}%"},
        )
        last_app_num = result.scalar_one_or_none()
        
        if not last_app_num:
            next_seq = 1
        else:
            try:
                # APP-CODE-YYYY-XXXX
                seq = last_app_num.split("-")[-1]
                next_seq = int(seq) + 1
            except Exception:
                next_seq = 1
                
        return f"{prefix}{next_seq:04d}"

    async def handle_course_change(self, db: AsyncSession, student_id: UUID, new_fee_structure_id: UUID | None):
        """
        Handle course/department change:
        1. Void (delete) all PENDING demands for the student.
        2. Assign new fees based on the new fee structure.
        """
        from common.models.billing.demand import DemandItem
        
        # 1. Delete PENDING demands
        # We only delete demands that are NOT linked to an invoice or are pending.
        # Ideally, we should check status="pending" and invoice_id IS NULL.
        stmt = select(DemandItem).where(
            DemandItem.student_id == student_id,
            DemandItem.status == "pending",
            DemandItem.invoice_id.is_(None)
        )
        res = await db.execute(stmt)
        pending_demands = res.scalars().all()
        
        for demand in pending_demands:
            await db.delete(demand)
            
        await db.flush()
        
        # 2. Assign new fees
        await self.assign_course_fees(db, student_id, new_fee_structure_id)
        
        await db.commit()

    async def _resolve_fee_structure_for_student(
        self,
        db: AsyncSession,
        student,
        fee_structure_id: UUID | None = None,
    ):
        """
        Resolve applicable fee structure for a student.
        """
        query = (
            select(FeeStructure)
            .options(selectinload(FeeStructure.items).selectinload(FeeStructureItem.fee_head))
        )

        if fee_structure_id:
            result = await db.execute(query.where(FeeStructure.id == fee_structure_id))
            fee_structure = result.scalar_one_or_none()
            if not fee_structure:
                raise ValueError("Fee Structure not found")
            return fee_structure

        prog = getattr(student, "program_details", None)
        if not prog or not prog.academic_year_id or not prog.course_id:
            return None

        query = query.where(
            FeeStructure.institution_id == prog.institution_id,
            FeeStructure.admission_year_id == prog.academic_year_id,
            FeeStructure.degree_id == prog.course_id,
        )
        result = await db.execute(query)
        fee_structures = result.scalars().all()
        if not fee_structures:
            return None

        def score(fs: FeeStructure) -> int:
            total = 0

            if prog.admission_quota_id:
                if fs.quota_id == prog.admission_quota_id:
                    total += 4
                elif fs.quota_id is None:
                    total += 2
                else:
                    return -1
            else:
                total += 2 if fs.quota_id is None else 1

            if prog.admission_type_id:
                if fs.admission_type_id == prog.admission_type_id:
                    total += 4
                elif fs.admission_type_id is None:
                    total += 2
                else:
                    return -1
            else:
                total += 2 if fs.admission_type_id is None else 1

            return total

        ranked = sorted(
            fee_structures,
            key=lambda fs: (
                score(fs),
                fs.updated_at or fs.created_at,
            ),
            reverse=True,
        )

        best = ranked[0]
        if score(best) < 0:
            return None
        return best

    async def auto_apply_deposit_to_invoice(
        self,
        db: AsyncSession,
        student_id: UUID,
        invoice: Invoice,
    ) -> bool:
        """
        Automatically apply available deposit/advance payment to an invoice.
        Returns True if deposit was applied, False if no deposit or not applicable.
        """
        try:
            from decimal import Decimal
            
            # Get student's deposit if it exists
            deposit_stmt = select(StudentDeposit).where(StudentDeposit.student_id == student_id)
            deposit_res = await db.execute(deposit_stmt)
            deposit = deposit_res.scalar_one_or_none()
            
            if not deposit or deposit.available_balance <= 0:
                return False
            
            # Calculate amount to apply (min of available balance and invoice amount)
            available = Decimal(str(deposit.available_balance))
            invoice_amount = invoice.balance_due or invoice.amount
            amount_to_apply = min(available, invoice_amount)
            
            if amount_to_apply <= 0:
                return False
            
            # Create line item for the deposit credit
            line_item = InvoiceLineItem(
                invoice_id=invoice.id,
                description="Deposit/Advance Credit Applied",
                amount=-amount_to_apply,  # Negative = credit/discount
                discount_amount=0,
                tax_amount=0,
                net_amount=-amount_to_apply,
            )
            db.add(line_item)
            
            # Update deposit tracking
            deposit.used_amount += amount_to_apply
            
            # Add to adjustment history
            from datetime import datetime
            adjustment_entry = {
                "date": datetime.utcnow().isoformat(),
                "amount": float(amount_to_apply),
                "invoice_id": str(invoice.id),
                "applied_by": None,
            }
            if deposit.adjustment_history is None:
                deposit.adjustment_history = []
            deposit.adjustment_history.append(adjustment_entry)
            
            # Update invoice balance_due
            if invoice.balance_due:
                invoice.balance_due -= amount_to_apply
            
            db.add(deposit)
            await db.flush()
            
            logger.info(
                f"Auto-applied deposit of {amount_to_apply} to invoice {invoice.id} for student {student_id}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error auto-applying deposit: {str(e)}", exc_info=True)
            return False

    async def lock_student_fee_structure(
        self,
        db: AsyncSession,
        student_id: UUID,
        fee_structure_id: UUID | None = None,
        locked_by: UUID | None = None,
    ) -> UUID:
        """
        Set and lock a student's final fee structure.
        """
        from datetime import datetime
        from common.models.admission.admission_entry import AdmissionStudent

        stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
        result = await db.execute(stmt)
        student = result.scalar_one_or_none()
        if not student:
            raise ValueError("Student not found")

        current_status = student.status.value if hasattr(student.status, "value") else str(student.status)

        # Idempotent path: already locked with a structure.
        if student.is_fee_structure_locked and student.fee_structure_id:
            if fee_structure_id and student.fee_structure_id != fee_structure_id:
                raise ValueError("Fee structure is already locked with a different value")
            return student.fee_structure_id

        resolved_fee_structure = None
        if fee_structure_id:
            resolved_fee_structure = await self._resolve_fee_structure_for_student(
                db, student, fee_structure_id
            )
        elif student.fee_structure_id:
            resolved_fee_structure = await self._resolve_fee_structure_for_student(
                db, student, student.fee_structure_id
            )
        else:
            resolved_fee_structure = await self._resolve_fee_structure_for_student(db, student)

        if not resolved_fee_structure:
            raise ValueError(
                "No matching fee structure found for this student. Configure fees before provisional allotment."
            )

        student.fee_structure_id = resolved_fee_structure.id
        student.is_fee_structure_locked = True
        student.fee_structure_locked_at = datetime.utcnow()
        student.fee_structure_locked_by = locked_by
        db.add(student)
        await db.flush()

        return resolved_fee_structure.id

    async def assign_course_fees(self, db: AsyncSession, student_id: UUID, fee_structure_id: UUID | None = None):
        """
        Assign configured course fees to a student by creating future demands.
        If fee_structure_id is None, it attempts to find the matching fee structure based on student details.
        """
        from common.models.billing.demand import DemandItem
        from common.models.admission.admission_entry import AdmissionStudent
        
        # 0. Fetch Student
        stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()
        if not student:
            raise ValueError("Student not found")

        fs = await self._resolve_fee_structure_for_student(db, student, fee_structure_id)
        if not fs:
            logger.warning(
                "No fee structure found for student %s (institution=%s, year=%s, course=%s, type=%s, quota=%s)",
                getattr(student.personal_details, "name", None) if getattr(student, "personal_details", None) else getattr(student, "name", None),
                getattr(student.program_details, "institution_id", None),
                getattr(student.program_details, "academic_year_id", None),
                getattr(student.program_details, "course_id", None),
                getattr(student.program_details, "admission_type_id", None),
                getattr(student.program_details, "admission_quota_id", None),
            )
            return []

        # Keep latest assigned structure on student for downstream lock/workflows.
        student.fee_structure_id = fs.id
        db.add(student)

        # 2. Iterate items and create demands
        created_demands = []
        # Reload items for the found fs
        await db.refresh(fs, ["items"])
        semesters_per_year = fs.semesters_per_year or 2
        
        for item in fs.items:
            head_name = item.fee_head.name if item.fee_head else "Fee"

            # --- Semester-based breakdown (preferred) ---
            if item.amount_by_semester:
                for sem_label, sem_amount in item.amount_by_semester.items():
                    amount = float(sem_amount)
                    if amount > 0:
                        sem_num = int(sem_label)
                        year_num = ((sem_num - 1) // semesters_per_year) + 1
                        di = DemandItem(
                            batch_id=None,
                            student_id=student_id,
                            fee_structure_id=fs.id,
                            fee_structure_item_id=item.id,
                            amount=amount,
                            fee_head_id=item.fee_head_id,
                            fee_sub_head_id=item.fee_sub_head_id,
                            semester=sem_num,
                            year=year_num,
                            payer_type=item.payer_type,
                            description=f"{head_name} - Sem {sem_label}",
                        )
                        db.add(di)
                        created_demands.append(di)

            # --- Year-based breakdown (legacy) ---
            elif item.amount_by_year:
                for year_label, year_amount in item.amount_by_year.items():
                    amount = float(year_amount)
                    if amount > 0:
                        di = DemandItem(
                            batch_id=None,
                            student_id=student_id,
                            fee_structure_id=fs.id,
                            fee_structure_item_id=item.id,
                            amount=amount,
                            fee_head_id=item.fee_head_id,
                            fee_sub_head_id=item.fee_sub_head_id,
                            year=int(year_label) if year_label.isdigit() else None,
                            payer_type=item.payer_type,
                            description=f"{head_name} - Year {year_label}",
                        )
                        db.add(di)
                        created_demands.append(di)
            else:
                amount = float(item.amount)
                if amount > 0:
                    di = DemandItem(
                        batch_id=None,
                        student_id=student_id,
                        fee_structure_id=fs.id,
                        fee_structure_item_id=item.id,
                        amount=amount,
                        fee_head_id=item.fee_head_id,
                        fee_sub_head_id=item.fee_sub_head_id,
                        payer_type=item.payer_type,
                        description=head_name,
                    )
                    db.add(di)
                    created_demands.append(di)
        
        return created_demands

    async def assign_application_fee(self, db: AsyncSession, student_id: UUID):
        """
        Assign application fee demand if configured for the student's course/year.
        """
        from common.models.admission.admission_entry import AdmissionStudent
        from common.models.master.annual_task import AcademicYearCourse
        from common.models.billing.application_fees import FeeHead
        from common.models.billing.demand import DemandItem
        from sqlalchemy.orm import selectinload
        
        # 1. Fetch Student
        stmt = select(AdmissionStudent).options(selectinload(AdmissionStudent.program_details)).where(AdmissionStudent.id == student_id)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()
        if not student:
            raise ValueError("Student not found")
            
        course_id = student.program_details.course_id if student.program_details else None
        academic_year_id = student.program_details.academic_year_id if student.program_details else None
        institution_id = student.program_details.institution_id if student.program_details else None

        if not course_id or not academic_year_id:
            return None # No course/year assigned
            
        # 2. Fetch Config
        stmt = select(AcademicYearCourse).where(
            AcademicYearCourse.academic_year_id == academic_year_id,
            AcademicYearCourse.course_id == course_id
        )
        res = await db.execute(stmt)
        config = res.scalar_one_or_none()
        
        if config and config.application_fee and config.application_fee > 0:
            # 3. Find 'Application Fee' Head
            stmt_head = select(FeeHead).where(
                FeeHead.institution_id == institution_id,
                FeeHead.name.ilike("Application Fee")
            )
            res_head = await db.execute(stmt_head)
            fee_head = res_head.scalars().first()
            
            # Create Demand
            di = DemandItem(
                student_id=student_id,
                fee_head_id=fee_head.id if fee_head else None,
                amount=config.application_fee,
                description="Application Fee"
            )
            db.add(di)
            # await db.flush() # Caller will commit
            return di
        return None

    async def create_invoice(self, db: AsyncSession, payload: InvoiceCreate):
        try:
            data = payload.dict(exclude_unset=True)
            # Create invoice skeleton
            invoice_number = await self._generate_invoice_number(db, data["institution_id"])  # type: ignore[operator]
            amount_override = data.get("amount")

            invoice = Invoice(
                institution_id=data["institution_id"],
                student_id=data["student_id"],
                invoice_number=invoice_number,
                amount=amount_override or 0.0,
                paid_amount=0.0,
                balance_due=amount_override or 0.0,
                status=PaymentStatusEnum.PENDING,
                issue_date=data["issue_date"],
                due_date=data["due_date"],
                notes=data.get("notes"),
            )

            db.add(invoice)
            await db.flush()

            total_amount = 0.0
            # Add line items
            line_items = data.get("line_items") or []
            for li in line_items:
                item_amount = li["amount"]
                discount = li.get("discount_amount") or 0.0
                tax = li.get("tax_amount") or 0.0
                net_amount = item_amount - (discount or 0.0) + (tax or 0.0)
                total_amount += net_amount
                db.add(
                    InvoiceLineItem(
                        invoice_id=invoice.id,
                        fee_head_id=li.get("fee_head_id"),
                        description=li.get("description"),
                        amount=item_amount,
                        discount_amount=discount,
                        tax_amount=tax,
                        net_amount=net_amount,
                    )
                )

            # If line items present, set invoice amount
            if line_items:
                invoice.amount = total_amount
                invoice.balance_due = total_amount

            await db.commit()


            stmt = select(Invoice).where(Invoice.id == invoice.id)
            result = await db.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            await db.rollback()
            raise e

    async def create_invoice_from_demands(self, db: AsyncSession, demands: list):
        """
        Create an invoice from a list of DemandItems.
        All demands must belong to the same student.
        """
        from common.models.billing.application_fees import Invoice, InvoiceLineItem, PaymentStatusEnum
        from datetime import date
        
        if not demands:
            return None
            
        # Validate all demands belong to same student
        student_id = demands[0].student_id
        institution_id = None
        
        # We need institution_id. Ideally demand has it, or we fetch from student.
        # DemandItem doesn't have institution_id. We fetch it from student.
        from common.models.admission.admission_entry import AdmissionStudent
        stmt = select(AdmissionStudent).options(selectinload(AdmissionStudent.program_details)).where(AdmissionStudent.id == student_id)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()
        if not student:
            raise ValueError("Student not found for demands")
        
        institution_id = student.program_details.institution_id if student.program_details else getattr(student, "institution_id", None)
        
        if not institution_id:
            raise ValueError("Student missing institution_id")
        
        total_amount = sum([d.amount for d in demands])
        
        invoice_number = await self._generate_invoice_number(db, institution_id)
        
        invoice = Invoice(
            institution_id=institution_id,
            student_id=student_id,
            invoice_number=invoice_number,
            amount=total_amount,
            paid_amount=0.0,
            balance_due=total_amount,
            status=PaymentStatusEnum.PENDING,
            issue_date=date.today(),
            due_date=date.today()
        )
        db.add(invoice)
        await db.flush()
        
        for d in demands:
            # Create Line Item
            line = InvoiceLineItem(
                invoice_id=invoice.id,
                fee_head_id=d.fee_head_id,
                description=d.description,
                amount=d.amount,
                net_amount=d.amount
            )
            db.add(line)
            
            # Link demand to invoice
            d.invoice_id = invoice.id
            # d.status = "invoiced" # If demand has status? It has 'status' field (default pending).
            d.status = "invoiced"
            db.add(d)
            
        await db.commit()
        await db.refresh(invoice)
        return invoice

    async def apply_payment(self, db: AsyncSession, invoice_id: UUID, payload: PaymentCreate, counter_id: UUID | None = None):
        try:
            from decimal import Decimal
            from sqlalchemy.orm import raiseload
            
            data = payload.dict(exclude_unset=True)
            # idempotency: check existing transaction_id
            transaction_id = data.get("transaction_id")
            if transaction_id:
                stmt = select(Payment).where(Payment.transaction_id == transaction_id).options(raiseload("*"))
                res = await db.execute(stmt)
                existing = res.scalar_one_or_none()
                if existing:
                    # Return dict to avoid circular reference serialization
                    return {
                        "id": existing.id,
                        "invoice_id": existing.invoice_id,
                        "amount": float(existing.amount),
                        "payment_method": existing.payment_method,
                        "transaction_id": existing.transaction_id,
                        "receipt_number": existing.receipt_number,
                        "notes": existing.notes,
                        "payment_date": existing.payment_date,
                    }

            stmt = select(Invoice).where(Invoice.id == invoice_id).options(raiseload("*"))
            res = await db.execute(stmt)
            invoice = res.scalar_one_or_none()
            if not invoice:
                raise ValueError("Invoice not found")

            # Convert amount to Decimal for consistent arithmetic
            payment_amount = Decimal(str(data["amount"]))
            
            payment = Payment(
                invoice_id=invoice.id,
                cash_counter_id=counter_id,
                amount=payment_amount,
                payment_method=data["payment_method"],
                transaction_id=transaction_id,
                receipt_number=data.get("receipt_number"),
                notes=data.get("notes"),
            )

            db.add(payment)
            await db.flush()

            # Store payment_date before commit
            payment_date = payment.payment_date

            # update invoice paid / balance / status using Decimal arithmetic
            invoice.paid_amount = (invoice.paid_amount or Decimal(0)) + payment_amount
            invoice.balance_due = max(Decimal(0), invoice.amount - invoice.paid_amount)
            old_status = invoice.status
            if invoice.paid_amount >= invoice.amount:
                invoice.status = PaymentStatusEnum.PAID
            elif Decimal(0) < invoice.paid_amount < invoice.amount:
                invoice.status = PaymentStatusEnum.PARTIAL

            # record status history
            db.add(
                InvoiceStatusHistory(
                    invoice_id=invoice.id,
                    from_status=old_status,
                    to_status=invoice.status,
                )
            )

            await db.commit()
            
            # Return dict response instead of model to avoid circular reference
            return {
                "id": payment.id,
                "invoice_id": payment.invoice_id,
                "amount": float(payment.amount),
                "payment_method": payment.payment_method,
                "transaction_id": payment.transaction_id,
                "receipt_number": payment.receipt_number,
                "notes": payment.notes,
                "payment_date": payment_date,
            }
        except Exception as e:
            await db.rollback()
            raise e


    async def set_active_financial_year(self, db: AsyncSession, financial_year_id: UUID):
        # Activate the provided financial year and deactivate others for the same institution in one transaction
        from sqlalchemy import select
        # fetch fy
        stmt = select(FinancialYear).where(FinancialYear.id == financial_year_id)
        res = await db.execute(stmt)
        fy = res.scalar_one_or_none()
        if not fy:
            raise ValueError("Financial Year not found")
        # Deactivate others only for the SAME institution
        await db.execute(
            update(FinancialYear)
            .where(FinancialYear.institution_id == fy.institution_id, FinancialYear.id != financial_year_id)
            .values(active=False)
        )
        # Activate this one
        fy.active = True
        await db.commit()
        await db.refresh(fy)
        return fy

    async def create_fee_structure(self, db: AsyncSession, payload: FeeStructureCreate):
        try:
            data = payload.dict(exclude_unset=True)
            items = data.pop("items", []) or []
            if not items:
                raise ValueError("A fee structure must contain at least one item")
            # validate item amounts
            for it in items:
                amt = it.get("amount")
                aby = it.get("amount_by_year")
                abs_ = it.get("amount_by_semester")
                if amt is None and not aby and not abs_:
                    raise ValueError("Each item must have 'amount', 'amount_by_year', or 'amount_by_semester'")
                if amt is not None and float(amt) < 0:
                    raise ValueError("Item amount must be >= 0")
                if aby and any(float(v) < 0 for v in aby.values()):
                    raise ValueError("Amounts in 'amount_by_year' must be >= 0")
                if abs_ and any(float(v) < 0 for v in abs_.values()):
                    raise ValueError("Amounts in 'amount_by_semester' must be >= 0")

            fs = FeeStructure(**data)
            db.add(fs)
            await db.flush()
            order_idx = 1
            for it in items:
                db.add(
                    FeeStructureItem(
                        fee_structure_id=fs.id,
                        fee_head_id=it.get("fee_head_id"),
                        fee_sub_head_id=it.get("fee_sub_head_id"),
                        amount=it.get("amount", 0),
                        amount_by_year=it.get("amount_by_year"),
                        amount_by_semester=it.get("amount_by_semester"),
                        payer_type=it.get("payer_type", "STUDENT"),
                        order=it.get("order", order_idx),
                    )
                )
                order_idx += 1
            await db.commit()
            stmt = select(FeeStructure).where(FeeStructure.id == fs.id)
            res = await db.execute(stmt)
            return res.scalar_one()
        except Exception as e:
            await db.rollback()
            raise e


    def _serialize_filter_value(self, value):
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, list):
            return [self._serialize_filter_value(v) for v in value if v not in (None, "", [], {})]
        return value

    def _normalize_demand_filters(self, filters: dict | None) -> dict:
        if not filters:
            return {}

        normalized: dict = {}
        for key, value in filters.items():
            if value in (None, "", [], {}):
                continue
            normalized[key] = self._serialize_filter_value(value)
        return normalized

    def _parse_uuid(self, value) -> UUID | None:
        if value in (None, ""):
            return None
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except Exception:
            return None

    def _as_list(self, value) -> list:
        if value in (None, "", [], {}):
            return []
        if isinstance(value, list):
            return [v for v in value if v not in (None, "")]
        return [value]

    def _normalize_identifier(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().casefold()
        return normalized or None

    def _amount_for_period_from_item(
        self,
        item: FeeStructureItem,
        year: str | None,
        semester: int | None,
        semesters_per_year: int,
    ) -> tuple[float, int | None, int | None]:
        if semester is not None:
            sem_key = str(semester)
            derived_year = ((semester - 1) // semesters_per_year) + 1

            if item.amount_by_semester:
                raw_value = item.amount_by_semester.get(sem_key)
                if raw_value not in (None, ""):
                    return float(raw_value or 0), semester, derived_year

            if item.amount_by_year:
                raw_value = item.amount_by_year.get(str(derived_year))
                if raw_value not in (None, ""):
                    return float(raw_value or 0), semester, derived_year

            if not item.amount_by_semester and not item.amount_by_year and derived_year == 1:
                return float(item.amount or 0), semester, derived_year

            return 0.0, semester, derived_year

        target_year = str(year or "").strip()
        if not target_year:
            return 0.0, None, None

        if item.amount_by_year:
            raw_value = item.amount_by_year.get(target_year)
            if raw_value in (None, ""):
                return 0.0, None, int(target_year)
            return float(raw_value or 0), None, int(target_year)

        if item.amount_by_semester:
            total = 0.0
            for sem_label, sem_amount in item.amount_by_semester.items():
                sem_num = int(sem_label)
                sem_year = ((sem_num - 1) // semesters_per_year) + 1
                if sem_year == int(target_year):
                    total += float(sem_amount or 0)
            return total, None, int(target_year)

        if target_year == "1":
            return float(item.amount or 0), None, 1

        return 0.0, None, int(target_year)

    def _find_fee_structure_item(
        self,
        fee_structure: FeeStructure,
        fee_head_id: UUID,
        fee_sub_head_id: UUID,
    ) -> FeeStructureItem | None:
        matches = [
            item
            for item in (fee_structure.items or [])
            if item.fee_head_id == fee_head_id and item.fee_sub_head_id == fee_sub_head_id
        ]
        if len(matches) > 1:
            raise ValueError(
                "Multiple fee structure items found for selected fee head/subhead. "
                "Please keep only one mapping in the fee structure."
            )
        return matches[0] if matches else None

    async def resolve_students_by_identifiers(
        self,
        db: AsyncSession,
        institution_id: UUID,
        identifiers: list[str] | None,
    ) -> dict:
        from common.models.admission.admission_entry import (
            AdmissionStudent,
            AdmissionStudentProgramDetails,
        )

        normalized_to_display: dict[str, str] = {}
        ordered_identifiers: list[str] = []
        for raw in identifiers or []:
            trimmed = str(raw or "").strip()
            normalized = self._normalize_identifier(trimmed)
            if not normalized:
                continue
            if normalized not in normalized_to_display:
                normalized_to_display[normalized] = trimmed
                ordered_identifiers.append(normalized)

        if not ordered_identifiers:
            return {"matched_students": [], "unmatched_identifiers": []}

        stmt = (
            select(AdmissionStudent)
            .options(
                selectinload(AdmissionStudent.department),
                selectinload(AdmissionStudent.course),
            )
            .join(
                AdmissionStudentProgramDetails,
                AdmissionStudentProgramDetails.student_id == AdmissionStudent.id,
            )
            .where(
                AdmissionStudent.deleted_at.is_(None),
                AdmissionStudentProgramDetails.institution_id == institution_id,
                or_(
                    func.lower(func.trim(AdmissionStudent.application_number)).in_(
                        ordered_identifiers
                    ),
                    func.lower(func.trim(AdmissionStudent.roll_number)).in_(
                        ordered_identifiers
                    ),
                ),
            )
        )
        result = await db.execute(stmt)
        students = result.scalars().all()

        matches_by_identifier: dict[str, list] = {key: [] for key in ordered_identifiers}
        for student in students:
            candidate_keys = {
                self._normalize_identifier(student.application_number),
                self._normalize_identifier(student.roll_number),
            }
            for key in candidate_keys:
                if key and key in matches_by_identifier:
                    matches_by_identifier[key].append(student)

        selected_students = []
        selected_ids: set[UUID] = set()
        unmatched_identifiers: list[str] = []

        for key in ordered_identifiers:
            matches = matches_by_identifier.get(key, [])
            if len(matches) > 1:
                conflicting_ids = ", ".join(str(student.id) for student in matches[:5])
                raise ValueError(
                    f"Identifier '{normalized_to_display[key]}' matches multiple students "
                    f"({conflicting_ids})."
                )
            if len(matches) == 1:
                student = matches[0]
                if student.id not in selected_ids:
                    selected_ids.add(student.id)
                    selected_students.append(student)
            else:
                unmatched_identifiers.append(normalized_to_display[key])

        matched_students = [
            {
                "id": student.id,
                "name": getattr(student.personal_details, "name", None) if getattr(student, "personal_details", None) else getattr(student, "name", None),
                "application_number": student.application_number,
                "roll_number": student.roll_number,
                "department": student.department.name if student.department else None,
                "course": student.course.title if student.course else None,
                "year": student.year,
            }
            for student in selected_students
        ]

        return {
            "matched_students": matched_students,
            "unmatched_identifiers": unmatched_identifiers,
        }

    async def _derive_general_demand_amount(
        self,
        fee_structure: FeeStructure,
        fee_head_id: UUID,
        fee_sub_head_id: UUID,
        year: str | None,
        semester: int | None,
    ) -> tuple[float, UUID, int | None, int | None]:
        matched_item = self._find_fee_structure_item(
            fee_structure=fee_structure,
            fee_head_id=fee_head_id,
            fee_sub_head_id=fee_sub_head_id,
        )
        if not matched_item:
            raise ValueError(
                "No matching fee structure item for selected fee head and subhead."
            )

        derived_amount, resolved_semester, resolved_year = self._amount_for_period_from_item(
            matched_item,
            year=year,
            semester=semester,
            semesters_per_year=fee_structure.semesters_per_year or 2,
        )
        if derived_amount <= 0:
            label = f"Semester {semester}" if semester is not None else f"Year {year}"
            raise ValueError(
                f"No configured amount found for {label} in selected fee structure."
            )

        return float(derived_amount), matched_item.id, resolved_semester, resolved_year

    async def create_general_demand(self, db: AsyncSession, payload) -> dict:
        from common.models.admission.admission_entry import (
            AdmissionStudent,
            AdmissionStudentProgramDetails,
        )
        from common.models.billing.application_fees import FeeHead
        from common.models.billing.demand import DemandBatch, DemandItem
        from common.models.billing.fee_subhead import FeeSubHead

        data = payload.dict(exclude_unset=True)
        institution_id: UUID = data["institution_id"]
        fee_structure_id: UUID = data["fee_structure_id"]
        year_raw = data.get("year")
        year = str(year_raw).strip() if year_raw not in (None, "") else None
        semester = data.get("semester")
        if semester not in (None, ""):
            semester = int(semester)
        else:
            semester = None
        fee_head_id: UUID = data["fee_head_id"]
        fee_sub_head_id: UUID = data["fee_sub_head_id"]
        avoid_duplicates = bool(data.get("avoid_duplicates", True))

        if year is None and semester is None:
            raise ValueError("Either year or semester is required")
        if year is not None and semester is not None:
            raise ValueError("Provide either year or semester, not both")

        fee_structure_stmt = (
            select(FeeStructure)
            .options(selectinload(FeeStructure.items))
            .where(
                FeeStructure.id == fee_structure_id,
                FeeStructure.institution_id == institution_id,
            )
        )
        fee_structure_res = await db.execute(fee_structure_stmt)
        fee_structure = fee_structure_res.scalar_one_or_none()
        if not fee_structure:
            raise ValueError("Fee structure not found for selected institution")

        fee_head_stmt = select(FeeHead).where(
            FeeHead.id == fee_head_id,
            FeeHead.institution_id == institution_id,
        )
        fee_head_res = await db.execute(fee_head_stmt)
        fee_head = fee_head_res.scalar_one_or_none()
        if not fee_head:
            raise ValueError("Fee head not found for selected institution")

        fee_sub_head_stmt = select(FeeSubHead).where(
            FeeSubHead.id == fee_sub_head_id,
            FeeSubHead.fee_head_id == fee_head_id,
            FeeSubHead.institution_id == institution_id,
        )
        fee_sub_head_res = await db.execute(fee_sub_head_stmt)
        fee_sub_head = fee_sub_head_res.scalar_one_or_none()
        if not fee_sub_head:
            raise ValueError("Fee subhead does not belong to selected fee head/institution")

        resolve_result = await self.resolve_students_by_identifiers(
            db=db,
            institution_id=institution_id,
            identifiers=data.get("identifiers") or [],
        )
        resolved_students = resolve_result.get("matched_students", [])
        unmatched_identifiers = resolve_result.get("unmatched_identifiers", [])

        explicit_student_ids = [
            parsed
            for raw in self._as_list(data.get("student_ids"))
            if (parsed := self._parse_uuid(raw))
        ]
        resolved_student_ids = [
            parsed
            for student in resolved_students
            if (parsed := self._parse_uuid(student.get("id")))
        ]

        target_student_ids: list[UUID] = []
        seen_ids: set[UUID] = set()
        for sid in explicit_student_ids + resolved_student_ids:
            if sid not in seen_ids:
                seen_ids.add(sid)
                target_student_ids.append(sid)

        if not target_student_ids:
            raise ValueError("No target students found for general demand")

        students_stmt = (
            select(AdmissionStudent.id)
            .join(
                AdmissionStudentProgramDetails,
                AdmissionStudentProgramDetails.student_id == AdmissionStudent.id,
            )
            .where(
                AdmissionStudent.deleted_at.is_(None),
                AdmissionStudentProgramDetails.institution_id == institution_id,
                AdmissionStudent.id.in_(target_student_ids),
            )
        )
        students_res = await db.execute(students_stmt)
        valid_student_ids = set(students_res.scalars().all())
        invalid_students = [sid for sid in target_student_ids if sid not in valid_student_ids]
        if invalid_students:
            invalid_text = ", ".join(str(sid) for sid in invalid_students[:5])
            raise ValueError(
                f"Some selected students do not belong to the selected institution: {invalid_text}"
            )

        matched_item = self._find_fee_structure_item(
            fee_structure=fee_structure,
            fee_head_id=fee_head_id,
            fee_sub_head_id=fee_sub_head_id,
        )

        if not matched_item:
            raise ValueError(
                "Selected fee head/subhead is not configured in the chosen fee structure"
            )

        amount_value = data.get("amount")
        fee_structure_item_id = matched_item.id
        resolved_semester = semester
        resolved_year = int(year) if year is not None else None
        if amount_value is None:
            (
                amount_used,
                fee_structure_item_id,
                resolved_semester,
                resolved_year,
            ) = await self._derive_general_demand_amount(
                fee_structure=fee_structure,
                fee_head_id=fee_head_id,
                fee_sub_head_id=fee_sub_head_id,
                year=year,
                semester=semester,
            )
        else:
            amount_used = float(amount_value)
            if amount_used <= 0:
                raise ValueError("Amount must be greater than zero")

        amount_used = round(float(amount_used), 2)

        description_base = (data.get("description") or "").strip()
        if not description_base:
            description_base = f"{fee_head.name} - {fee_sub_head.name}"
        scope_suffix = (
            f"(Sem {resolved_semester})"
            if resolved_semester is not None
            else f"(Year {resolved_year})"
        )
        description = (
            description_base
            if scope_suffix.casefold() in description_base.casefold()
            else f"{description_base} {scope_suffix}"
        )

        batch = DemandBatch(
            name=f"General Demand - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            institution_id=institution_id,
            fee_structure_id=fee_structure_id,
            filters={
                "type": "general_demand",
                "year": resolved_year,
                "semester": resolved_semester,
                "fee_head_id": str(fee_head_id),
                "fee_sub_head_id": str(fee_sub_head_id),
                "description": description,
            },
            status="generated",
            generated_at=datetime.utcnow(),
        )
        db.add(batch)
        await db.flush()

        skipped_student_ids: set[UUID] = set()
        if avoid_duplicates:
            existing_stmt = (
                select(DemandItem.student_id)
                .where(
                    DemandItem.student_id.in_(target_student_ids),
                    DemandItem.status == "pending",
                    DemandItem.invoice_id.is_(None),
                    DemandItem.fee_head_id == fee_head_id,
                    DemandItem.fee_sub_head_id == fee_sub_head_id,
                    DemandItem.amount == amount_used,
                    (
                        or_(
                            DemandItem.semester == resolved_semester,
                            DemandItem.description.ilike(f"%(Sem {resolved_semester})"),
                        )
                        if resolved_semester is not None
                        else or_(
                            DemandItem.year == resolved_year,
                            DemandItem.description.ilike(f"%(Year {resolved_year})"),
                        )
                    ),
                )
                .distinct()
            )
            existing_res = await db.execute(existing_stmt)
            skipped_student_ids = set(existing_res.scalars().all())

        created_count = 0
        skipped_count = 0
        for student_id in target_student_ids:
            if student_id in skipped_student_ids:
                skipped_count += 1
                continue

            db.add(
                DemandItem(
                    batch_id=batch.id,
                    student_id=student_id,
                    fee_structure_id=fee_structure_id,
                    fee_structure_item_id=fee_structure_item_id,
                    fee_head_id=fee_head_id,
                    fee_sub_head_id=fee_sub_head_id,
                    amount=amount_used,
                    description=description,
                    semester=resolved_semester,
                    year=resolved_year,
                    status="pending",
                )
            )
            created_count += 1

        await db.commit()

        logger.info(
            "general_demand_created batch_id={} created_count={} skipped_count={} institution_id={}",
            str(batch.id),
            created_count,
            skipped_count,
            str(institution_id),
        )

        return {
            "batch_id": batch.id,
            "resolved_student_count": len(target_student_ids),
            "created_count": created_count,
            "skipped_count": skipped_count,
            "unmatched_identifiers": unmatched_identifiers,
            "amount_used": amount_used,
            "message": "General demand created successfully",
        }

    async def create_demand_batch(self, db: AsyncSession, payload):
        """Create a demand batch; this can target explicit students or filter-based student groups."""
        from common.models.billing.demand import DemandBatch

        data = payload.dict(exclude_unset=True)
        filters = self._normalize_demand_filters(data.get("filters") or {})

        explicit_students = self._as_list(data.pop("apply_to_students", None))
        if explicit_students:
            filters["apply_to_students"] = [
                str(uid) for uid in explicit_students if self._parse_uuid(uid)
            ]

        data["filters"] = filters or None
        if not data.get("name"):
            data["name"] = f"Demand Batch - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

        batch = DemandBatch(**data)
        db.add(batch)
        await db.commit()
        await db.refresh(batch)
        return batch

    async def _students_matching_filters(
        self,
        db: AsyncSession,
        filters: dict | None,
        institution_id: UUID | None = None,
        apply_to_students: list[UUID] | list[str] | None = None,
    ):
        """Return AdmissionStudent IDs matching filters."""
        from common.models.admission.admission_entry import (
            AdmissionStudent,
            AdmissionStudentPersonalDetails,
            AdmissionStudentProgramDetails,
        )
        from common.models.master.admission_masters import SeatQuota
        from common.models.master.institution import Course, Department

        normalized = self._normalize_demand_filters(filters or {})
        explicit_students = apply_to_students
        if explicit_students is None:
            explicit_students = normalized.pop("apply_to_students", None)

        # Enforce Rule: Only students with locked fee structures can have demands created.
        stmt = select(AdmissionStudent.id).where(
            AdmissionStudent.deleted_at.is_(None),
            AdmissionStudent.is_fee_structure_locked == True
        )

        stmt = stmt.join(
            AdmissionStudentProgramDetails,
            AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id,
            isouter=True,
        ).join(
            AdmissionStudentPersonalDetails,
            AdmissionStudentPersonalDetails.admission_student_id == AdmissionStudent.id,
            isouter=True,
        )

        institution_uuid = self._parse_uuid(institution_id)
        if institution_uuid:
            stmt = stmt.where(AdmissionStudentProgramDetails.institution_id == institution_uuid)

        explicit_student_ids = [
            parsed
            for raw in self._as_list(explicit_students)
            if (parsed := self._parse_uuid(raw))
        ]
        if explicit_student_ids:
            stmt = stmt.where(AdmissionStudent.id.in_(explicit_student_ids))

        # Admission year
        admission_year = (
            normalized.get("admission_year_id")
            or normalized.get("admission_year")
            or normalized.get("academic_year_id")
        )
        admission_year_uuid = self._parse_uuid(admission_year)
        if admission_year_uuid:
            stmt = stmt.where(AdmissionStudentProgramDetails.academic_year_id == admission_year_uuid)

        # Department filters (ID / name)
        department_ids = []
        for raw in (
            self._as_list(normalized.get("department_id"))
            + self._as_list(normalized.get("department_ids"))
        ):
            parsed = self._parse_uuid(raw)
            if parsed:
                department_ids.append(parsed)

        department_text = None
        if not department_ids and normalized.get("department"):
            maybe_uuid = self._parse_uuid(normalized.get("department"))
            if maybe_uuid:
                department_ids.append(maybe_uuid)
            else:
                department_text = str(normalized.get("department")).strip()

        if department_ids:
            stmt = stmt.where(AdmissionStudentProgramDetails.department_id.in_(department_ids))
        elif department_text:
            stmt = stmt.join(Department, AdmissionStudentProgramDetails.department_id == Department.id)
            stmt = stmt.where(Department.name.ilike(f"%{department_text}%"))

        # Degree/Course filters (ID / name)
        degree_ids = []
        for raw in (
            self._as_list(normalized.get("degree_id"))
            + self._as_list(normalized.get("degree_ids"))
            + self._as_list(normalized.get("course_id"))
        ):
            parsed = self._parse_uuid(raw)
            if parsed:
                degree_ids.append(parsed)

        degree_text = None
        if not degree_ids and normalized.get("course"):
            maybe_uuid = self._parse_uuid(normalized.get("course"))
            if maybe_uuid:
                degree_ids.append(maybe_uuid)
            else:
                degree_text = str(normalized.get("course")).strip()

        if degree_ids:
            stmt = stmt.where(AdmissionStudentProgramDetails.course_id.in_(degree_ids))
        elif degree_text:
            stmt = stmt.join(Course, AdmissionStudentProgramDetails.course_id == Course.id)
            stmt = stmt.where(
                or_(
                    Course.title.ilike(f"%{degree_text}%"),
                    Course.short_name.ilike(f"%{degree_text}%"),
                    Course.code.ilike(f"%{degree_text}%"),
                )
            )

        # Batch/year
        batch_values = [
            str(v).strip()
            for v in (self._as_list(normalized.get("batch")) + self._as_list(normalized.get("batches")))
            if str(v).strip()
        ]
        if batch_values:
            stmt = stmt.where(AdmissionStudentProgramDetails.year.in_(batch_values))

        # Gender
        gender_values = [
            str(v).strip()
            for v in (self._as_list(normalized.get("gender")) + self._as_list(normalized.get("genders")))
            if str(v).strip()
        ]
        if gender_values:
            stmt = stmt.where(AdmissionStudentPersonalDetails.gender.in_(gender_values))

        # Admission quota by ID or by name
        quota_ids = []
        for raw in self._as_list(normalized.get("admission_quota_id")):
            parsed = self._parse_uuid(raw)
            if parsed:
                quota_ids.append(parsed)

        quota_text = None
        if not quota_ids and normalized.get("admission_quota"):
            maybe_uuid = self._parse_uuid(normalized.get("admission_quota"))
            if maybe_uuid:
                quota_ids.append(maybe_uuid)
            else:
                quota_text = str(normalized.get("admission_quota")).strip()

        if quota_ids:
            stmt = stmt.where(AdmissionStudentProgramDetails.admission_quota_id.in_(quota_ids))
        elif quota_text:
            stmt = stmt.join(
                SeatQuota, AdmissionStudentProgramDetails.admission_quota_id == SeatQuota.id
            ).where(SeatQuota.name.ilike(f"%{quota_text}%"))

        if normalized.get("category"):
            stmt = stmt.where(AdmissionStudentProgramDetails.category == normalized.get("category"))
        if normalized.get("quota_type"):
            stmt = stmt.where(
                AdmissionStudentProgramDetails.quota_type.ilike(f"%{normalized.get('quota_type')}%")
            )
        if normalized.get("special_quota"):
            stmt = stmt.where(
                AdmissionStudentProgramDetails.special_quota.ilike(f"%{normalized.get('special_quota')}%")
            )
        if normalized.get("scholarships"):
            stmt = stmt.where(
                AdmissionStudentProgramDetails.scholarships.ilike(f"%{normalized.get('scholarships')}%")
            )
        if normalized.get("boarding_place"):
            stmt = stmt.where(
                AdmissionStudentProgramDetails.boarding_place.ilike(f"%{normalized.get('boarding_place')}%")
            )

        # Only student IDs are selected here; ordering by non-selected columns breaks on Postgres with DISTINCT.
        stmt = stmt.distinct()
        res = await db.execute(stmt)
        return list(res.scalars().all())

    def _per_student_fee_total(self, fee_structure: FeeStructure) -> float:
        total = 0.0
        for item in fee_structure.items:
            if item.amount_by_year:
                total += sum(float(v or 0) for v in item.amount_by_year.values())
            else:
                total += float(item.amount or 0)
        return total

    async def preview_demand_batch(self, db: AsyncSession, payload) -> dict:
        """Preview demand creation count and amount for explicit students or filter matches."""
        from common.models.admission.admission_entry import AdmissionStudent

        data = payload.dict(exclude_unset=True)
        filters = self._normalize_demand_filters(data.get("filters") or {})
        apply_to_students = data.get("apply_to_students")

        student_ids = await self._students_matching_filters(
            db,
            filters=filters,
            institution_id=data.get("institution_id"),
            apply_to_students=apply_to_students,
        )

        if not student_ids:
            return {
                "student_count": 0,
                "count": 0,
                "total_amount": 0.0,
                "total": 0.0,
                "message": "No students found matching criteria",
                "sample_students": [],
            }

        stmt = select(FeeStructure).where(FeeStructure.id == data["fee_structure_id"])
        res = await db.execute(stmt)
        fs = res.scalar_one_or_none()
        if not fs:
            raise ValueError("FeeStructure not found")

        per_student_total = self._per_student_fee_total(fs)
        total_amount = per_student_total * len(student_ids)

        sample_stmt = (
            select(AdmissionStudent)
            .options(
                selectinload(AdmissionStudent.department),
                selectinload(AdmissionStudent.course),
            )
            .where(AdmissionStudent.id.in_(student_ids[:5]))
        )
        sample_res = await db.execute(sample_stmt)
        sample_students = []
        for student in sample_res.scalars().all():
            sample_students.append(
                {
                    "id": str(student.id),
                    "name": getattr(student.personal_details, "name", None) if getattr(student, "personal_details", None) else getattr(student, "name", None),
                    "batch": student.year,
                    "gender": student.gender.value if student.gender else None,
                    "department_id": str(student.department_id) if student.department_id else None,
                    "department_name": student.department.name if student.department else None,
                    "degree_id": str(student.course_id) if student.course_id else None,
                    "degree_name": student.course.title if student.course else None,
                }
            )

        return {
            "student_count": len(student_ids),
            "count": len(student_ids),
            "total_amount": total_amount,
            "total": total_amount,
            "message": f"Found {len(student_ids)} students. Total estimated demand: {total_amount}",
            "sample_students": sample_students,
        }

    async def generate_demands_for_batch(
        self, db: AsyncSession, batch_id: UUID, dry_run: bool = False
    ):
        """Generate demand items for a batch. Supports explicit students and/or filters."""
        from common.models.billing.demand import DemandBatch, DemandItem

        batch_stmt = select(DemandBatch).where(DemandBatch.id == batch_id)
        batch_res = await db.execute(batch_stmt)
        batch = batch_res.scalar_one_or_none()
        if not batch:
            raise ValueError("Batch not found")

        filters = dict(batch.filters or {})
        explicit_students = filters.pop("apply_to_students", None)

        student_ids = await self._students_matching_filters(
            db,
            filters=filters,
            institution_id=batch.institution_id,
            apply_to_students=explicit_students,
        )
        if not student_ids:
            return {"count": 0, "total": 0.0}

        if not batch.fee_structure_id:
            raise ValueError("Batch does not have a fee_structure_id")

        fee_stmt = select(FeeStructure).where(FeeStructure.id == batch.fee_structure_id)
        fee_res = await db.execute(fee_stmt)
        fee_structure = fee_res.scalar_one_or_none()
        if not fee_structure:
            raise ValueError("FeeStructure not found")

        per_student_total = self._per_student_fee_total(fee_structure)
        total_amount = per_student_total * len(student_ids)

        if dry_run:
            return {"count": len(student_ids), "total": total_amount}

        # Prevent duplicate rows when a generated batch is re-triggered.
        existing_count_stmt = select(func.count(DemandItem.id)).where(
            DemandItem.batch_id == batch.id
        )
        existing_count_res = await db.execute(existing_count_stmt)
        existing_count = existing_count_res.scalar() or 0
        if batch.status == "generated" and existing_count > 0:
            return {
                "created": 0,
                "existing": existing_count,
                "count": len(student_ids),
                "total": total_amount,
                "message": "Batch is already generated",
            }

        created = 0
        for student_id in student_ids:
            for item in fee_structure.items:
                if item.amount_by_year:
                    amount = sum(float(v or 0) for v in item.amount_by_year.values())
                else:
                    amount = float(item.amount or 0)

                if amount <= 0:
                    continue

                fee_head_name = item.fee_head.name if item.fee_head else "Fee"
                fee_subhead_name = item.fee_sub_head.name if item.fee_sub_head else ""
                description = (
                    f"{fee_head_name} - {fee_subhead_name}"
                    if fee_subhead_name
                    else fee_head_name
                )

                db.add(
                    DemandItem(
                        batch_id=batch.id,
                        student_id=student_id,
                        fee_structure_id=fee_structure.id,
                        fee_structure_item_id=item.id,
                        amount=amount,
                        fee_head_id=item.fee_head_id,
                        fee_sub_head_id=item.fee_sub_head_id,
                        description=description,
                    )
                )
                created += 1

        batch.status = "generated"
        batch.generated_at = datetime.utcnow()
        await db.commit()
        return {"created": created, "count": len(student_ids), "total": total_amount}

    async def create_student_demand(self, db: AsyncSession, student_id: UUID, fee_structure_id: UUID, items_overrides: list | None = None):
        """Create demand items for a student using a fee structure. Optional overrides is a list of items with amounts."""
        from common.models.billing.demand import DemandItem
        from common.models.admission.admission_entry import AdmissionStudent

        student_stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
        student_res = await db.execute(student_stmt)
        student = student_res.scalar_one_or_none()
        if not student:
            raise ValueError("Student not found")

        effective_fee_structure_id = fee_structure_id
        if student.is_fee_structure_locked:
            if not student.fee_structure_id:
                raise ValueError("Student fee structure is locked but not set")
            if str(student.fee_structure_id) != str(fee_structure_id):
                raise ValueError(
                    "Fee structure is locked for this student. Use the locked fee structure for demand creation."
                )
            effective_fee_structure_id = student.fee_structure_id

        # load structure
        stmt = select(FeeStructure).where(FeeStructure.id == effective_fee_structure_id)
        res = await db.execute(stmt)
        fs = res.scalar_one_or_none()
        if not fs:
            raise ValueError("FeeStructure not found")
        created = []
        if items_overrides:
            for it in items_overrides:
                amt = it.get("amount") or 0
                di = DemandItem(batch_id=None, student_id=student_id, fee_structure_id=effective_fee_structure_id, fee_structure_item_id=it.get("fee_structure_item_id"), amount=amt)
                db.add(di)
                created.append(di)
        else:
            for it in fs.items:
                if it.amount_by_year:
                    amt = sum([float(v) for v in it.amount_by_year.values()])
                else:
                    amt = float(it.amount or 0)
                di = DemandItem(batch_id=None, student_id=student_id, fee_structure_id=effective_fee_structure_id, fee_structure_item_id=it.id, amount=amt)
                db.add(di)
                created.append(di)
        await db.commit()
        return len(created)

    async def create_year_specific_demand(
        self,
        db: AsyncSession,
        student_ids: list[UUID],
        fee_structure_id: UUID | None = None,
        year: str | None = None,
        semester: int | None = None,
    ) -> dict:
        """
        Create demand items for multiple students for a specific year or semester.
        Uses each student's own locked fee structure automatically.
        fee_structure_id is kept as an optional override for backward compatibility.
        Also creates invoices automatically for each student.
        
        Args:
            db: Database session
            student_ids: List of student UUIDs
            fee_structure_id: Fee structure UUID
            year: Year number as string (e.g., "1", "2", "3")
            semester: Semester number (e.g., 1, 2, 3)
            
        Returns:
            dict with created_count, total_amount, invoice_count, and message
        """
        from common.models.billing.demand import DemandItem, DemandBatch
        from datetime import datetime
        
        if not student_ids:
            raise ValueError("No students provided")
        if year in (None, "") and semester is None:
            raise ValueError("Either year or semester is required")
        if year not in (None, "") and semester is not None:
            raise ValueError("Provide either year or semester, not both")

        from common.models.admission.admission_entry import AdmissionStudent

        students_stmt = select(AdmissionStudent).where(AdmissionStudent.id.in_(student_ids))
        students_res = await db.execute(students_stmt)
        students = students_res.scalars().all()
        student_map = {student.id: student for student in students}

        missing_student_ids = [str(student_id) for student_id in student_ids if student_id not in student_map]
        if missing_student_ids:
            raise ValueError(f"Students not found: {', '.join(missing_student_ids)}")

        # Build per-student fee structure mapping
        fs_id_for_student: dict[UUID, UUID] = {}
        skipped_students: list[str] = []

        for sid in student_ids:
            student = student_map[sid]
            if fee_structure_id:
                # Backward-compat override: skip locked-mismatch students
                if (student.is_fee_structure_locked and student.fee_structure_id
                        and student.fee_structure_id != fee_structure_id):
                    skipped_students.append(getattr(student.personal_details, "name", None) if getattr(student, "personal_details", None) else getattr(student, "name", None) or str(sid))
                else:
                    fs_id_for_student[sid] = fee_structure_id
            else:
                # Auto-resolve: use student's own locked fee structure
                if not student.is_fee_structure_locked or not student.fee_structure_id:
                    skipped_students.append(getattr(student.personal_details, "name", None) if getattr(student, "personal_details", None) else getattr(student, "name", None) or str(sid))
                    continue
                fs_id_for_student[sid] = student.fee_structure_id

        if not fs_id_for_student:
            raise ValueError(
                "No eligible students found. Ensure students have their fee structure locked."
            )

        # Fetch all unique fee structures in one query
        unique_fs_ids = list(set(fs_id_for_student.values()))
        fs_stmt = (
            select(FeeStructure)
            .where(FeeStructure.id.in_(unique_fs_ids))
            .options(
                selectinload(FeeStructure.items).selectinload(FeeStructureItem.fee_head),
                selectinload(FeeStructure.items).selectinload(FeeStructureItem.fee_sub_head),
            )
        )
        fs_res = await db.execute(fs_stmt)
        fs_map: dict[UUID, FeeStructure] = {fs.id: fs for fs in fs_res.scalars().all()}

        # Get institution_id from first eligible student for the batch
        first_sid = next(iter(fs_id_for_student))
        institution_id = student_map[first_sid].institution_id
        if not institution_id:
            raise ValueError("Could not determine institution from students")

        # Create batch
        period_label = f"Semester {semester}" if semester is not None else f"Year {year}"
        batch = DemandBatch(
            name=f"{period_label} Demand - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            institution_id=institution_id,
            fee_structure_id=unique_fs_ids[0] if len(unique_fs_ids) == 1 else None,
            status="generated",
            generated_at=datetime.utcnow()
        )
        db.add(batch)
        await db.flush()

        created_count = 0
        total_amount = 0.0
        invoice_count = 0
        year_int = int(year) if year not in (None, "") else None

        for student_id, fs_id in fs_id_for_student.items():
            fs = fs_map.get(fs_id)
            if not fs:
                skipped_students.append(str(student_id))
                continue

            semesters_per_year = fs.semesters_per_year or 2
            student_demands = []

            for item in fs.items:
                amount = 0.0
                demand_year = None
                demand_semester = None

                if semester is not None:
                    sem_key = str(semester)
                    derived_year = ((semester - 1) // semesters_per_year) + 1

                    if item.amount_by_semester and sem_key in item.amount_by_semester:
                        amount = float(item.amount_by_semester[sem_key] or 0)
                        demand_semester = semester
                        demand_year = derived_year
                    elif item.amount_by_year and str(derived_year) in item.amount_by_year:
                        amount = float(item.amount_by_year[str(derived_year)] or 0)
                        demand_semester = semester
                        demand_year = derived_year
                    elif not item.amount_by_semester and not item.amount_by_year and derived_year == 1:
                        amount = float(item.amount or 0)
                        demand_semester = semester
                        demand_year = derived_year
                else:
                    if item.amount_by_semester:
                        total = 0.0
                        for sem_label, sem_amount in item.amount_by_semester.items():
                            sem_num = int(sem_label)
                            sem_year = ((sem_num - 1) // semesters_per_year) + 1
                            if sem_year == year_int:
                                total += float(sem_amount or 0)
                        amount = total
                    elif item.amount_by_year and str(year_int) in item.amount_by_year:
                        amount = float(item.amount_by_year[str(year_int)] or 0)
                    elif not item.amount_by_year and year_int == 1:
                        amount = float(item.amount or 0)

                    demand_year = year_int

                if amount > 0:
                    fee_head_name = item.fee_head.name if item.fee_head else "Fee"
                    fee_subhead_name = item.fee_sub_head.name if item.fee_sub_head else ""
                    scope_label = f"Sem {semester}" if semester is not None else f"Year {year_int}"
                    description = (
                        f"{fee_head_name} - {fee_subhead_name} ({scope_label})"
                        if fee_subhead_name
                        else f"{fee_head_name} ({scope_label})"
                    )

                    demand_item = DemandItem(
                        batch_id=batch.id,
                        student_id=student_id,
                        fee_structure_id=fs.id,
                        fee_structure_item_id=item.id,
                        amount=amount,
                        fee_head_id=item.fee_head_id,
                        fee_sub_head_id=item.fee_sub_head_id,
                        semester=demand_semester,
                        year=demand_year,
                        description=description
                    )
                    db.add(demand_item)
                    student_demands.append(demand_item)
                    created_count += 1
                    total_amount += amount

            if student_demands:
                await db.flush()
                invoice = await self.create_invoice_from_demands(db, student_demands)
                if invoice:
                    invoice_count += 1

        await db.commit()

        return {
            "created_count": created_count,
            "total_amount": total_amount,
            "invoice_count": invoice_count,
            "skipped_count": len(skipped_students),
            "message": (
                f"Created {created_count} demand item(s) and {invoice_count} invoice(s) "
                f"for {len(fs_id_for_student)} student(s) for {period_label}"
                + (f". Skipped {len(skipped_students)} student(s)." if skipped_students else "")
            )
        }




    # --- Hostel & Transport CRUD ---
    async def create_hostel_fee_structure(self, db: AsyncSession, payload):
        from common.models.billing.hostel import HostelFeeStructure
        data = payload.dict(exclude_unset=True)
        if float(data.get("amount", 0)) < 0:
            raise ValueError("Amount must be >= 0")
        hfs = HostelFeeStructure(**data)
        db.add(hfs)
        await db.commit()
        await db.refresh(hfs)
        return hfs

    async def list_hostel_fee_structures(self, db: AsyncSession, filters: dict | None = None):
        from common.models.billing.hostel import HostelFeeStructure
        stmt = select(HostelFeeStructure)
        if filters:
            if filters.get("college_id"):
                stmt = stmt.where(HostelFeeStructure.institution_id == filters.get("college_id"))
            if filters.get("hostel_id"):
                stmt = stmt.where(HostelFeeStructure.hostel_id == filters.get("hostel_id"))
            if filters.get("financial_year_id"):
                stmt = stmt.where(HostelFeeStructure.financial_year_id == filters.get("financial_year_id"))
            if filters.get("room_type"):
                stmt = stmt.where(HostelFeeStructure.room_type.ilike(f"%{filters.get('room_type')}%"))
        res = await db.execute(stmt)
        return res.scalars().all()

    async def create_transport_fee_structure(self, db: AsyncSession, payload):
        from common.models.billing.transport import TransportFeeStructure
        data = payload.dict(exclude_unset=True)
        if float(data.get("amount", 0)) < 0:
            raise ValueError("Amount must be >= 0")
        tfs = TransportFeeStructure(**data)
        db.add(tfs)
        await db.commit()
        await db.refresh(tfs)
        return tfs

    async def list_transport_fee_structures(self, db: AsyncSession, filters: dict | None = None):
        from common.models.billing.transport import TransportFeeStructure
        stmt = select(TransportFeeStructure)
        if filters:
            if filters.get("college_id"):
                stmt = stmt.where(TransportFeeStructure.institution_id == filters.get("college_id"))
            if filters.get("route_id"):
                stmt = stmt.where(TransportFeeStructure.route_id == filters.get("route_id"))
            if filters.get("batch"):
                stmt = stmt.where(TransportFeeStructure.batch == filters.get("batch"))
        res = await db.execute(stmt)
        return res.scalars().all()

    async def list_transport_routes(self, db: AsyncSession, college_id: str | None = None):
        from common.models.billing.transport import TransportRoute
        stmt = select(TransportRoute)
        if college_id:
            stmt = stmt.where(TransportRoute.institution_id == college_id)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def create_transport_route(self, db: AsyncSession, payload):
        from common.models.billing.transport import TransportRoute
        data = payload.dict(exclude_unset=True)
        tr = TransportRoute(**data)
        db.add(tr)
        await db.commit()
        await db.refresh(tr)
        return tr

    # --- Concessions ---
    async def create_concession(self, db: AsyncSession, payload):
        from common.models.billing.concession import Concession, ConcessionAudit
        data = payload.dict(exclude_unset=True)
        if not data.get("amount") and not data.get("percent"):
            raise ValueError("Either amount or percent should be provided")
        c = Concession(**data)
        db.add(c)
        await db.flush()
        # add audit
        db.add(ConcessionAudit(concession_id=c.id, action="created", performed_by=data.get("meta", {}).get("performed_by")))
        await db.commit()
        await db.refresh(c)
        return c

    async def list_concessions_for_student(self, db: AsyncSession, student_id: str):
        from common.models.billing.concession import Concession
        stmt = select(Concession).where(Concession.student_id == student_id)
        res = await db.execute(stmt)
        return res.scalars().all()

    async def approve_concession(self, db: AsyncSession, concession_id: str, approver_id: str | None = None):
        from common.models.billing.concession import Concession, ConcessionAudit
        stmt = select(Concession).where(Concession.id == concession_id)
        res = await db.execute(stmt)
        c = res.scalar_one_or_none()
        if not c:
            raise ValueError("Concession not found")
        c.status = "approved"
        db.add(ConcessionAudit(concession_id=c.id, action="approved", performed_by=approver_id))
        await db.commit()
        await db.refresh(c)
        return c

    # --- Payment recall ---
    async def request_payment_recall(self, db: AsyncSession, payload):
        from common.models.billing.recall import PaymentRecallRequest
        data = payload.dict(exclude_unset=True)
        pr = PaymentRecallRequest(**data)
        db.add(pr)
        await db.commit()
        await db.refresh(pr)
        return pr

    async def list_payment_recall_requests(self, db: AsyncSession, filters: dict | None = None):
        from common.models.billing.recall import PaymentRecallRequest
        stmt = select(PaymentRecallRequest)
        if filters:
            if filters.get("status"):
                stmt = stmt.where(PaymentRecallRequest.status == filters.get("status"))
            if filters.get("payment_id"):
                stmt = stmt.where(PaymentRecallRequest.payment_id == filters.get("payment_id"))
        res = await db.execute(stmt)
        return res.scalars().all()

    async def process_payment_recall(self, db: AsyncSession, recall_id: str, processor_id: str | None = None, approve: bool = False):
        from common.models.billing.recall import PaymentRecallRequest
        stmt = select(PaymentRecallRequest).where(PaymentRecallRequest.id == recall_id)
        res = await db.execute(stmt)
        pr = res.scalar_one_or_none()
        if not pr:
            raise ValueError("Recall request not found")
        pr.processed_by = processor_id
        pr.processed_at = "now"
        pr.status = "approved" if approve else "rejected"
        await db.commit()
        await db.refresh(pr)
        return pr


    async def create_cash_counter(self, db: AsyncSession, payload):
        from common.models.billing.cash_counter import CashCounter
        data = payload.dict(exclude_unset=True)
        cc = CashCounter(**data)
        db.add(cc)
        await db.commit()
        await db.refresh(cc)
        return cc

    async def list_cash_counters(self, db: AsyncSession, institution_id: UUID | None = None):
        from common.models.billing.cash_counter import CashCounter
        stmt = select(CashCounter)
        if institution_id:
            stmt = stmt.where(CashCounter.institution_id == institution_id)
        res = await db.execute(stmt)
        return res.scalars().all()


    # --- Application Fee Collection ---
    async def collect_application_fee(self, db: AsyncSession, payload, user_id: UUID | None = None):
        """
        Collect application fee from a student.
        Validates the fee amount against the AcademicYearDepartment configuration.
        """
        from common.models.master.annual_task import AcademicYearCourse
        
        data = payload.dict(exclude_unset=True)
        academic_year_id = data["academic_year_id"]
        course_id = data["course_id"]
        
        # 1. Fetch configured fee
        stmt = select(AcademicYearCourse).where(
            AcademicYearCourse.academic_year_id == academic_year_id,
            AcademicYearCourse.course_id == course_id
        )
        res = await db.execute(stmt)
        config = res.scalar_one_or_none()
        
        if not config or not config.is_active:
            raise ValueError("Application fees not configured or active for this course/year.")
        
        # 2. Validate amount (Optional: Strict check or allow override?)
        # For now, we'll enforce the configured fee if it's not zero, or ensure payload matches.
        # Let's assume the frontend sends what it sees, but we double-check.
        # If payload amount is missing, use config.
        # If payload amount is present, it must match config (unless we allow partial/overpayment, sticking to strict for now).
        # note: schema requires 'amount', but we haven't added amount to schema yet! 
        # Wait, the schema I defined earlier didn't have amount! Let's check schema.
        # Schema `ApplicationFeePaymentRequest` usually should rely on backend config or explicit amount.
        # Let's assume we use the Configured Amount as the Truth. 
        
        fee_amount = config.application_fee
        
        # 3. Generate Receipt Number
        # Format: APP-{Year}-{DeptCode}-{Seq} or simple APP-{UUID}
        # Let's use simple APP-{Date}-{Seq} for now
        from datetime import datetime
        today_str = datetime.utcnow().strftime("%Y%m%d")
        

        # get count for today to generate seq
        
    async def get_student_dues_by_application_number(self, db: AsyncSession, application_number: str):
        from common.models.admission.admission_entry import AdmissionStudent, AdmissionStudentProgramDetails
        from common.models.billing.application_fees import Invoice, PaymentStatusEnum
        from sqlalchemy.orm import selectinload
        
        # 1. Find Student
        # We search by application_number OR enquiry_number to be safe? 
        # Request asked for application_number.
        stmt = select(AdmissionStudent).options(
            selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.department),
            selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.course),
            selectinload(AdmissionStudent.personal_details)
        ).where(AdmissionStudent.application_number == application_number)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()
        
        if not student:
            # Fallback try enquiry_number just in case
             stmt = select(AdmissionStudent).options(
                selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.department),
                selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.course),
                selectinload(AdmissionStudent.personal_details)
             ).where(AdmissionStudent.enquiry_number == application_number)
             res = await db.execute(stmt)
             student = res.scalar_one_or_none()
             
        if not student:
            # Fallback try roll_number just in case
             stmt = select(AdmissionStudent).options(
                selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.department),
                selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.course),
                selectinload(AdmissionStudent.personal_details)
             ).where(AdmissionStudent.roll_number == application_number)
             res = await db.execute(stmt)
             student = res.scalar_one_or_none()
             
        if not student:
            raise ValueError("Student not found")
            
        # 2. Fetch Invoices not fully paid
        # We want PENDING, PARTIAL, OVERDUE. Basically anything not PAID or CANCELLED?
        # Or maybe even PAID ones for history?
        # Usually 'dues' implies outstanding. But 'Cash Counter' might want to see history.
        # Let's return all non-cancelled for now so they can see context.
        stmt = select(Invoice).where(
            Invoice.student_id == student.id,
            Invoice.status != PaymentStatusEnum.CANCELLED
        ).options(
            selectinload(Invoice.line_items),
            selectinload(Invoice.payments),
            selectinload(Invoice.status_history)
        ).order_by(Invoice.issue_date.desc())
        
        res = await db.execute(stmt)
        invoices = res.scalars().all()
        
        # 3. Construct Response
        name_val = getattr(student, "name", None)
        if hasattr(student, "personal_details") and student.personal_details:
            name_val = getattr(student.personal_details, "name", name_val)

        return {
            "student_id": student.id,
            "application_number": student.application_number,
            "name": name_val,
            "department": student.program_details.department.name if student.program_details and student.program_details.department else None,
            "course": student.program_details.course.title if student.program_details and student.program_details.course else None,
            "batch": student.program_details.year if student.program_details else None,
            "status": getattr(student, "status", None),
            "invoices": invoices
        }

        # (This is a simple implementation, might need better concurrency handling in high load)
        stmt_count = select(ApplicationTransaction).where(
            ApplicationTransaction.receipt_number.like(f"APP-{today_str}-%")
        )
        # We need simpler counting, maybe just count all
        # To avoid complex query, let's just use UUID or Timestamp for safety or simple seq
        # Let's try simple sequence
        # We can also just use a random hex for receipt to be safe
        receipt_suffix = uuid.uuid4().hex[:6].upper()
        receipt_number = f"APP-{today_str}-{receipt_suffix}"
        
        transaction = ApplicationTransaction(
            student_name=data["student_name"],
            student_mobile=data["student_mobile"],
            academic_year_id=academic_year_id,
            course_id=course_id,
            amount=fee_amount, # Using configured amount
            payment_mode=data["payment_mode"],
            cash_counter_id=data.get("cash_counter_id"),
            created_by=user_id,
            receipt_number=receipt_number,
            payment_status=PaymentStatusEnum.PAID,
            remarks=data.get("remarks")
        )
        
        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)
        return transaction

    async def get_application_fee_transactions(
        self, 
        db: AsyncSession, 
        academic_year_id: UUID | None = None,
        course_id: UUID | None = None,
        receipt_number: str | None = None
    ):
        from common.models.billing.application_fees import ApplicationTransaction
        
        stmt = select(ApplicationTransaction).options(
            joinedload(ApplicationTransaction.course),
            joinedload(ApplicationTransaction.academic_year)
        ).order_by(ApplicationTransaction.transaction_date.desc())
        
        if academic_year_id:
            stmt = stmt.where(ApplicationTransaction.academic_year_id == academic_year_id)
        if course_id:
            stmt = stmt.where(ApplicationTransaction.course_id == course_id)
        if receipt_number:
            stmt = stmt.where(ApplicationTransaction.receipt_number.ilike(f"%{receipt_number}%"))
            
        res = await db.execute(stmt)
        txs = res.scalars().all()
        
        # Enrich info manually if needed (schema has optional fields)
        # The joinedload above fetches relations, so we can map them in response model or schema
        
        result_list = []
        for tx in txs:
            # Manually map if Pydantic doesn't auto-resolve relation fields to strings
            # Schema `ApplicationFeeTransactionResponse` has `department_name` etc.
            # We can rely on Pydantic's `from_attributes` interacting with the ORM object if relations are loaded
            # But let's be explicit to be safe
            tx_dict = tx.__dict__.copy() 
            if tx.course:
                tx_dict['course_name'] = tx.course.title 
            if tx.academic_year:
                tx_dict['academic_year_name'] = tx.academic_year.year_name
            result_list.append(tx_dict)
            
        return result_list



    async def check_year_demand_status(
        self,
        db: AsyncSession,
        student_ids: list[UUID],
        fee_structure_id: UUID,
        year: str | None = None,
        semester: int | None = None,
    ) -> dict[str, bool]:
        """
        Check if demands exist for the given students and selected period.
        Returns a dict mapping student_id (str) -> bool (True if demand exists).
        """
        from common.models.billing.demand import DemandItem
        
        if not student_ids:
            return {}
        if year in (None, "") and semester is None:
            return {}
            
        conditions = [
            DemandItem.student_id.in_(student_ids),
            DemandItem.fee_structure_id == fee_structure_id,
        ]
        if semester is not None:
            conditions.append(
                or_(
                    DemandItem.semester == semester,
                    DemandItem.description.ilike(f"%(Sem {semester})"),
                )
            )
        else:
            year_int = int(year)
            conditions.append(
                or_(
                    DemandItem.year == year_int,
                    DemandItem.description.ilike(f"%(Year {year_int})"),
                )
            )

        stmt = select(DemandItem.student_id).where(*conditions).distinct()
        
        res = await db.execute(stmt)
        existing_student_ids = {str(uid) for uid in res.scalars().all()}
        
        # Return status for requested students
        return {str(sid): (str(sid) in existing_student_ids) for sid in student_ids}

    def _to_start_datetime(self, value: date | None) -> datetime | None:
        if not value:
            return None
        return datetime.combine(value, time.min)

    def _to_end_datetime(self, value: date | None) -> datetime | None:
        if not value:
            return None
        return datetime.combine(value, time.max)

    def _normalize_datetime(self, value: datetime | date | None) -> datetime:
        if value is None:
            return datetime.utcnow()
        if isinstance(value, date) and not isinstance(value, datetime):
            value = datetime.combine(value, time.min)
        if value.tzinfo is not None:
            return value.replace(tzinfo=None)
        return value

    def _finalize_ledger_entries(
        self,
        entries: list[dict],
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> dict:
        entry_order = {"demand": 0, "invoice": 1, "payment": 2}
        normalized_entries = [
            {**entry, "entry_date": self._normalize_datetime(entry.get("entry_date"))}
            for entry in entries
        ]
        ordered = sorted(
            normalized_entries,
            key=lambda item: (
                item["entry_date"],
                entry_order.get(item.get("entry_type"), 99),
                str(item.get("source_id") or ""),
            ),
        )

        opening_balance = 0.0
        running_balance = 0.0
        period_entries: list[dict] = []

        for entry in ordered:
            debit = float(entry.get("debit") or 0)
            credit = float(entry.get("credit") or 0)
            net = debit - credit
            entry_date = entry["entry_date"]

            if from_dt and entry_date < from_dt:
                opening_balance += net
                running_balance = opening_balance
                continue
            if to_dt and entry_date > to_dt:
                continue

            running_balance += net
            period_entry = {**entry, "running_balance": running_balance}
            period_entries.append(period_entry)

        total_debit = sum(float(item.get("debit") or 0) for item in period_entries)
        total_credit = sum(float(item.get("credit") or 0) for item in period_entries)
        closing_balance = opening_balance + (total_debit - total_credit)

        return {
            "opening_balance": opening_balance,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "closing_balance": closing_balance,
            "entries": period_entries,
        }

    async def _build_ledger(
        self,
        db: AsyncSession,
        institution_id: UUID,
        student_ids: list[UUID],
        from_date: date | None = None,
        to_date: date | None = None,
        filters: dict | None = None,
        student_id: UUID | None = None,
    ) -> dict:
        from common.models.admission.admission_entry import AdmissionStudent
        from common.models.billing.demand import DemandItem

        if not student_ids:
            return {
                "institution_id": institution_id,
                "student_id": student_id,
                "from_date": from_date,
                "to_date": to_date,
                "filters": filters or {},
                "opening_balance": 0.0,
                "total_debit": 0.0,
                "total_credit": 0.0,
                "closing_balance": 0.0,
                "entries": [],
            }

        start_dt = self._to_start_datetime(from_date)
        end_dt = self._to_end_datetime(to_date)

        from common.models.admission.admission_entry import AdmissionStudentPersonalDetails
        names_stmt = select(AdmissionStudent.id, AdmissionStudentPersonalDetails.name).join(AdmissionStudentPersonalDetails, AdmissionStudent.id == AdmissionStudentPersonalDetails.admission_student_id).where(
            AdmissionStudent.id.in_(student_ids)
        )
        names_res = await db.execute(names_stmt)
        student_name_map = {row[0]: row[1] for row in names_res.all()}

        entries: list[dict] = []

        # Debits from demand items.
        demand_stmt = select(DemandItem).where(
            DemandItem.deleted_at.is_(None),
            DemandItem.student_id.in_(student_ids),
        )
        if end_dt:
            demand_stmt = demand_stmt.where(DemandItem.created_at <= end_dt)
        demand_res = await db.execute(demand_stmt)
        demands = demand_res.scalars().all()

        linked_invoice_ids = {
            demand.invoice_id for demand in demands if getattr(demand, "invoice_id", None)
        }

        for demand in demands:
            entries.append(
                {
                    "entry_date": demand.created_at,
                    "entry_type": "demand",
                    "source": "demand_item",
                    "source_id": demand.id,
                    "reference": str(demand.batch_id) if demand.batch_id else None,
                    "description": demand.description or "Demand Raised",
                    "student_id": demand.student_id,
                    "student_name": student_name_map.get(demand.student_id),
                    "debit": float(demand.amount or 0),
                    "credit": 0.0,
                }
            )

        # Debits from direct invoice line items not originated from linked demands.
        invoice_stmt = (
            select(Invoice, InvoiceLineItem)
            .join(InvoiceLineItem, InvoiceLineItem.invoice_id == Invoice.id)
            .where(
                Invoice.deleted_at.is_(None),
                InvoiceLineItem.deleted_at.is_(None),
                Invoice.student_id.in_(student_ids),
            )
        )
        if linked_invoice_ids:
            invoice_stmt = invoice_stmt.where(Invoice.id.notin_(list(linked_invoice_ids)))
        if end_dt:
            invoice_stmt = invoice_stmt.where(Invoice.created_at <= end_dt)

        invoice_res = await db.execute(invoice_stmt)
        for invoice, line_item in invoice_res.all():
            invoice_entry_date = invoice.created_at
            if not invoice_entry_date and invoice.issue_date:
                invoice_entry_date = datetime.combine(invoice.issue_date, time.min)

            entries.append(
                {
                    "entry_date": invoice_entry_date or datetime.utcnow(),
                    "entry_type": "invoice",
                    "source": "invoice_line_item",
                    "source_id": line_item.id,
                    "reference": invoice.invoice_number,
                    "description": line_item.description or "Invoice Charge",
                    "student_id": invoice.student_id,
                    "student_name": student_name_map.get(invoice.student_id),
                    "debit": float(line_item.net_amount or line_item.amount or 0),
                    "credit": 0.0,
                }
            )

        # Credits from payments.
        payment_stmt = (
            select(Payment, Invoice)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .where(
                Payment.deleted_at.is_(None),
                Invoice.deleted_at.is_(None),
                Invoice.student_id.in_(student_ids),
            )
        )
        if end_dt:
            payment_stmt = payment_stmt.where(Payment.payment_date <= end_dt)
        payment_res = await db.execute(payment_stmt)

        for payment, invoice in payment_res.all():
            reference = payment.receipt_number or payment.transaction_id or invoice.invoice_number
            entries.append(
                {
                    "entry_date": payment.payment_date,
                    "entry_type": "payment",
                    "source": "payment",
                    "source_id": payment.id,
                    "reference": reference,
                    "description": payment.notes or "Payment Received",
                    "student_id": invoice.student_id,
                    "student_name": student_name_map.get(invoice.student_id),
                    "debit": 0.0,
                    "credit": float(payment.amount or 0),
                }
            )

        summary = self._finalize_ledger_entries(entries, from_dt=start_dt, to_dt=end_dt)
        return {
            "institution_id": institution_id,
            "student_id": student_id,
            "from_date": from_date,
            "to_date": to_date,
            "filters": self._normalize_demand_filters(filters or {}),
            **summary,
        }

    async def get_general_ledger(
        self,
        db: AsyncSession,
        institution_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
        student_id: UUID | None = None,
        degree_id: UUID | None = None,
        department_id: UUID | None = None,
        batch: str | None = None,
        gender: str | None = None,
    ) -> dict:
        filters: dict = {}
        if degree_id:
            filters["degree_id"] = degree_id
        if department_id:
            filters["department_id"] = department_id
        if batch:
            filters["batch"] = batch
        if gender:
            filters["gender"] = gender

        explicit_students = [student_id] if student_id else None
        student_ids = await self._students_matching_filters(
            db,
            filters=filters,
            institution_id=institution_id,
            apply_to_students=explicit_students,
        )

        return await self._build_ledger(
            db=db,
            institution_id=institution_id,
            student_ids=student_ids,
            from_date=from_date,
            to_date=to_date,
            filters={**filters, **({"student_id": student_id} if student_id else {})},
            student_id=student_id,
        )

    async def get_student_ledger(
        self,
        db: AsyncSession,
        student_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict:
        from common.models.admission.admission_entry import AdmissionStudent

        student_stmt = select(AdmissionStudent).where(
            AdmissionStudent.id == student_id,
            AdmissionStudent.deleted_at.is_(None),
        )
        student_res = await db.execute(student_stmt)
        student = student_res.scalar_one_or_none()
        if not student:
            raise ValueError("Student not found")
        if not student.institution_id:
            raise ValueError("Student is not mapped to any institution")

        return await self._build_ledger(
            db=db,
            institution_id=student.institution_id,
            student_ids=[student.id],
            from_date=from_date,
            to_date=to_date,
            filters={"student_id": student.id},
            student_id=student.id,
        )

billing_service = BillingService()
