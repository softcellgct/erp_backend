import csv
import json
import math
from datetime import date, datetime, time, timezone
from io import StringIO
from uuid import UUID

from fastapi_pagination import Params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_, asc, desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from common.models.admission.admission_entry import (
    AdmissionStudent,
    AdmissionStatusEnum,
    SourceEnum,
    VisitStatusEnum,
)
from fastapi import HTTPException
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

# Maps incoming payload field names to AdmissionStudent column names
_FIELD_MAP = {
    "student_name": "name",
    "mobile_number": "student_mobile",
    "parent_or_guardian_name": "father_name",
    "aadhar_number": "aadhaar_number",
    "vehicle": "has_vehicle",
    "gate_pass_no": "gate_pass_number",
}


class AdmissionVisitorCRUD:
    @staticmethod
    def _to_model_field(field_name: str) -> str:
        field_map = {
            "gate_pass_no": "gate_pass_number",
            "student_name": "name",
            "mobile_number": "student_mobile",
            "parent_or_guardian_name": "father_name",
            "aadhar_number": "aadhaar_number",
            "vehicle": "has_vehicle",
        }
        return field_map.get(field_name, field_name)

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
        column = getattr(AdmissionStudent, model_field_name, None)
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

        # Supports querybuilder shape: {"operator":"and","conditions":[...]}
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

        # Supports simple shape: {"field": value}
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
            select(AdmissionStudent)
            .options(
                selectinload(AdmissionStudent.consultancy_reference),
                selectinload(AdmissionStudent.staff_reference),
                selectinload(AdmissionStudent.student_reference),
                selectinload(AdmissionStudent.other_reference),
            )
            .where(
                AdmissionStudent.deleted_at.is_(None),
                AdmissionStudent.source == SourceEnum.GATE_ENQUIRY,
            )
        )

        if search and search.strip():
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    AdmissionStudent.gate_pass_number.ilike(pattern),
                    AdmissionStudent.enquiry_number.ilike(pattern),
                    AdmissionStudent.application_number.ilike(pattern),
                    AdmissionStudent.name.ilike(pattern),
                    AdmissionStudent.father_name.ilike(pattern),
                    AdmissionStudent.student_mobile.ilike(pattern),
                    AdmissionStudent.parent_mobile.ilike(pattern),
                    AdmissionStudent.aadhaar_number.ilike(pattern),
                    AdmissionStudent.reference_type.ilike(pattern),
                    AdmissionStudent.vehicle_number.ilike(pattern),
                )
            )

        stmt = self._apply_filters(stmt, filters)

        sort_field = "created_at"
        sort_dir = "desc"
        if isinstance(sort, str) and ":" in sort:
            raw_field, raw_dir = sort.split(":", 1)
            sort_field = (raw_field or "created_at").strip()
            sort_dir = (raw_dir or "desc").strip().lower()

        sort_column = getattr(AdmissionStudent, sort_field, None)
        if sort_column is None:
            sort_column = AdmissionStudent.created_at

        stmt = stmt.order_by(
            asc(sort_column) if sort_dir == "asc" else desc(sort_column),
            desc(AdmissionStudent.id),
        )

        return await paginate(db, stmt, Params(page=page, size=size))

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

            # Remap field names from visitor schema to student model
            for old_key, new_key in _FIELD_MAP.items():
                if old_key in data:
                    data[new_key] = data.pop(old_key)

            # check for duplicate Aadhaar sent from gate interface
            aadhar_val = data.get("aadhaar_number")
            if aadhar_val:
                dup_stmt = select(AdmissionStudent.id).where(
                    AdmissionStudent.aadhaar_number == aadhar_val,
                    AdmissionStudent.deleted_at.is_(None),
                )
                dup_res = await db.execute(dup_stmt)
                if dup_res.scalar_one_or_none():
                    # mirror HTTP 409 used elsewhere for uniqueness conflicts
                    raise HTTPException(
                        status_code=409,
                        detail=f"Aadhar number {aadhar_val} already exists",
                    )

            # Generate gate pass number if not provided
            if not data.get("gate_pass_number"):
                data["gate_pass_number"] = await self._generate_unique_gate_pass_no(db)

            # Generate enquiry number
            from apps.admission.services import generate_enquiry_number
            data["enquiry_number"] = await generate_enquiry_number(db, data.get("institution_id"))

            # Pop reference sub-payloads
            consultancy = data.pop("consultancy_reference", None)
            staff = data.pop("staff_reference", None)
            student_ref = data.pop("student_reference", None)
            other = data.pop("other_reference", None)

            # Set gate-enquiry-specific defaults
            data["source"] = SourceEnum.GATE_ENQUIRY
            data["status"] = AdmissionStatusEnum.ENQUIRY
            data["visit_status"] = VisitStatusEnum.CHECKED_IN
            data["reference_type"] = ref_type.value

            student = AdmissionStudent(**data)
            student.check_in_time = func.now()
            db.add(student)
            await db.flush()

            match ref_type:
                case ReferenceType.CONSULTANCY if consultancy:
                    db.add(
                        ConsultancyReference(student_id=student.id, **consultancy)
                    )
                case ReferenceType.STAFF if staff:
                    db.add(StaffReference(student_id=student.id, **staff))
                case ReferenceType.STUDENT if student_ref:
                    db.add(StudentReference(student_id=student.id, **student_ref))
                case ReferenceType.OTHER if other:
                    db.add(OtherReference(student_id=student.id, **other))

            await db.commit()

            stmt = (
                select(AdmissionStudent)
                .where(AdmissionStudent.id == student.id)
                .options(
                    selectinload(AdmissionStudent.consultancy_reference),
                    selectinload(AdmissionStudent.staff_reference),
                    selectinload(AdmissionStudent.student_reference),
                    selectinload(AdmissionStudent.other_reference),
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
                "SELECT gate_pass_number FROM admission_students "
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

    async def get_one(self, db: AsyncSession, student_id: UUID):
        stmt = (
            select(AdmissionStudent)
            .where(
                AdmissionStudent.id == student_id,
                AdmissionStudent.deleted_at.is_(None),
                AdmissionStudent.source == SourceEnum.GATE_ENQUIRY,
            )
            .options(
                joinedload(AdmissionStudent.consultancy_reference),
                joinedload(AdmissionStudent.staff_reference),
                joinedload(AdmissionStudent.student_reference),
                joinedload(AdmissionStudent.other_reference),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_gate_pass_no(self, db: AsyncSession, gate_pass_no: str):
        normalized = gate_pass_no.strip()
        stmt = (
            select(AdmissionStudent)
            .where(
                AdmissionStudent.gate_pass_number == normalized,
                AdmissionStudent.deleted_at.is_(None),
            )
            .options(
                joinedload(AdmissionStudent.consultancy_reference),
                joinedload(AdmissionStudent.staff_reference),
                joinedload(AdmissionStudent.student_reference),
                joinedload(AdmissionStudent.other_reference),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_all(self, db: AsyncSession, query):
        # Ensure only gate enquiries are returned
        query = query.where(AdmissionStudent.source == SourceEnum.GATE_ENQUIRY)
        # Apply DISTINCT ON only when joins are present; otherwise preserve
        # caller-provided sorting (e.g. created_at:desc) without reordering.
        has_joins = bool(getattr(query, "_setup_joins", None))
        pk = getattr(AdmissionStudent, "id", None)
        if has_joins and pk is not None:
            query = query.distinct(pk)

            # PostgreSQL requires DISTINCT ON expressions to match the initial
            # ORDER BY expressions; ensure primary key is ordered first.
            try:
                existing_order_by = getattr(query, "_order_by_clause", None)
                if existing_order_by is not None and len(existing_order_by) > 0:
                    query = query.order_by(None)
                    query = query.order_by(pk, *list(existing_order_by))
                else:
                    query = query.order_by(pk)
            except Exception:
                # Fall back to DISTINCT ON without modifying order if inspection fails.
                pass
        elif has_joins:
            query = query.distinct()

        return await paginate(db, query)

    async def update(
        self, db: AsyncSession, student_id: UUID, payload: AdmissionVisitorUpdate
    ):
        student = await db.get(AdmissionStudent, student_id)
        if not student or student.source != SourceEnum.GATE_ENQUIRY:
            return None

        update_data = payload.dict(exclude_unset=True)
        for old_key, new_key in _FIELD_MAP.items():
            if old_key in update_data:
                update_data[new_key] = update_data.pop(old_key)

        # if the client is updating Aadhaar, ensure it doesn't collide with another record
        if update_data.get("aadhaar_number"):
            aadhar_val = update_data["aadhaar_number"]
            dup_stmt = select(AdmissionStudent.id).where(
                AdmissionStudent.aadhaar_number == aadhar_val,
                AdmissionStudent.id != student_id,
            )
            dup_res = await db.execute(dup_stmt)
            if dup_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=409,
                    detail=f"Aadhar number {aadhar_val} already exists",
                )

        for field, value in update_data.items():
            if hasattr(student, field):
                setattr(student, field, value)

        try:
            await db.commit()
            await db.refresh(student)
        except Exception as exc:
            await db.rollback()
            # Catch DB-level unique constraint violations (e.g. soft-deleted records)
            exc_str = str(exc).lower()
            if "unique" in exc_str or "duplicate" in exc_str or "aadhaar" in exc_str:
                raise HTTPException(
                    status_code=409,
                    detail=f"Aadhar number {update_data.get('aadhaar_number', '')} already exists",
                )
            raise
        return student

    async def delete(self, db: AsyncSession, student_id: UUID):
        student = await db.get(AdmissionStudent, student_id)
        if not student or student.source != SourceEnum.GATE_ENQUIRY:
            return 0
        await db.delete(student)
        await db.commit()
        return 1

    async def pass_out(
        self,
        db: AsyncSession,
        student_id: UUID,
        payload: AdmissionVisitorPassOutRequest,
    ):
        student = await self.get_one(db, student_id)
        if not student:
            return None, False

        if student.visit_status == VisitStatusEnum.CHECKED_OUT:
            return student, True

        check_out_time = payload.check_out_time or datetime.now(timezone.utc)
        if student.check_in_time and self._to_naive_utc(check_out_time) < self._to_naive_utc(student.check_in_time):
            raise ValueError("check_out_time cannot be earlier than check_in_time")

        student.visit_status = VisitStatusEnum.CHECKED_OUT
        student.check_out_time = check_out_time
        student.check_out_remarks = (payload.remarks or "").strip() or None
        db.add(student)
        await db.commit()
        await db.refresh(student)
        return student, False

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
                AdmissionStudent,
                Institution.name.label("institution_name"),
            )
            .select_from(AdmissionStudent)
            .join(Institution, Institution.id == AdmissionStudent.institution_id, isouter=True)
            .where(*filters)
            .order_by(
                AdmissionStudent.check_in_time.desc(),
                AdmissionStudent.created_at.desc(),
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
                AdmissionStudent,
                Institution.name.label("institution_name"),
            )
            .select_from(AdmissionStudent)
            .join(Institution, Institution.id == AdmissionStudent.institution_id, isouter=True)
            .where(*filters)
            .order_by(
                AdmissionStudent.check_in_time.desc(),
                AdmissionStudent.created_at.desc(),
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
        entries_filters.extend(self._time_range_filters(AdmissionStudent.check_in_time, date_from, date_to))
        total_entries = await self._get_count(db, entries_filters)

        exits_filters = list(common_filters)
        exits_filters.append(AdmissionStudent.check_out_time.is_not(None))
        exits_filters.extend(self._time_range_filters(AdmissionStudent.check_out_time, date_from, date_to))
        total_exits = await self._get_count(db, exits_filters)

        inside_filters = list(common_filters)
        inside_filters.append(AdmissionStudent.visit_status == VisitStatusEnum.CHECKED_IN)
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
            AdmissionStudent.deleted_at.is_(None),
            AdmissionStudent.source == SourceEnum.GATE_ENQUIRY,
        ]

        if visit_status:
            filters.append(AdmissionStudent.visit_status == visit_status)

        if institution_id:
            filters.append(AdmissionStudent.institution_id == institution_id)

        if reference_type:
            filters.append(AdmissionStudent.reference_type == reference_type)

        if search:
            like = f"%{search.strip()}%"
            filters.append(
                or_(
                    AdmissionStudent.gate_pass_number.ilike(like),
                    AdmissionStudent.name.ilike(like),
                    AdmissionStudent.student_mobile.ilike(like),
                    AdmissionStudent.father_name.ilike(like),
                    AdmissionStudent.native_place.ilike(like),
                )
            )

        if for_items and (date_from or date_to):
            in_range_in = and_(
                *self._time_range_filters(AdmissionStudent.check_in_time, date_from, date_to)
            )
            in_range_out = and_(
                *self._time_range_filters(AdmissionStudent.check_out_time, date_from, date_to)
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
        stmt = select(func.count()).select_from(AdmissionStudent).where(*filters)
        result = await db.execute(stmt)
        return result.scalar_one() or 0

    def _row_to_report_item(self, row):
        """Maps AdmissionStudent columns back to old API response field names for backward compatibility."""
        student = row[0]
        institution_name = row[1]
        return {
            "id": student.id,
            "gate_pass_no": student.gate_pass_number,
            "student_name": student.name,
            "mobile_number": student.student_mobile,
            "parent_or_guardian_name": student.father_name,
            "native_place": student.native_place,
            "institution_id": student.institution_id,
            "institution_name": institution_name,
            "reference_type": str(student.reference_type) if student.reference_type else None,
            "visit_status": student.visit_status.value
            if hasattr(student.visit_status, "value")
            else str(student.visit_status),
            "check_in_time": student.check_in_time.isoformat() if student.check_in_time else None,
            "check_out_time": student.check_out_time.isoformat() if student.check_out_time else None,
            "check_out_remarks": student.check_out_remarks,
            "created_at": student.created_at.isoformat() if student.created_at else None,
            "updated_at": student.updated_at.isoformat() if student.updated_at else None,
        }

    def _to_naive_utc(self, value: datetime | None):
        if value is None:
            return datetime.min
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)


admission_crud = AdmissionVisitorCRUD()
