from uuid import UUID
from sqlalchemy.orm import sessionmaker, joinedload, selectinload
from sqlalchemy import select
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

    async def handle_course_change(self, db: AsyncSession, student_id: UUID, new_fee_structure_id: UUID):
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

        # 1. Automatic Fee Structure Lookup
        if not fee_structure_id:
            # Find fee structure matching: Academic Year + Course + Admission Type + Quota + Gender (optional)
            stmt = select(FeeStructure).where(
                FeeStructure.admission_year_id == student.academic_year_id,
                FeeStructure.degree_id == student.course_id,
                FeeStructure.admission_type_id == student.admission_type_id,
                FeeStructure.quota_id == student.admission_quota_id,
                # FeeStructure.quota_id.is_(None) if not student.admission_quota_id else FeeStructure.quota_id == student.admission_quota_id
                # FeeStructure.admission_type_id.is_(None) if not student.admission_type_id else FeeStructure.admission_type_id == student.admission_type_id
            )
            
            # Filter by Quota (Handle Nulls)
            if student.admission_quota_id:
                stmt = stmt.where(FeeStructure.quota_id == student.admission_quota_id)
            else:
                 stmt = stmt.where(FeeStructure.quota_id.is_(None))

            # Filter by Admission Type (Handle Nulls)
            if student.admission_type_id:
                stmt = stmt.where(FeeStructure.admission_type_id == student.admission_type_id)
            else:
                stmt = stmt.where(FeeStructure.admission_type_id.is_(None))
                
            
            # Optional: Add Gender filter if you have specific gender-based fees
            # if student.gender:
            #    stmt = stmt.where(or_(FeeStructure.gender == student.gender, FeeStructure.gender == GenderEnum.ALL))

            res = await db.execute(stmt)
            fs_list = res.scalars().all()
            
            if not fs_list:
                # Fallback: Try finding a generic structure (no quota/type)? 
                # For now, strict matching.
                print(f"No fee structure found for Student {student.name} (Type: {student.admission_type_id}, Quota: {student.admission_quota_id})")
                return [] # Or raise error?
            
            # If multiple found, pick the first active one?
            fs = fs_list[0] # Simplification
        else:
            # Fetch explicitly provided Fee Structure
            stmt = select(FeeStructure).options(selectinload(FeeStructure.items).selectinload(FeeStructureItem.fee_head)).where(FeeStructure.id == fee_structure_id)
            res = await db.execute(stmt)
            fs = res.scalar_one_or_none()
            if not fs:
                raise ValueError("Fee Structure not found")
            
        # 2. Iterate items and create demands
        created_demands = []
        # Reload items for the found fs
        await db.refresh(fs, ["items"])
        
        for item in fs.items:
            # Handle amount_by_year
            if item.amount_by_year:
                for year_label, year_amount in item.amount_by_year.items():
                    amount = float(year_amount)
                    if amount > 0:
                        # Determine Fee Head Name
                        # We need to load fee_head relationship if not loaded
                        # await db.refresh(item, ["fee_head"]) 
                        # Better to eager load in the query above.
                        
                        di = DemandItem(
                            batch_id=None, # Allow ad-hoc demand (model must support nullable)
                            student_id=student_id,
                            fee_structure_id=fs.id,
                            fee_structure_item_id=item.id,
                            amount=amount,
                            fee_head_id=item.fee_head_id,
                            description=f"{item.fee_head.name} - Year {year_label}" if item.fee_head else f"Fee - Year {year_label}"
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
                        description=item.fee_head.name if item.fee_head else "Fee"
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
        
        # 1. Fetch Student
        stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()
        if not student:
            raise ValueError("Student not found")
            
        if not student.course_id or not student.academic_year_id:
            return None # No course/year assigned
            
        # 2. Fetch Config
        stmt = select(AcademicYearCourse).where(
            AcademicYearCourse.academic_year_id == student.academic_year_id,
            AcademicYearCourse.course_id == student.course_id
        )
        res = await db.execute(stmt)
        config = res.scalar_one_or_none()
        
        if config and config.application_fee and config.application_fee > 0:
            # 3. Find 'Application Fee' Head
            stmt_head = select(FeeHead).where(
                FeeHead.institution_id == student.institution_id,
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
        stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()
        if not student:
            raise ValueError("Student not found for demands")
        institution_id = student.institution_id
        
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
            data = payload.dict(exclude_unset=True)
            # idempotency: check existing transaction_id
            transaction_id = data.get("transaction_id")
            if transaction_id:
                stmt = select(Payment).where(Payment.transaction_id == transaction_id)
                res = await db.execute(stmt)
                existing = res.scalar_one_or_none()
                if existing:
                    return existing

            stmt = select(Invoice).where(Invoice.id == invoice_id)
            res = await db.execute(stmt)
            invoice = res.scalar_one_or_none()
            if not invoice:
                raise ValueError("Invoice not found")

            payment = Payment(
                invoice_id=invoice.id,
                cash_counter_id=counter_id,
                amount=data["amount"],
                payment_method=data["payment_method"],
                transaction_id=transaction_id,
                receipt_number=data.get("receipt_number"),
                notes=data.get("notes"),
            )

            db.add(payment)
            await db.flush()

            # update invoice paid / balance / status
            invoice.paid_amount = (invoice.paid_amount or 0.0) + data["amount"]
            invoice.balance_due = max(0.0, invoice.amount - invoice.paid_amount)
            old_status = invoice.status
            if invoice.paid_amount >= invoice.amount:
                invoice.status = PaymentStatusEnum.PAID
            elif 0 < invoice.paid_amount < invoice.amount:
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
            await db.refresh(payment)
            await db.refresh(invoice)
            return payment
        except Exception as e:
            await db.rollback()
            raise e


    async def set_active_financial_year(self, db: AsyncSession, financial_year_id: UUID):
        # Activate the provided financial year and deactivate others for the same institution in one transaction
        from sqlalchemy import update, select
        # fetch fy
        stmt = select(FinancialYear).where(FinancialYear.id == financial_year_id)
        res = await db.execute(stmt)
        fy = res.scalar_one_or_none()
        if not fy:
            raise ValueError("Financial Year not found")
        # Deactivate others
        await db.execute(
            update(FinancialYear)
            .where(FinancialYear.id != financial_year_id)
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
                if amt is None and not it.get("amount_by_year"):
                    raise ValueError("Each item must have 'amount' or 'amount_by_year'")
                if amt is not None and float(amt) < 0:
                    raise ValueError("Item amount must be >= 0")
                aby = it.get("amount_by_year")
                if aby and any(float(v) < 0 for v in aby.values()):
                    raise ValueError("Amounts in 'amount_by_year' must be >= 0")

            fs = FeeStructure(**data)
            db.add(fs)
            await db.flush()
            order_idx = 1
            for it in items:
                db.add(
                    FeeStructureItem(
                        fee_structure_id=fs.id,
                        fee_head_id=it.get("fee_head_id"),
                        fee_sub_head_id=it["fee_sub_head_id"],
                        amount=it.get("amount", 0),
                        amount_by_year=it.get("amount_by_year"),
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


    async def create_demand_batch(self, db: AsyncSession, payload):
        """Create a demand batch (draft)."""
        from common.models.billing.demand import DemandBatch
        data = payload.dict(exclude_unset=True)
        
        # Ensure filters are JSON serializable (convert UUIDs to strings)
        if "filters" in data and isinstance(data["filters"], dict):
            new_filters = {}
            for k, v in data["filters"].items():
                if isinstance(v, UUID):
                    new_filters[k] = str(v)
                else:
                    new_filters[k] = v
            data["filters"] = new_filters

        batch = DemandBatch(**data)
        db.add(batch)
        await db.commit()
        await db.refresh(batch)
        return batch

    async def _students_matching_filters(self, db: AsyncSession, filters: dict | None, institution_id=None):
        """Return list of AdmissionStudent ids matching filters."""
        from common.models.admission.admission_entry import AdmissionStudent
        stmt = select(AdmissionStudent)
        if institution_id:
            stmt = stmt.where(AdmissionStudent.campus == str(institution_id))  # Note: mapping campus to institution
        
        if not filters:
            res = await db.execute(stmt)
            return [s.id for s in res.scalars().all()]

        # Apply dictionary filters
        if filters.get("department"):
            stmt = stmt.where(AdmissionStudent.department.ilike(f"%{filters.get('department')}%"))
        if filters.get("course"):
            stmt = stmt.where(AdmissionStudent.course.ilike(f"%{filters.get('course')}%"))
        if filters.get("batch"):
            # assuming 'year' maps to batch or we need a batch field. Model has 'year'.
            stmt = stmt.where(AdmissionStudent.year.ilike(f"%{filters.get('batch')}%"))
        if filters.get("admission_quota"):
            stmt = stmt.where(AdmissionStudent.admission_quota == filters.get("admission_quota"))
        if filters.get("category"):
            stmt = stmt.where(AdmissionStudent.category == filters.get("category"))
        if filters.get("gender"):
            stmt = stmt.where(AdmissionStudent.gender == filters.get("gender"))
        if filters.get("quota_type"):
            stmt = stmt.where(AdmissionStudent.quota_type.ilike(f"%{filters.get('quota_type')}%"))
        if filters.get("special_quota"):
            stmt = stmt.where(AdmissionStudent.special_quota.ilike(f"%{filters.get('special_quota')}%"))
        if filters.get("scholarships"):
            stmt = stmt.where(AdmissionStudent.scholarships.ilike(f"%{filters.get('scholarships')}%"))
        if filters.get("boarding_place"):
            stmt = stmt.where(AdmissionStudent.boarding_place.ilike(f"%{filters.get('boarding_place')}%"))
        
        # Pydantic model dump handling (if passing schema dict)
        # The service calls this with `batch.filters` which is JSON/dict.

        res = await db.execute(stmt)
        return [s.id for s in res.scalars().all()]

    async def preview_demand_batch(self, db: AsyncSession, payload) -> dict:
        """Preview the demand creation: count students and calculate total."""
        from common.models.admission.admission_entry import AdmissionStudent
        data = payload.dict(exclude_unset=True)
        filters = data.get("filters", {})
        if hasattr(filters, "dict"):
            filters = filters.dict(exclude_unset=True)
        
        student_ids = await self._students_matching_filters(db, filters, data.get("institution_id"))
        
        if not student_ids:
            return {"student_count": 0, "total_amount": 0.0, "message": "No students found matching criteria", "sample_students": []}

        # Calculate amount per student
        stmt = select(FeeStructure).where(FeeStructure.id == data["fee_structure_id"])
        res = await db.execute(stmt)
        fs = res.scalar_one_or_none()
        if not fs:
            raise ValueError("FeeStructure not found")
        
        per_student_total = 0.0
        for it in fs.items:
            if it.amount_by_year:
                per_student_total += sum([float(v) for v in it.amount_by_year.values()])
            else:
                per_student_total += float(it.amount or 0)
        
        total = per_student_total * len(student_ids)

        # Get sample students
        stmt = select(AdmissionStudent).where(AdmissionStudent.id.in_(student_ids[:5]))
        res = await db.execute(stmt)
        samples = []
        for s in res.scalars():
            samples.append({
                "id": str(s.id),
                "name": s.name,
                "course": s.course,
                "department": s.department,
                "admission_quota": s.admission_quota
            })

        return {
            "student_count": len(student_ids),
            "total_amount": total,
            "message": f"Found {len(student_ids)} students. Total estimated demand: {total}",
            "sample_students": samples
        }

    async def generate_demands_for_batch(self, db: AsyncSession, batch_id: UUID, dry_run: bool = False):
        """Generate demands for a batch; if dry_run, return counts and totals only."""
        from common.models.billing.demand import DemandBatch, DemandItem
        stmt = select(DemandBatch).where(DemandBatch.id == batch_id)
        res = await db.execute(stmt)
        batch = res.scalar_one_or_none()
        if not batch:
            raise ValueError("Batch not found")
        # find students
        student_ids = await self._students_matching_filters(db, batch.filters, batch.institution_id)
        if not student_ids:
            return {"count": 0, "total": 0.0}
        # load fee structure
        if not batch.fee_structure_id:
            raise ValueError("Batch does not have a fee_structure_id")
        stmt = select(FeeStructure).where(FeeStructure.id == batch.fee_structure_id)
        res = await db.execute(stmt)
        fs = res.scalar_one_or_none()
        if not fs:
            raise ValueError("FeeStructure not found")
        # calculate total per student
        items = fs.items
        per_student_total = 0.0
        for it in items:
            if it.amount_by_year:
                per_student_total += sum([float(v) for v in it.amount_by_year.values()])
            else:
                per_student_total += float(it.amount or 0)
        total = per_student_total * len(student_ids)
        if dry_run:
            return {"count": len(student_ids), "total": total}
        # create DemandItems
        created = 0
        for sid in student_ids:
            for it in items:
                amt = 0.0
                if it.amount_by_year:
                    amt = sum([float(v) for v in it.amount_by_year.values()])
                else:
                    amt = float(it.amount or 0)
                
                # Build description with fee head and subhead names
                fee_head_name = it.fee_head.name if it.fee_head else "Fee"
                fee_subhead_name = it.fee_sub_head.name if it.fee_sub_head else ""
                
                if fee_subhead_name:
                    description = f"{fee_head_name} - {fee_subhead_name}"
                else:
                    description = fee_head_name
                
                di = DemandItem(
                    batch_id=batch.id,
                    student_id=sid,
                    fee_structure_id=fs.id,
                    fee_structure_item_id=it.id,
                    amount=amt,
                    fee_head_id=it.fee_head_id,
                    description=description,
                )
                db.add(di)
                created += 1
        batch.status = "generated"
        from datetime import datetime
        batch.generated_at = datetime.utcnow()
        await db.commit()
        return {"created": created, "count": len(student_ids), "total": total}

    async def create_student_demand(self, db: AsyncSession, student_id: UUID, fee_structure_id: UUID, items_overrides: list | None = None):
        """Create demand items for a student using a fee structure. Optional overrides is a list of items with amounts."""
        from common.models.billing.demand import DemandItem
        # load structure
        stmt = select(FeeStructure).where(FeeStructure.id == fee_structure_id)
        res = await db.execute(stmt)
        fs = res.scalar_one_or_none()
        if not fs:
            raise ValueError("FeeStructure not found")
        created = []
        if items_overrides:
            for it in items_overrides:
                amt = it.get("amount") or 0
                di = DemandItem(batch_id=None, student_id=student_id, fee_structure_id=fee_structure_id, fee_structure_item_id=it.get("fee_structure_item_id"), amount=amt)
                db.add(di)
                created.append(di)
        else:
            for it in fs.items:
                if it.amount_by_year:
                    amt = sum([float(v) for v in it.amount_by_year.values()])
                else:
                    amt = float(it.amount or 0)
                di = DemandItem(batch_id=None, student_id=student_id, fee_structure_id=fee_structure_id, fee_structure_item_id=it.id, amount=amt)
                db.add(di)
                created.append(di)
        await db.commit()
        return len(created)

    async def create_year_specific_demand(
        self, db: AsyncSession, student_ids: list[UUID], fee_structure_id: UUID, year: str
    ) -> dict:
        """
        Create demand items for multiple students for a specific year only.
        Also creates invoices automatically for each student.
        
        Args:
            db: Database session
            student_ids: List of student UUIDs
            fee_structure_id: Fee structure UUID
            year: Year number as string (e.g., "1", "2", "3")
            
        Returns:
            dict with created_count, total_amount, invoice_count, and message
        """
        from common.models.billing.demand import DemandItem, DemandBatch
        from datetime import datetime
        
        if not student_ids:
            raise ValueError("No students provided")
        
        # Fetch fee structure
        stmt = select(FeeStructure).where(FeeStructure.id == fee_structure_id)
        res = await db.execute(stmt)
        fs = res.scalar_one_or_none()
        if not fs:
            raise ValueError("Fee structure not found")
        
        # Get institution_id from first student for the batch
        from common.models.admission.admission_entry import AdmissionStudent
        stmt = select(AdmissionStudent.institution_id).where(AdmissionStudent.id == student_ids[0])
        res = await db.execute(stmt)
        institution_id = res.scalar_one_or_none()
        if not institution_id:
            raise ValueError("Could not determine institution from students")
        
        # Create a batch for this operation
        batch = DemandBatch(
            name=f"Year {year} Demand - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            institution_id=institution_id,
            fee_structure_id=fee_structure_id,
            status="generated",
            generated_at=datetime.utcnow()
        )
        db.add(batch)
        await db.flush()
        
        created_count = 0
        total_amount = 0.0
        invoice_count = 0
        
        # Create demand items for each student
        for student_id in student_ids:
            student_demands = []
            
            for item in fs.items:
                # Get amount for the specific year
                amount = 0.0
                if item.amount_by_year and year in item.amount_by_year:
                    amount = float(item.amount_by_year[year])
                elif not item.amount_by_year:
                    # If no year breakdown, use the flat amount for Year 1 only
                    if year == "1":
                        amount = float(item.amount or 0)
                
                # Only create demand if amount > 0
                if amount > 0:
                    # Build descriptive name: "Fee Head - Fee Subhead (Year X)"
                    fee_head_name = item.fee_head.name if item.fee_head else "Fee"
                    fee_subhead_name = item.fee_sub_head.name if item.fee_sub_head else ""
                    
                    if fee_subhead_name:
                        description = f"{fee_head_name} - {fee_subhead_name} (Year {year})"
                    else:
                        description = f"{fee_head_name} (Year {year})"
                    
                    demand_item = DemandItem(
                        batch_id=batch.id,
                        student_id=student_id,
                        fee_structure_id=fee_structure_id,
                        fee_structure_item_id=item.id,
                        amount=amount,
                        fee_head_id=item.fee_head_id,
                        description=description
                    )
                    db.add(demand_item)
                    student_demands.append(demand_item)
                    created_count += 1
                    total_amount += amount
            
            # Create invoice for this student's demands
            if student_demands:
                await db.flush()  # Flush to get demand IDs
                invoice = await self.create_invoice_from_demands(db, student_demands)
                if invoice:
                    invoice_count += 1
        
        await db.commit()
        
        return {
            "created_count": created_count,
            "total_amount": total_amount,
            "invoice_count": invoice_count,
            "message": f"Created {created_count} demand items and {invoice_count} invoices for {len(student_ids)} student(s) for Year {year}"
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
                stmt = stmt.where(HostelFeeStructure.college_id == filters.get("college_id"))
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
                stmt = stmt.where(TransportFeeStructure.college_id == filters.get("college_id"))
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
            stmt = stmt.where(TransportRoute.college_id == college_id)
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
        from common.models.billing.application_fees import ApplicationTransaction, PaymentStatusEnum
        from common.models.master.annual_task import AcademicYearCourse
        import uuid
        
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
        from common.models.admission.admission_entry import AdmissionStudent
        from common.models.billing.application_fees import Invoice, PaymentStatusEnum
        
        # 1. Find Student
        # We search by application_number OR enquiry_number to be safe? 
        # Request asked for application_number.
        stmt = select(AdmissionStudent).options(
            selectinload(AdmissionStudent.department),
            selectinload(AdmissionStudent.course)
        ).where(AdmissionStudent.application_number == application_number)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()
        
        if not student:
            # Fallback try enquiry_number just in case
             stmt = select(AdmissionStudent).options(
                selectinload(AdmissionStudent.department),
                selectinload(AdmissionStudent.course)
             ).where(AdmissionStudent.enquiry_number == application_number)
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
        return {
            "student_id": student.id,

            "application_number": student.application_number,
            "name": student.name,
            "department": student.department.name if student.department else None,
            "course": student.course.title if student.course else None,
            "batch": student.year,
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
        self, db: AsyncSession, student_ids: list[UUID], fee_structure_id: UUID, year: str
    ) -> dict[str, bool]:
        """
        Check if demands exist for the given students, fee structure, and year.
        Returns a dict mapping student_id (str) -> bool (True if demand exists).
        """
        from common.models.billing.demand import DemandItem
        
        if not student_ids:
            return {}
            
        # Check for any demand item matching the fee structure and year description pattern
        # This assumes the description format "(Year X)" is consistently used for year-specific demands
        stmt = select(DemandItem.student_id).where(
            DemandItem.student_id.in_(student_ids),
            DemandItem.fee_structure_id == fee_structure_id,
            DemandItem.description.ilike(f"%(Year {year})")
        ).distinct()
        
        res = await db.execute(stmt)
        existing_student_ids = {str(uid) for uid in res.scalars().all()}
        
        # Return status for requested students
        return {str(sid): (str(sid) in existing_student_ids) for sid in student_ids}

billing_service = BillingService()
