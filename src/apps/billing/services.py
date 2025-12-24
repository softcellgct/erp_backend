from uuid import UUID
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

    async def apply_payment(self, db: AsyncSession, invoice_id: UUID, payload: PaymentCreate):
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
        batch = DemandBatch(**data)
        db.add(batch)
        await db.commit()
        await db.refresh(batch)
        return batch

    async def _students_matching_filters(self, db: AsyncSession, filters: dict | None, institution_id=None):
        """Return list of AdmissionStudent ids matching simple filters."""
        from common.models.admission.admission_entry import AdmissionStudent
        stmt = select(AdmissionStudent)
        if institution_id:
            stmt = stmt.where(AdmissionStudent.campus == institution_id)
        if not filters:
            res = await db.execute(stmt)
            return [s.id for s in res.scalars().all()]
        # apply known filters
        if filters.get("department"):
            stmt = stmt.where(AdmissionStudent.department == filters.get("department"))
        if filters.get("course"):
            stmt = stmt.where(AdmissionStudent.course == filters.get("course"))
        if filters.get("year"):
            stmt = stmt.where(AdmissionStudent.year == filters.get("year"))
        res = await db.execute(stmt)
        return [s.id for s in res.scalars().all()]

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
                di = DemandItem(
                    batch_id=batch.id,
                    student_id=sid,
                    fee_structure_id=fs.id,
                    fee_structure_item_id=it.id,
                    amount=amt,
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


billing_service = BillingService()
