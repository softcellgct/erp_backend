import csv
import math
from datetime import date, datetime, time, timezone
from io import StringIO
from uuid import UUID

from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from common.models.gate.visitor_model import (
    AdmissionVisitor,
    ConsultancyReference,
    OtherReference,
    ReferenceType,
    StaffReference,
    StudentReference,
    VisitStatus,
)
from common.models.master.institution import Institution
from common.schemas.gate.admission_visitor import (
    AdmissionVisitorCreate,
    AdmissionVisitorPassOutRequest,
    AdmissionVisitorReportSummary,
    AdmissionVisitorUpdate,
)


class AdmissionVisitorCRUD:
    async def create(self, db: AsyncSession, payload: AdmissionVisitorCreate):
        try:
            data = payload.dict(exclude_unset=True)
            ref_type_raw = data.pop("reference_type")

            if isinstance(ref_type_raw, str):
                try:
                    try:
                        ref_type = ReferenceType[ref_type_raw.upper()]
                    except KeyError:
                        ref_type = ReferenceType(ref_type_raw)
                except Exception as exc:
                    raise ValueError(f"Invalid reference_type: {ref_type_raw}") from exc
            else:
                ref_type = ref_type_raw

            if "gate_pass_no" not in data or not data["gate_pass_no"]:
                data["gate_pass_no"] = await self._generate_unique_gate_pass_no(db)

            consultancy = data.pop("consultancy_reference", None)
            staff = data.pop("staff_reference", None)
            student = data.pop("student_reference", None)
            other = data.pop("other_reference", None)

            visitor = AdmissionVisitor(**data, reference_type=ref_type)
            db.add(visitor)
            await db.flush()

            match ref_type:
                case ReferenceType.CONSULTANCY if consultancy:
                    db.add(
                        ConsultancyReference(admission_visitor_id=visitor.id, **consultancy)
                    )
                case ReferenceType.STAFF if staff:
                    db.add(StaffReference(reference_id=visitor.id, **staff))
                case ReferenceType.STUDENT if student:
                    db.add(StudentReference(reference_id=visitor.id, **student))
                case ReferenceType.OTHER if other:
                    db.add(OtherReference(reference_id=visitor.id, **other))

            await db.commit()

            stmt = (
                select(AdmissionVisitor)
                .where(AdmissionVisitor.id == visitor.id)
                .options(
                    selectinload(AdmissionVisitor.consultancy_reference),
                    selectinload(AdmissionVisitor.staff_reference),
                    selectinload(AdmissionVisitor.student_reference),
                    selectinload(AdmissionVisitor.other_reference),
                )
            )
            result = await db.execute(stmt)
            return result.scalar_one()
        except Exception:
            await db.rollback()
            raise

    async def _generate_unique_gate_pass_no(self, db: AsyncSession) -> str:
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")
        prefix = f"{date_str}/"

        result = await db.execute(
            text(
                "SELECT gate_pass_no FROM admission_visitors "
                "WHERE gate_pass_no LIKE :prefix "
                "ORDER BY CAST(SUBSTRING(gate_pass_no FROM 10) AS INTEGER) DESC LIMIT 1"
            ),
            {"prefix": f"{prefix}%"},
        )
        last_gate_pass = result.scalar_one_or_none()

        if not last_gate_pass:
            next_num = 1
        else:
            try:
                next_num = int(last_gate_pass.split("/")[-1]) + 1
            except (IndexError, ValueError):
                next_num = 1

        return f"{prefix}{next_num:03d}"

    async def get_one(self, db: AsyncSession, visitor_id: UUID):
        stmt = (
            select(AdmissionVisitor)
            .where(
                AdmissionVisitor.id == visitor_id,
                AdmissionVisitor.deleted_at.is_(None),
            )
            .options(
                joinedload(AdmissionVisitor.consultancy_reference),
                joinedload(AdmissionVisitor.staff_reference),
                joinedload(AdmissionVisitor.student_reference),
                joinedload(AdmissionVisitor.other_reference),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_gate_pass_no(self, db: AsyncSession, gate_pass_no: str):
        normalized_gate_pass_no = gate_pass_no.strip()
        stmt = (
            select(AdmissionVisitor)
            .where(
                AdmissionVisitor.gate_pass_no == normalized_gate_pass_no,
                AdmissionVisitor.deleted_at.is_(None),
            )
            .options(
                joinedload(AdmissionVisitor.consultancy_reference),
                joinedload(AdmissionVisitor.staff_reference),
                joinedload(AdmissionVisitor.student_reference),
                joinedload(AdmissionVisitor.other_reference),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_all(self, db: AsyncSession, query):
        return await paginate(db, query)

    async def update(
        self, db: AsyncSession, visitor_id: UUID, payload: AdmissionVisitorUpdate
    ):
        visitor = await db.get(AdmissionVisitor, visitor_id)
        if not visitor:
            return None

        for field, value in payload.dict(exclude_unset=True).items():
            setattr(visitor, field, value)

        await db.commit()
        await db.refresh(visitor)
        return visitor

    async def delete(self, db: AsyncSession, visitor_id: UUID):
        visitor = await db.get(AdmissionVisitor, visitor_id)
        if not visitor:
            return 0
        await db.delete(visitor)
        await db.commit()
        return 1

    async def pass_out(
        self,
        db: AsyncSession,
        visitor_id: UUID,
        payload: AdmissionVisitorPassOutRequest,
    ):
        visitor = await self.get_one(db, visitor_id)
        if not visitor:
            return None, False

        if visitor.visit_status == VisitStatus.CHECKED_OUT:
            return visitor, True

        check_out_time = payload.check_out_time or datetime.now(timezone.utc)
        if self._to_naive_utc(check_out_time) < self._to_naive_utc(visitor.check_in_time):
            raise ValueError("check_out_time cannot be earlier than check_in_time")

        visitor.visit_status = VisitStatus.CHECKED_OUT
        visitor.check_out_time = check_out_time
        visitor.check_out_remarks = (payload.remarks or "").strip() or None
        db.add(visitor)
        await db.commit()
        await db.refresh(visitor)
        return visitor, False

    async def get_report(
        self,
        db: AsyncSession,
        *,
        date_from: date | None,
        date_to: date | None,
        visit_status: VisitStatus | None,
        institution_id: UUID | None,
        reference_type: str | None,
        search: str | None,
        page: int,
        size: int,
    ):
        filters = self._build_filters(
            date_from=date_from,
            date_to=date_to,
            visit_status=visit_status,
            institution_id=institution_id,
            reference_type=reference_type,
            search=search,
            for_items=True,
        )
        total = await self._get_count(db, filters)

        stmt = (
            select(
                AdmissionVisitor,
                Institution.name.label("institution_name"),
            )
            .select_from(AdmissionVisitor)
            .join(Institution, Institution.id == AdmissionVisitor.institution_id, isouter=True)
            .where(*filters)
            .order_by(
                AdmissionVisitor.check_in_time.desc(),
                AdmissionVisitor.created_at.desc(),
            )
            .offset((page - 1) * size)
            .limit(size)
        )
        rows = (await db.execute(stmt)).all()
        items = [self._row_to_report_item(row) for row in rows]

        summary = await self._get_report_summary(
            db,
            date_from=date_from,
            date_to=date_to,
            visit_status=visit_status,
            institution_id=institution_id,
            reference_type=reference_type,
            search=search,
        )

        pages = math.ceil(total / size) if size else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
            "summary": summary.model_dump()
            if hasattr(summary, "model_dump")
            else summary.dict(),
        }

    async def export_report_csv(
        self,
        db: AsyncSession,
        *,
        date_from: date | None,
        date_to: date | None,
        visit_status: VisitStatus | None,
        institution_id: UUID | None,
        reference_type: str | None,
        search: str | None,
    ):
        filters = self._build_filters(
            date_from=date_from,
            date_to=date_to,
            visit_status=visit_status,
            institution_id=institution_id,
            reference_type=reference_type,
            search=search,
            for_items=True,
        )

        stmt = (
            select(
                AdmissionVisitor,
                Institution.name.label("institution_name"),
            )
            .select_from(AdmissionVisitor)
            .join(Institution, Institution.id == AdmissionVisitor.institution_id, isouter=True)
            .where(*filters)
            .order_by(
                AdmissionVisitor.check_in_time.desc(),
                AdmissionVisitor.created_at.desc(),
            )
        )
        rows = (await db.execute(stmt)).all()
        report_rows = [self._row_to_report_item(row) for row in rows]

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "gate_pass_no",
                "student_name",
                "mobile_number",
                "parent_or_guardian_name",
                "native_place",
                "institution_name",
                "reference_type",
                "visit_status",
                "check_in_time",
                "check_out_time",
                "check_out_remarks",
            ]
        )
        for item in report_rows:
            writer.writerow(
                [
                    item["gate_pass_no"],
                    item["student_name"],
                    item["mobile_number"],
                    item["parent_or_guardian_name"] or "",
                    item["native_place"],
                    item["institution_name"] or "",
                    item["reference_type"],
                    item["visit_status"],
                    item["check_in_time"] or "",
                    item["check_out_time"] or "",
                    item["check_out_remarks"] or "",
                ]
            )

        date_tag = datetime.now().strftime("%Y%m%d")
        filename = f"admission_visitor_reports_{date_tag}.csv"
        return output.getvalue(), filename

    async def _get_report_summary(
        self,
        db: AsyncSession,
        *,
        date_from: date | None,
        date_to: date | None,
        visit_status: VisitStatus | None,
        institution_id: UUID | None,
        reference_type: str | None,
        search: str | None,
    ) -> AdmissionVisitorReportSummary:
        common_filters = self._build_filters(
            date_from=None,
            date_to=None,
            visit_status=visit_status,
            institution_id=institution_id,
            reference_type=reference_type,
            search=search,
            for_items=False,
        )

        entries_filters = list(common_filters)
        entries_filters.extend(self._time_range_filters(AdmissionVisitor.check_in_time, date_from, date_to))
        total_entries = await self._get_count(db, entries_filters)

        exits_filters = list(common_filters)
        exits_filters.append(AdmissionVisitor.check_out_time.is_not(None))
        exits_filters.extend(self._time_range_filters(AdmissionVisitor.check_out_time, date_from, date_to))
        total_exits = await self._get_count(db, exits_filters)

        inside_filters = list(common_filters)
        inside_filters.append(AdmissionVisitor.visit_status == VisitStatus.CHECKED_IN)
        inside_campus = await self._get_count(db, inside_filters)

        return AdmissionVisitorReportSummary(
            total_entries=total_entries,
            total_exits=total_exits,
            inside_campus=inside_campus,
        )

    def _build_filters(
        self,
        *,
        date_from: date | None,
        date_to: date | None,
        visit_status: VisitStatus | None,
        institution_id: UUID | None,
        reference_type: str | None,
        search: str | None,
        for_items: bool,
    ):
        filters = [AdmissionVisitor.deleted_at.is_(None)]

        if visit_status:
            filters.append(AdmissionVisitor.visit_status == visit_status)

        if institution_id:
            filters.append(AdmissionVisitor.institution_id == institution_id)

        if reference_type:
            filters.append(AdmissionVisitor.reference_type == reference_type)

        if search:
            like = f"%{search.strip()}%"
            filters.append(
                or_(
                    AdmissionVisitor.gate_pass_no.ilike(like),
                    AdmissionVisitor.student_name.ilike(like),
                    AdmissionVisitor.mobile_number.ilike(like),
                    AdmissionVisitor.parent_or_guardian_name.ilike(like),
                    AdmissionVisitor.native_place.ilike(like),
                )
            )

        if for_items and (date_from or date_to):
            in_range_in = and_(
                *self._time_range_filters(AdmissionVisitor.check_in_time, date_from, date_to)
            )
            in_range_out = and_(
                *self._time_range_filters(AdmissionVisitor.check_out_time, date_from, date_to)
            )
            filters.append(or_(in_range_in, in_range_out))

        return filters

    def _time_range_filters(self, column, date_from: date | None, date_to: date | None):
        filters = []
        if date_from:
            filters.append(column >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
        if date_to:
            filters.append(column <= datetime.combine(date_to, time.max, tzinfo=timezone.utc))
        return filters

    async def _get_count(self, db: AsyncSession, filters):
        stmt = select(func.count()).select_from(AdmissionVisitor).where(*filters)
        result = await db.execute(stmt)
        return result.scalar_one() or 0

    def _row_to_report_item(self, row):
        visitor = row[0]
        institution_name = row[1]
        return {
            "id": visitor.id,
            "gate_pass_no": visitor.gate_pass_no,
            "student_name": visitor.student_name,
            "mobile_number": visitor.mobile_number,
            "parent_or_guardian_name": visitor.parent_or_guardian_name,
            "native_place": visitor.native_place,
            "institution_id": visitor.institution_id,
            "institution_name": institution_name,
            "reference_type": visitor.reference_type.value
            if hasattr(visitor.reference_type, "value")
            else str(visitor.reference_type),
            "visit_status": visitor.visit_status.value
            if hasattr(visitor.visit_status, "value")
            else str(visitor.visit_status),
            "check_in_time": visitor.check_in_time.isoformat() if visitor.check_in_time else None,
            "check_out_time": visitor.check_out_time.isoformat() if visitor.check_out_time else None,
            "check_out_remarks": visitor.check_out_remarks,
            "created_at": visitor.created_at.isoformat() if visitor.created_at else None,
            "updated_at": visitor.updated_at.isoformat() if visitor.updated_at else None,
        }

    def _to_naive_utc(self, value: datetime | None):
        if value is None:
            return datetime.min
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)


admission_crud = AdmissionVisitorCRUD()
