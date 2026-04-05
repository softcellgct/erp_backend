import csv
import json
import math
from datetime import date, datetime, time, timezone
from io import StringIO
from uuid import UUID

from fastapi import HTTPException
from fastapi_pagination import Params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_, asc, desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from common.models.admission.admission_entry import AdmissionGateEntry, AdmissionStatusEnum, VisitStatusEnum
from common.models.gate.visitor_model import (
    ConsultancyReference,
    OtherReference,
    ReferenceType,
    StaffReference,
    StudentReference,
)
from common.models.master.institution import Institution
from common.schemas.gate.admission_visitor import (
    AdmissionVisitorCreate,
    AdmissionVisitorPassOutRequest,
    AdmissionVisitorReportSummary,
    AdmissionVisitorUpdate,
)

# Maps incoming payload field names to AdmissionGateEntry column names
_FIELD_MAP = {
    "gate_pass_no": "gate_pass_number",
}


class AdmissionVisitorCRUD:
    @staticmethod
    def _to_model_field(field_name: str) -> str:
        return _FIELD_MAP.get(field_name, field_name)

    @staticmethod
    def _normalize_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return value

    def _build_filter_expression(self, field_name: str, operator: str, value):
        model_field_name = self._to_model_field(field_name)
        column = getattr(AdmissionGateEntry, model_field_name, None)
        if column is None:
            return None

        op = (operator or "eq").strip().lower()
        normalized_value = self._normalize_bool(value)

        if op in {"eq", "$eq"}:
            return column == normalized_value
        if op in {"ne", "$ne"}:
            return column != normalized_value
        if op in {"contains", "$contains"} and isinstance(value, str):
            return column.ilike(f"%{value}%")
        if op in {"startswith", "$startswith"} and isinstance(value, str):
            return column.ilike(f"{value}%")
        if op in {"endswith", "$endswith"} and isinstance(value, str):
            return column.ilike(f"%{value}")
        if op in {"in", "$in"} and isinstance(value, list):
            values = [self._normalize_bool(v) for v in value]
            return column.in_(values)

        return None

    def _apply_filters(self, stmt, filters_raw: str | None):
        if not filters_raw:
            return stmt

        try:
            parsed = json.loads(filters_raw) if isinstance(filters_raw, str) else filters_raw
        except Exception:
            return stmt

        expressions = []

        if isinstance(parsed, dict) and isinstance(parsed.get("conditions"), list):
            for condition in parsed["conditions"]:
                if not isinstance(condition, dict):
                    continue
                expr = self._build_filter_expression(
                    condition.get("field", ""),
                    condition.get("operator", "eq"),
                    condition.get("value"),
                )
                if expr is not None:
                    expressions.append(expr)

        elif isinstance(parsed, dict):
            for field, value in parsed.items():
                if isinstance(value, dict):
                    for op_key, op_val in value.items():
                        expr = self._build_filter_expression(field, op_key, op_val)
                        if expr is not None:
                            expressions.append(expr)
                else:
                    expr = self._build_filter_expression(field, "eq", value)
                    if expr is not None:
                        expressions.append(expr)

        if expressions:
            stmt = stmt.where(and_(*expressions))

        return stmt

    async def get_all_filtered(
        self,
        db: AsyncSession,
        page: int = 1,
        size: int = 50,
        search: str | None = None,
        sort: str = "created_at:desc",
        filters: str | None = None,
    ):
        stmt = (
            select(AdmissionGateEntry)
            .options(
                selectinload(AdmissionGateEntry.consultancy_reference),
                selectinload(AdmissionGateEntry.staff_reference),
                selectinload(AdmissionGateEntry.student_reference),
                selectinload(AdmissionGateEntry.other_reference),
            )
            .where(AdmissionGateEntry.deleted_at.is_(None))
        )

        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    AdmissionGateEntry.gate_pass_number.ilike(pattern),
                    AdmissionGateEntry.enquiry_number.ilike(pattern),
                    AdmissionGateEntry.student_name.ilike(pattern),
                    AdmissionGateEntry.parent_or_guardian_name.ilike(pattern),
                    AdmissionGateEntry.mobile_number.ilike(pattern),
                    AdmissionGateEntry.aadhar_number.ilike(pattern),
                    AdmissionGateEntry.reference_type.ilike(pattern),
                    AdmissionGateEntry.vehicle_number.ilike(pattern),
                )
            )

        stmt = self._apply_filters(stmt, filters)

        sort_field = "created_at"
        sort_dir = "desc"
        if isinstance(sort, str) and ":" in sort:
            raw_field, raw_dir = sort.split(":", 1)
            sort_field = (raw_field or "created_at").strip()
            sort_dir = (raw_dir or "desc").strip().lower()

        sort_column = getattr(AdmissionGateEntry, sort_field, None)
        if sort_column is None:
            sort_column = AdmissionGateEntry.created_at

        stmt = stmt.order_by(
            asc(sort_column) if sort_dir == "asc" else desc(sort_column),
            desc(AdmissionGateEntry.id),
        )

        return await paginate(db, stmt, Params(page=page, size=size))

    async def create(self, db: AsyncSession, payload: AdmissionVisitorCreate):
        try:
            data = payload.dict(exclude_unset=True)
            ref_type_raw = data.pop("reference_type", None)

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

            for old_key, new_key in _FIELD_MAP.items():
                if old_key in data:
                    data[new_key] = data.pop(old_key)

            aadhar_val = data.get("aadhar_number")
            if aadhar_val:
                dup_stmt = select(AdmissionGateEntry.id).where(
                    AdmissionGateEntry.aadhar_number == aadhar_val,
                    AdmissionGateEntry.deleted_at.is_(None),
                )
                dup_res = await db.execute(dup_stmt)
                if dup_res.scalar_one_or_none():
                    raise HTTPException(
                        status_code=409,
                        detail=f"Aadhar number {aadhar_val} already exists",
                    )

            if not data.get("gate_pass_number"):
                data["gate_pass_number"] = await self._generate_unique_gate_pass_no(db)

            from apps.admission.services import generate_enquiry_number

            data["enquiry_number"] = await generate_enquiry_number(db, data.get("institution_id"))

            consultancy = data.pop("consultancy_reference", None)
            staff = data.pop("staff_reference", None)
            student_ref = data.pop("student_reference", None)
            other = data.pop("other_reference", None)

            data["status"] = AdmissionStatusEnum.ENQUIRY
            data["visit_status"] = VisitStatusEnum.CHECKED_IN
            data["reference_type"] = ref_type.value if ref_type else None

            gate_entry = AdmissionGateEntry(**data)
            gate_entry.check_in_time = func.now()
            db.add(gate_entry)
            await db.flush()

            match ref_type:
                case ReferenceType.CONSULTANCY if consultancy:
                    db.add(
                        ConsultancyReference(gate_entry_id=gate_entry.id, **consultancy)
                    )
                case ReferenceType.STAFF if staff:
                    db.add(StaffReference(gate_entry_id=gate_entry.id, **staff))
                case ReferenceType.STUDENT if student_ref:
                    db.add(StudentReference(gate_entry_id=gate_entry.id, **student_ref))
                case ReferenceType.OTHER if other:
                    db.add(OtherReference(gate_entry_id=gate_entry.id, **other))

            await db.commit()

            stmt = (
                select(AdmissionGateEntry)
                .where(AdmissionGateEntry.id == gate_entry.id)
                .options(
                    selectinload(AdmissionGateEntry.consultancy_reference),
                    selectinload(AdmissionGateEntry.staff_reference),
                    selectinload(AdmissionGateEntry.student_reference),
                    selectinload(AdmissionGateEntry.other_reference),
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
                "SELECT gate_pass_number FROM admission_gate_entries "
                "WHERE gate_pass_number LIKE :prefix "
                "ORDER BY CAST(SUBSTRING(gate_pass_number FROM 10) AS INTEGER) DESC LIMIT 1"
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
            select(AdmissionGateEntry)
            .where(
                AdmissionGateEntry.id == visitor_id,
                AdmissionGateEntry.deleted_at.is_(None),
            )
            .options(
                joinedload(AdmissionGateEntry.consultancy_reference),
                joinedload(AdmissionGateEntry.staff_reference),
                joinedload(AdmissionGateEntry.student_reference),
                joinedload(AdmissionGateEntry.other_reference),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_gate_pass_no(self, db: AsyncSession, gate_pass_no: str):
        normalized = gate_pass_no.strip()
        stmt = (
            select(AdmissionGateEntry)
            .where(
                AdmissionGateEntry.gate_pass_number == normalized,
                AdmissionGateEntry.deleted_at.is_(None),
            )
            .options(
                joinedload(AdmissionGateEntry.consultancy_reference),
                joinedload(AdmissionGateEntry.staff_reference),
                joinedload(AdmissionGateEntry.student_reference),
                joinedload(AdmissionGateEntry.other_reference),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_all(self, db: AsyncSession, query):
        has_joins = bool(getattr(query, "_setup_joins", None))
        pk = getattr(AdmissionGateEntry, "id", None)
        if has_joins and pk is not None:
            query = query.distinct(pk)
            try:
                existing_order_by = getattr(query, "_order_by_clause", None)
                if existing_order_by is not None and len(existing_order_by) > 0:
                    query = query.order_by(None)
                    query = query.order_by(pk, *list(existing_order_by))
                else:
                    query = query.order_by(pk)
            except Exception:
                pass
        elif has_joins:
            query = query.distinct()

        return await paginate(db, query)

    async def update(
        self, db: AsyncSession, visitor_id: UUID, payload: AdmissionVisitorUpdate
    ):
        gate_entry = await db.get(AdmissionGateEntry, visitor_id)
        if not gate_entry:
            return None

        update_data = payload.dict(exclude_unset=True)
        for old_key, new_key in _FIELD_MAP.items():
            if old_key in update_data:
                update_data[new_key] = update_data.pop(old_key)

        if update_data.get("aadhar_number"):
            aadhar_val = update_data["aadhar_number"]
            dup_stmt = select(AdmissionGateEntry.id).where(
                AdmissionGateEntry.aadhar_number == aadhar_val,
                AdmissionGateEntry.id != visitor_id,
            )
            dup_res = await db.execute(dup_stmt)
            if dup_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=409,
                    detail=f"Aadhar number {aadhar_val} already exists",
                )

        for field, value in update_data.items():
            if hasattr(gate_entry, field):
                setattr(gate_entry, field, value)

        try:
            await db.commit()
            await db.refresh(gate_entry)
        except Exception as exc:
            await db.rollback()
            exc_str = str(exc).lower()
            if "unique" in exc_str or "duplicate" in exc_str or "aadhar" in exc_str:
                raise HTTPException(
                    status_code=409,
                    detail=f"Aadhar number {update_data.get('aadhar_number', '')} already exists",
                )
            raise

        return gate_entry

    async def delete(self, db: AsyncSession, visitor_id: UUID):
        gate_entry = await db.get(AdmissionGateEntry, visitor_id)
        if not gate_entry:
            return 0
        await db.delete(gate_entry)
        await db.commit()
        return 1

    async def pass_out(
        self,
        db: AsyncSession,
        visitor_id: UUID,
        payload: AdmissionVisitorPassOutRequest,
    ):
        gate_entry = await self.get_one(db, visitor_id)
        if not gate_entry:
            return None, False

        if gate_entry.visit_status == VisitStatusEnum.CHECKED_OUT:
            return gate_entry, True

        check_out_time = payload.check_out_time or datetime.now(timezone.utc)
        if gate_entry.check_in_time and self._to_naive_utc(check_out_time) < self._to_naive_utc(gate_entry.check_in_time):
            raise ValueError("check_out_time cannot be earlier than check_in_time")

        gate_entry.visit_status = VisitStatusEnum.CHECKED_OUT
        gate_entry.check_out_time = check_out_time
        gate_entry.check_out_remarks = (payload.remarks or "").strip() or None
        db.add(gate_entry)
        await db.commit()
        await db.refresh(gate_entry)
        return gate_entry, False

    async def get_report(
        self,
        db: AsyncSession,
        *,
        date_from: date | None,
        date_to: date | None,
        visit_status: VisitStatusEnum | None,
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
                AdmissionGateEntry,
                Institution.name.label("institution_name"),
            )
            .select_from(AdmissionGateEntry)
            .join(Institution, Institution.id == AdmissionGateEntry.institution_id, isouter=True)
            .where(*filters)
            .order_by(
                AdmissionGateEntry.check_in_time.desc(),
                AdmissionGateEntry.created_at.desc(),
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
        visit_status: VisitStatusEnum | None,
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
                AdmissionGateEntry,
                Institution.name.label("institution_name"),
            )
            .select_from(AdmissionGateEntry)
            .join(Institution, Institution.id == AdmissionGateEntry.institution_id, isouter=True)
            .where(*filters)
            .order_by(
                AdmissionGateEntry.check_in_time.desc(),
                AdmissionGateEntry.created_at.desc(),
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
        visit_status: VisitStatusEnum | None,
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
        entries_filters.extend(self._time_range_filters(AdmissionGateEntry.check_in_time, date_from, date_to))
        total_entries = await self._get_count(db, entries_filters)

        exits_filters = list(common_filters)
        exits_filters.append(AdmissionGateEntry.check_out_time.is_not(None))
        exits_filters.extend(self._time_range_filters(AdmissionGateEntry.check_out_time, date_from, date_to))
        total_exits = await self._get_count(db, exits_filters)

        inside_filters = list(common_filters)
        inside_filters.append(AdmissionGateEntry.visit_status == VisitStatusEnum.CHECKED_IN)
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
        visit_status: VisitStatusEnum | None,
        institution_id: UUID | None,
        reference_type: str | None,
        search: str | None,
        for_items: bool,
    ):
        filters = [
            AdmissionGateEntry.deleted_at.is_(None),
        ]

        if visit_status:
            filters.append(AdmissionGateEntry.visit_status == visit_status)

        if institution_id:
            filters.append(AdmissionGateEntry.institution_id == institution_id)

        if reference_type:
            filters.append(AdmissionGateEntry.reference_type == reference_type)

        if search:
            like = f"%{search.strip()}%"
            filters.append(
                or_(
                    AdmissionGateEntry.gate_pass_number.ilike(like),
                    AdmissionGateEntry.student_name.ilike(like),
                    AdmissionGateEntry.mobile_number.ilike(like),
                    AdmissionGateEntry.parent_or_guardian_name.ilike(like),
                    AdmissionGateEntry.native_place.ilike(like),
                )
            )

        if for_items and (date_from or date_to):
            in_range_in = and_(
                *self._time_range_filters(AdmissionGateEntry.check_in_time, date_from, date_to)
            )
            in_range_out = and_(
                *self._time_range_filters(AdmissionGateEntry.check_out_time, date_from, date_to)
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
        stmt = select(func.count()).select_from(AdmissionGateEntry).where(*filters)
        result = await db.execute(stmt)
        return result.scalar_one() or 0

    def _row_to_report_item(self, row):
        gate_entry = row[0]
        institution_name = row[1]
        return {
            "id": gate_entry.id,
            "gate_pass_no": gate_entry.gate_pass_number,
            "student_name": gate_entry.student_name,
            "mobile_number": gate_entry.mobile_number,
            "parent_or_guardian_name": gate_entry.parent_or_guardian_name,
            "native_place": gate_entry.native_place,
            "institution_id": gate_entry.institution_id,
            "institution_name": institution_name,
            "reference_type": str(gate_entry.reference_type) if gate_entry.reference_type else None,
            "visit_status": gate_entry.visit_status.value
            if hasattr(gate_entry.visit_status, "value")
            else str(gate_entry.visit_status),
            "check_in_time": gate_entry.check_in_time.isoformat() if gate_entry.check_in_time else None,
            "check_out_time": gate_entry.check_out_time.isoformat() if gate_entry.check_out_time else None,
            "check_out_remarks": gate_entry.check_out_remarks,
            "created_at": gate_entry.created_at.isoformat() if gate_entry.created_at else None,
            "updated_at": gate_entry.updated_at.isoformat() if gate_entry.updated_at else None,
            "vehicle": gate_entry.vehicle,
            "vehicle_number": gate_entry.vehicle_number,
        }

    def _to_naive_utc(self, value: datetime | None):
        if value is None:
            return datetime.min
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)


admission_crud = AdmissionVisitorCRUD()
