import csv
import json
import math
from datetime import date, datetime, time, timezone
from io import StringIO
from uuid import UUID

from fastapi import HTTPException
from fastapi_pagination import Params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_, asc, desc, func, or_, select, text, union_all, literal_column, cast, String, null, case, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from common.models.admission.admission_entry import AdmissionGateEntry, AdmissionStatusEnum, VisitStatusEnum
from common.models.gate.visitor_model import (
    ConsultancyReference,
    OtherReference,
    ReferenceType,
    StaffReference,
    StudentReference,
    VisitStatus,
    PersonType,
    Visitor,
)
from common.models.master.institution import Institution, Staff
from common.schemas.gate.admission_visitor import (
    AdmissionVisitorCreate,
    AdmissionVisitorPassOutRequest,
    AdmissionVisitorReportSummary,
    AdmissionVisitorUpdate,
)
from common.models.admission.consultancy import Consultancy
from common.schemas.gate.visitor_schemas import (
    VisitorCreate,
    VisitorUpdate,
    VisitorReportResponse,
    VisitorReportSummary,
)
from common.models.master.institution import Department

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

        paginated = await paginate(db, stmt, Params(page=page, size=size))
        for item in paginated.items:
            await self._enrich_reference_names(db, item)
        return paginated

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

    async def _enrich_reference_names(self, db: AsyncSession, gate_entry):
        """Attach consultancy_name and staff_name onto the related reference rows
        so Pydantic response models can surface them to the frontend."""
        if not gate_entry:
            return gate_entry

        cref = getattr(gate_entry, "consultancy_reference", None)
        if cref and getattr(cref, "consultancy_id", None):
            from common.models.admission.consultancy import Consultancy
            name = await db.scalar(
                select(Consultancy.name).where(Consultancy.id == cref.consultancy_id)
            )
            setattr(cref, "consultancy_name", name)

        sref = getattr(gate_entry, "staff_reference", None)
        if sref and getattr(sref, "staff_id", None):
            from common.models.master.institution import Staff
            staff_data = (await db.execute(
                select(Staff.name, Staff.designation, Staff.department_id).where(Staff.id == sref.staff_id)
            )).first()
            if staff_data:
                setattr(sref, "staff_name", staff_data.name)
                setattr(sref, "designation", staff_data.designation)
                setattr(sref, "department_id", staff_data.department_id)

        return gate_entry

    async def get_one(self, db: AsyncSession, visitor_id: UUID):
        stmt = (
            select(AdmissionGateEntry)
            .where(
                AdmissionGateEntry.id == visitor_id,
                AdmissionGateEntry.deleted_at.is_(None),
            )
            .options(
                selectinload(AdmissionGateEntry.institution),
                joinedload(AdmissionGateEntry.consultancy_reference),
                joinedload(AdmissionGateEntry.staff_reference),
                joinedload(AdmissionGateEntry.student_reference),
                joinedload(AdmissionGateEntry.other_reference),
            )
        )
        result = await db.execute(stmt)
        gate_entry = result.scalars().first()
        return await self._enrich_reference_names(db, gate_entry)

    async def get_by_gate_pass_no(self, db: AsyncSession, gate_pass_no: str):
        normalized = gate_pass_no.strip()
        stmt = (
            select(AdmissionGateEntry)
            .where(
                AdmissionGateEntry.gate_pass_number == normalized,
                AdmissionGateEntry.deleted_at.is_(None),
            )
            .options(
                selectinload(AdmissionGateEntry.institution),
                joinedload(AdmissionGateEntry.consultancy_reference),
                joinedload(AdmissionGateEntry.staff_reference),
                joinedload(AdmissionGateEntry.student_reference),
                joinedload(AdmissionGateEntry.other_reference),
            )
        )
        result = await db.execute(stmt)
        gate_entry = result.scalars().first()
        return await self._enrich_reference_names(db, gate_entry)

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
        
        # Extract nested reference data
        consultancy_payload = update_data.pop("consultancy_reference", None)
        staff_payload = update_data.pop("staff_reference", None)
        student_payload = update_data.pop("student_reference", None)
        other_payload = update_data.pop("other_reference", None)

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

        # Filter fields that exist in the model columns
        mapper = inspect(AdmissionGateEntry)
        column_names = {c.key for c in mapper.columns}
        
        for field, value in update_data.items():
            if field in column_names:
                setattr(gate_entry, field, value)

        # Handle nested reference updates using relationships
        ref_type = gate_entry.reference_type
        
        if ref_type == "consultancy" and consultancy_payload:
            existing_ref = gate_entry.consultancy_reference
            if existing_ref:
                for k, v in consultancy_payload.items():
                    if k != "id" and hasattr(existing_ref, k): setattr(existing_ref, k, v)
            else:
                consultancy_payload.pop("id", None)
                gate_entry.consultancy_reference = ConsultancyReference(gate_entry_id=visitor_id, **consultancy_payload)
                
        elif ref_type == "staff" and staff_payload:
            existing_ref = gate_entry.staff_reference
            if existing_ref:
                for k, v in staff_payload.items():
                    if k != "id" and hasattr(existing_ref, k): setattr(existing_ref, k, v)
            else:
                staff_payload.pop("id", None)
                gate_entry.staff_reference = StaffReference(gate_entry_id=visitor_id, **staff_payload)
                
        elif ref_type == "student" and student_payload:
            existing_ref = gate_entry.student_reference
            if existing_ref:
                for k, v in student_payload.items():
                    if k != "id" and hasattr(existing_ref, k): setattr(existing_ref, k, v)
            else:
                student_payload.pop("id", None)
                gate_entry.student_reference = StudentReference(gate_entry_id=visitor_id, **student_payload)
                
        elif ref_type == "other" and other_payload:
            existing_ref = gate_entry.other_reference
            if existing_ref:
                for k, v in other_payload.items():
                    if k != "id" and hasattr(existing_ref, k): setattr(existing_ref, k, v)
            else:
                other_payload.pop("id", None)
                gate_entry.other_reference = OtherReference(gate_entry_id=visitor_id, **other_payload)

        try:
            await db.commit()
            return await self.get_one(db, visitor_id)
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
            "image_url": gate_entry.image_url,
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


from common.schemas.gate.visitor_schemas import VisitorCreate, VisitorUpdate

class GeneralVisitorCRUD:
    async def create(self, db: AsyncSession, payload: VisitorCreate):
        data = payload.dict(exclude_unset=True)
        
        # Handle representative_name mapping to name if name is empty and representative_name is provided
        if not data.get("name") and data.get("representative_name"):
            data["name"] = data.pop("representative_name")
        elif data.get("representative_name"):
            # If both are provided, representative_name takes precedence for vendor visitors
            # But we keep 'name' as the primary field in DB
            data["name"] = data.pop("representative_name")
        
        # Remove person_type string before model creation (it's a relationship)
        data.pop("person_type", None)
        if not data.get("pass_number"):
            data["pass_number"] = await self._generate_unique_pass_no(db)
            
        visitor = Visitor(**data)
        visitor.check_in_time = func.now()
        visitor.visit_status = VisitStatus.CHECKED_IN
        
        db.add(visitor)
        try:
            await db.commit()
            await db.refresh(visitor)
            return visitor
        except Exception:
            await db.rollback()
            raise

    async def update(
        self, db: AsyncSession, visitor_id: UUID, payload: VisitorUpdate
    ):
        visitor = await self.get_one(db, visitor_id)
        if not visitor:
            return None

        update_data = payload.dict(exclude_unset=True)
        update_data.pop("id", None)
        update_data.pop("person_type", None) # Remove person_type string
        
        # Handle representative_name mapping if provided
        if update_data.get("representative_name"):
            update_data["name"] = update_data.get("representative_name")

        mapper = inspect(Visitor)
        valid_columns = mapper.columns.keys()

        for field, value in update_data.items():
            if field in valid_columns:
                setattr(visitor, field, value)
        
        # If person_type_id was provided, ensure it's set
        if "person_type_id" in update_data:
            visitor.person_type_id = update_data["person_type_id"]

        try:
            await db.commit()
            await db.refresh(visitor, ["person_type", "institution", "department"])
            return visitor
        except Exception:
            await db.rollback()
            raise

    async def _generate_unique_pass_no(self, db: AsyncSession) -> str:
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")
        prefix = f"VP/{date_str}/"

        result = await db.execute(
            text(
                "SELECT pass_number FROM visitors "
                "WHERE pass_number LIKE :prefix "
                "ORDER BY CAST(SUBSTRING(pass_number FROM 13) AS INTEGER) DESC LIMIT 1"
            ),
            {"prefix": f"{prefix}%"},
        )
        last_pass = result.scalar_one_or_none()

        if not last_pass:
            next_num = 1
        else:
            try:
                next_num = int(last_pass.split("/")[-1]) + 1
            except (IndexError, ValueError):
                next_num = 1

        return f"{prefix}{next_num:03d}"

    async def get_one(self, db: AsyncSession, visitor_id: UUID):
        stmt = select(Visitor).where(Visitor.id == visitor_id).options(
            selectinload(Visitor.institution),
            selectinload(Visitor.department),
            selectinload(Visitor.person_type),
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_filtered(
        self,
        db: AsyncSession,
        page: int = 1,
        size: int = 50,
        search: str | None = None,
        sort: str = "created_at:desc",
        filters: str | None = None,
    ):
        stmt = select(Visitor).options(
            selectinload(Visitor.institution),
            selectinload(Visitor.department),
            selectinload(Visitor.person_type),
        )

        if search and search.strip():
            pattern = f"%{search.strip()}%"
            # Join PersonType to allow filtering/searching by its name if needed, 
            # though current query above only searches Visitor columns.
            # If we want to search person_type name, we need to join it.
            stmt = stmt.join(Visitor.person_type, isouter=True).where(
                or_(
                    Visitor.name.ilike(pattern),
                    Visitor.contact_number.ilike(pattern),
                    Visitor.pass_number.ilike(pattern),
                    Visitor.company_name.ilike(pattern),
                    Visitor.person_name.ilike(pattern),
                    # Now we can search on the joined table
                    text("person_types.name ILIKE :pattern").bindparams(pattern=pattern)
                )
            )

        # Apply basic sorting
        sort_field = "created_at"
        sort_dir = "desc"
        if sort and ":" in sort:
            sort_field, sort_dir = sort.split(":", 1)
        
        column = getattr(Visitor, sort_field, Visitor.created_at)
        stmt = stmt.order_by(desc(column) if sort_dir == "desc" else asc(column))

        return await paginate(db, stmt, Params(page=page, size=size))

    async def get_unique_companies(self, db: AsyncSession):
        try:
            stmt = select(Visitor.company_name).distinct()
            result = await db.execute(stmt)
            return [str(c) for c in result.scalars().all() if c]
        except Exception as e:
            print(f"Error in get_unique_companies: {e}")
            return []


    async def get_report(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        size: int = 20,
        date_from: date = None,
        date_to: date = None,
        visit_status: str = None,
        source: str = None,
        institution_id: UUID = None,
        search: str = None,
    ):
        # 1. Build Visitor Subquery
        v_stmt = select(
            Visitor.id.label("id"),
            Visitor.name.label("name"),
            Visitor.contact_number.label("contact"),
            cast(Visitor.visitor_type, String).label("visitor_type"),
            cast(Visitor.visit_status, String).label("visit_status"),
            Visitor.check_in_time.label("check_in_time"),
            Visitor.check_out_time.label("check_out_time"),
            Visitor.pass_number.label("pass_number"),
            Visitor.institution_id.label("institution_id"),
            Institution.name.label("institution_name"),
            Department.name.label("department_name"),
            Visitor.department_id.label("department_id"),
            Visitor.person_name.label("person_name"),
            PersonType.name.label("person_type"),
            Visitor.person_type_id.label("person_type_id"),
            Visitor.purpose_of_visit.label("purpose_of_visit"),
            Visitor.photo_url.label("photo_path"),
            null().label("native_place"),
            null().label("parent_name"),
            null().label("reference_type"),
            Visitor.company_name.label("company_name"),
            Visitor.vehicle_number.label("vehicle_number"),
            Visitor.members_count.label("members_count"),
            null().label("aadhar_number"),
            literal_column("'VISITOR'").label("source"),
            Visitor.created_at.label("created_at")
        ).select_from(Visitor).outerjoin(
            Institution, Institution.id == Visitor.institution_id
        ).outerjoin(
            Department, Department.id == Visitor.department_id
        ).outerjoin(
            PersonType, PersonType.id == Visitor.person_type_id
        )

        # 2. Build Admission Subquery
        a_stmt = select(
            AdmissionGateEntry.id.label("id"),
            AdmissionGateEntry.student_name.label("name"),
            AdmissionGateEntry.mobile_number.label("contact"),
            literal_column("'ADMISSION'").label("visitor_type"),
            cast(AdmissionGateEntry.visit_status, String).label("visit_status"),
            AdmissionGateEntry.check_in_time.label("check_in_time"),
            AdmissionGateEntry.check_out_time.label("check_out_time"),
            AdmissionGateEntry.gate_pass_number.label("pass_number"),
            AdmissionGateEntry.institution_id.label("institution_id"),
            Institution.name.label("institution_name"),
            null().label("department_name"),
            null().label("department_id"),
            null().label("person_name"),
            case(
                (StaffReference.id != None, func.concat('Staff (', Staff.name, case((Staff.designation != None, func.concat(' - ', Staff.designation)), else_=''), ')')),
                (ConsultancyReference.id != None, func.concat('Consultancy (', Consultancy.name, ')')),
                (StudentReference.id != None, func.concat('Student (', StudentReference.student_name, ')')),
                (OtherReference.id != None, func.concat('Other (', OtherReference.description, ')')),
                else_=AdmissionGateEntry.reference_type
            ).label("person_type"),
            null().label("person_type_id"),
            null().label("purpose_of_visit"),
            AdmissionGateEntry.image_url.label("photo_path"),
            AdmissionGateEntry.native_place.label("native_place"),
            AdmissionGateEntry.parent_or_guardian_name.label("parent_name"),
            case(
                (StaffReference.id != None, func.concat('Staff (', Staff.name, case((Staff.designation != None, func.concat(' - ', Staff.designation)), else_=''), ')')),
                (ConsultancyReference.id != None, func.concat('Consultancy (', Consultancy.name, ')')),
                (StudentReference.id != None, func.concat('Student (', StudentReference.student_name, ')')),
                (OtherReference.id != None, func.concat('Other (', OtherReference.description, ')')),
                else_=AdmissionGateEntry.reference_type
            ).label("reference_type"),
            null().label("company_name"),
            AdmissionGateEntry.vehicle_number.label("vehicle_number"),
            literal_column("1").label("members_count"),
            AdmissionGateEntry.aadhar_number.label("aadhar_number"),
            literal_column("'ADMISSION'").label("source"),
            AdmissionGateEntry.created_at.label("created_at")
        ).select_from(AdmissionGateEntry).join(
            Institution, Institution.id == AdmissionGateEntry.institution_id, isouter=True
        ).join(
            StaffReference, StaffReference.gate_entry_id == AdmissionGateEntry.id, isouter=True
        ).join(
            Staff, Staff.id == StaffReference.staff_id, isouter=True
        ).join(
            ConsultancyReference, ConsultancyReference.gate_entry_id == AdmissionGateEntry.id, isouter=True
        ).join(
            Consultancy, Consultancy.id == ConsultancyReference.consultancy_id, isouter=True
        ).join(
            StudentReference, StudentReference.gate_entry_id == AdmissionGateEntry.id, isouter=True
        ).join(
            OtherReference, OtherReference.gate_entry_id == AdmissionGateEntry.id, isouter=True
        )

        # 3. Apply Filters
        if date_from:
            dt_from = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
            v_stmt = v_stmt.where(Visitor.check_in_time >= dt_from)
            a_stmt = a_stmt.where(AdmissionGateEntry.check_in_time >= dt_from)
        
        if date_to:
            dt_to = datetime.combine(date_to, time.max, tzinfo=timezone.utc)
            v_stmt = v_stmt.where(Visitor.check_in_time <= dt_to)
            a_stmt = a_stmt.where(AdmissionGateEntry.check_in_time <= dt_to)

        if visit_status:
            v_stmt = v_stmt.where(cast(Visitor.visit_status, String) == visit_status)
            a_stmt = a_stmt.where(cast(AdmissionGateEntry.visit_status, String) == visit_status)

        if institution_id:
            v_stmt = v_stmt.where(Visitor.institution_id == institution_id)
            a_stmt = a_stmt.where(AdmissionGateEntry.institution_id == institution_id)

        if search and search.strip():
            pattern = f"%{search.strip()}%"
            v_stmt = v_stmt.where(or_(
                Visitor.name.ilike(pattern),
                Visitor.contact_number.ilike(pattern),
                Visitor.company_name.ilike(pattern),
                Visitor.pass_number.ilike(pattern),
                Visitor.person_name.ilike(pattern),
                PersonType.name.ilike(pattern)
            ))
            a_stmt = a_stmt.where(or_(
                AdmissionGateEntry.student_name.ilike(pattern),
                AdmissionGateEntry.mobile_number.ilike(pattern),
                AdmissionGateEntry.gate_pass_number.ilike(pattern),
                AdmissionGateEntry.native_place.ilike(pattern)
            ))

        # 4. Handle Source Filtering & Union
        if source == "VISITOR":
            combined_stmt = v_stmt
        elif source == "ADMISSION":
            combined_stmt = a_stmt
        else:
            combined_stmt = union_all(v_stmt, a_stmt)

        # 5. Get Total Count
        count_stmt = select(func.count()).select_from(combined_stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        # 6. Execute Paginated & Sorted Query
        final_stmt = (
            select(combined_stmt.subquery())
            .order_by(desc(text("check_in_time")))
            .offset((page - 1) * size)
            .limit(size)
        )

        results = (await db.execute(final_stmt)).all()
        items = [dict(row._mapping) for row in results]

        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": math.ceil(total / size) if size else 0
        }

    async def export_report_csv(
        self,
        db: AsyncSession,
        *,
        date_from: date | None,
        date_to: date | None,
        visit_status: VisitStatus | None,
        institution_id: UUID | None,
        search: str | None,
    ):
        filters = self._build_report_filters(
            date_from=date_from,
            date_to=date_to,
            visit_status=visit_status,
            institution_id=institution_id,
            search=search,
            for_items=True,
        )

        stmt = (
            select(
                Visitor,
                Institution.name.label("institution_name"),
                Department.name.label("department_name"),
                PersonType.name.label("person_type_name"),
            )
            .select_from(Visitor)
            .join(Institution, Institution.id == Visitor.institution_id, isouter=True)
            .join(Department, Department.id == Visitor.department_id, isouter=True)
            .join(PersonType, PersonType.id == Visitor.person_type_id, isouter=True)
            .where(*filters)
            .order_by(
                Visitor.check_in_time.desc(),
                Visitor.created_at.desc(),
            )
        )
        rows = (await db.execute(stmt)).all()
        report_rows = [self._row_to_report_item(row) for row in rows]

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "pass_number",
                "name",
                "contact_number",
                "company_name",
                "members_count",
                "visitor_type",
                "institution_name",
                "department_name",
                "person_type",
                "person_name",
                "purpose_of_visit",
                "visit_status",
                "check_in_time",
                "check_out_time",
                "vehicle_number",
            ]
        )
        for item in report_rows:
            writer.writerow(
                [
                    item["pass_number"],
                    item["name"],
                    item["contact_number"],
                    item["company_name"] or "",
                    item["members_count"],
                    item["visitor_type"],
                    item["institution_name"] or "",
                    item["department_name"] or "",
                    item["person_type"] or "",
                    item["person_name"],
                    item["purpose_of_visit"],
                    item["visit_status"],
                    item["check_in_time"] or "",
                    item["check_out_time"] or "",
                    item["vehicle_number"] or "",
                ]
            )

        date_tag = datetime.now().strftime("%Y%m%d")
        filename = f"visitor_reports_{date_tag}.csv"
        return output.getvalue(), filename

    def _build_report_filters(
        self,
        *,
        date_from: date | None,
        date_to: date | None,
        visit_status: VisitStatus | None,
        institution_id: UUID | None,
        search: str | None,
        for_items: bool,
    ):
        filters = []
        # In this project, Visitor model might not have deleted_at, let's check
        # Based on previous view, it inherits from Base. Base usually has deleted_at if configured.
        # But looking at models/gate/visitor_model.py, it doesn't explicitly define deleted_at.
        # Let's assume it doesn't unless Base has it.
        # Actually, let's play it safe and NOT include it if I didn't see it.
        
        if visit_status:
            filters.append(Visitor.visit_status == visit_status)

        if institution_id:
            filters.append(Visitor.institution_id == institution_id)

        if search:
            like = f"%{search.strip()}%"
            filters.append(
                or_(
                    Visitor.pass_number.ilike(like),
                    Visitor.name.ilike(like),
                    Visitor.contact_number.ilike(like),
                    Visitor.company_name.ilike(like),
                    Visitor.person_name.ilike(like),
                )
            )

        if for_items and (date_from or date_to):
            in_range_in = and_(
                *self._time_range_filters(Visitor.check_in_time, date_from, date_to)
            )
            in_range_out = and_(
                *self._time_range_filters(Visitor.check_out_time, date_from, date_to)
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

    async def _get_report_count(self, db: AsyncSession, filters):
        stmt = select(func.count()).select_from(Visitor).where(*filters)
        result = await db.execute(stmt)
        return result.scalar_one() or 0

    async def _get_report_summary(
        self,
        db: AsyncSession,
        *,
        date_from: date | None,
        date_to: date | None,
        visit_status: VisitStatus | None,
        institution_id: UUID | None,
        search: str | None,
    ) -> VisitorReportSummary:
        common_filters = self._build_report_filters(
            date_from=None,
            date_to=None,
            visit_status=visit_status,
            institution_id=institution_id,
            search=search,
            for_items=False,
        )

        entries_filters = list(common_filters)
        entries_filters.extend(self._time_range_filters(Visitor.check_in_time, date_from, date_to))
        total_entries = await self._get_report_count(db, entries_filters)

        exits_filters = list(common_filters)
        exits_filters.append(Visitor.check_out_time.is_not(None))
        exits_filters.extend(self._time_range_filters(Visitor.check_out_time, date_from, date_to))
        total_exits = await self._get_report_count(db, exits_filters)

        inside_filters = list(common_filters)
        inside_filters.append(Visitor.visit_status == VisitStatus.CHECKED_IN)
        inside_campus = await self._get_report_count(db, inside_filters)

        return VisitorReportSummary(
            total_entries=total_entries,
            total_exits=total_exits,
            inside_campus=inside_campus,
        )

    def _row_to_report_item(self, row):
        visitor = row[0]
        institution_name = row[1]
        department_name = row[2]
        person_type_name = row[3]
        return {
            "id": visitor.id,
            "pass_number": visitor.pass_number,
            "name": visitor.name,
            "contact_number": visitor.contact_number,
            "company_name": visitor.company_name,
            "members_count": visitor.members_count,
            "visitor_type": visitor.visitor_type.value if hasattr(visitor.visitor_type, "value") else str(visitor.visitor_type),
            "institution_id": visitor.institution_id,
            "institution_name": institution_name,
            "department_id": visitor.department_id,
            "department_name": department_name,
            "person_type": person_type_name,
            "person_name": visitor.person_name,
            "purpose_of_visit": visitor.purpose_of_visit,
            "visit_status": visitor.visit_status.value if hasattr(visitor.visit_status, "value") else str(visitor.visit_status),
            "check_in_time": visitor.check_in_time.isoformat() if visitor.check_in_time else None,
            "check_out_time": visitor.check_out_time.isoformat() if visitor.check_out_time else None,
            "has_vehicle": visitor.has_vehicle,
            "vehicle_number": visitor.vehicle_number,
            "vehicle_type": visitor.vehicle_type,
            "created_at": visitor.created_at.isoformat() if visitor.created_at else None,
            "updated_at": visitor.updated_at.isoformat() if visitor.updated_at else None,
        }

from common.models.gate.material_model import MaterialPass, MaterialStatus, MaterialIn
from common.schemas.gate.material_schemas import (
    MaterialPassCreate, 
    MaterialPassUpdate,
    MaterialInCreate
)

class MaterialPassCRUD:
    # ... (existing methods)
    async def create(self, db: AsyncSession, payload: MaterialPassCreate):
        data = payload.dict(exclude_unset=True)
        if not data.get("pass_number"):
            data["pass_number"] = await self._generate_unique_pass_no(db)
        
        # Calculate pending if not provided
        if data.get("pending_quantity") is None:
            data["pending_quantity"] = str(data.get("quantity"))
            
        material_pass = MaterialPass(**data)
        db.add(material_pass)
        await db.commit()
        await db.refresh(material_pass)
        return material_pass

    async def get_all(self, db: AsyncSession, page: int = 1, size: int = 50, search: str | None = None):
        stmt = select(MaterialPass)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    MaterialPass.pass_number.ilike(pattern),
                    MaterialPass.name.ilike(pattern),
                    MaterialPass.material_name.ilike(pattern),
                    MaterialPass.company_name.ilike(pattern)
                )
            )
        stmt = stmt.order_by(desc(MaterialPass.created_at))
        return await paginate(db, stmt, Params(page=page, size=size))

    async def get_one(self, db: AsyncSession, pass_id: UUID):
        stmt = select(MaterialPass).where(MaterialPass.id == pass_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_pass_no(self, db: AsyncSession, pass_no: str):
        stmt = select(MaterialPass).where(MaterialPass.pass_number == pass_no.strip())
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, db: AsyncSession, pass_id: UUID, payload: MaterialPassUpdate):
        material_pass = await self.get_one(db, pass_id)
        if not material_pass:
            return None
        
        update_data = payload.dict(exclude_unset=True)
        
        # Handle in_quantity logic
        if "in_quantity" in update_data:
            material_pass.in_quantity = update_data["in_quantity"]
            
            try:
                # Attempt automated math only if both are numeric
                qty_val = int(material_pass.quantity)
                in_qty_val = int(material_pass.in_quantity)
                pending_val = qty_val - in_qty_val
                
                material_pass.pending_quantity = str(max(0, pending_val))
                
                if pending_val <= 0:
                    material_pass.status = MaterialStatus.RETURNED
                else:
                    material_pass.status = MaterialStatus.PENDING
            except (ValueError, TypeError):
                # If non-numeric (e.g. "10kg"), math is skipped. 
                # Status remains unchanged unless explicitly provided.
                if "status" not in update_data:
                    material_pass.status = MaterialStatus.PENDING

        for key, value in update_data.items():
            if key != "in_quantity" and hasattr(material_pass, key):
                setattr(material_pass, key, value)
        
        await db.commit()
        await db.refresh(material_pass)
        return material_pass

    async def _generate_unique_pass_no(self, db: AsyncSession) -> str:
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")
        prefix = f"MAT-{date_str}/"

        result = await db.execute(
            text(
                "SELECT pass_number FROM material_passes "
                "WHERE pass_number LIKE :prefix "
                "ORDER BY CAST(SUBSTRING(pass_number FROM 14) AS INTEGER) DESC LIMIT 1"
            ),
            {"prefix": f"{prefix}%"},
        )
        last_pass = result.scalar_one_or_none()

        if not last_pass:
            next_num = 1
        else:
            try:
                next_num = int(last_pass.split("/")[-1]) + 1
            except (IndexError, ValueError):
                next_num = 1

        return f"{prefix}{next_num:04d}"

    async def get_unified_report(self, db: AsyncSession, page: int = 1, size: int = 50, search: str | None = None, pass_type: str | None = None, status: str | None = None):
        # 1. Fetch Material Pass records
        stmt_passes = select(MaterialPass)
        if search:
            pattern = f"%{search.strip()}%"
            stmt_passes = stmt_passes.where(
                or_(
                    MaterialPass.pass_number.ilike(pattern),
                    MaterialPass.name.ilike(pattern),
                    MaterialPass.material_name.ilike(pattern),
                    MaterialPass.company_name.ilike(pattern)
                )
            )
        
        # 2. Fetch Material In records
        stmt_in = select(MaterialIn)
        if search:
            pattern = f"%{search.strip()}%"
            stmt_in = stmt_in.where(
                or_(
                    MaterialIn.pass_number.ilike(pattern),
                    MaterialIn.staff_name.ilike(pattern),
                    MaterialIn.material_name.ilike(pattern),
                    MaterialIn.company_name.ilike(pattern)
                )
            )

        res_passes = await db.execute(stmt_passes)
        res_in = await db.execute(stmt_in)
        
        passes = res_passes.scalars().all()
        ins = res_in.scalars().all()
        
        combined = []
        for p in passes:
            combined.append({
                "id": p.id,
                "pass_number": p.pass_number,
                "pass_type": "Material Out/In",
                "name": p.name,
                "material_name": p.material_name,
                "quantity": p.quantity,
                "company_name": p.company_name,
                "place_or_bill": p.place,
                "date": p.out_date,
                "time": p.out_time,
                "status": p.status.value,
                "in_date": p.in_date,
                "in_time": p.in_time,
                "in_quantity": p.in_quantity,
                "pending_quantity": p.pending_quantity,
                "vehicle_number": p.vehicle_number,
                "vehicle_name": p.vehicle_name,
                "created_at": p.created_at
            })
            
        for i in ins:
            combined.append({
                "id": i.id,
                "pass_number": i.pass_number,
                "pass_type": "New Material",
                "name": i.staff_name,
                "material_name": i.material_name,
                "quantity": i.quantity,
                "company_name": i.company_name,
                "place_or_bill": i.bill_number,
                "date": i.bill_date,
                "time": i.created_at.strftime("%H:%M"),
                "status": "received",
                "vehicle_number": i.vehicle_number,
                "vehicle_name": i.vehicle_name,
                "vehicle_charge": i.vehicle_charge,
                "amount": i.total_amount,
                "created_at": i.created_at
            })
            
        # Apply filters
        if pass_type and pass_type != "All":
            combined = [x for x in combined if x["pass_type"] == pass_type]
        
        if status and status != "All":
            combined = [x for x in combined if x["status"] == status.lower()]

        # Sort by created_at desc
        combined.sort(key=lambda x: x["created_at"], reverse=True)
        
        # Manual pagination
        total = len(combined)
        start = (page - 1) * size
        end = start + size
        items = combined[start:end]
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": math.ceil(total / size) if size > 0 else 1
        }


class MaterialInCRUD:
    async def create(self, db: AsyncSession, payload: MaterialInCreate):
        data = payload.dict(exclude_unset=True)
        data["pass_number"] = await self._generate_unique_pass_no(db)
        
        material_in = MaterialIn(**data)
        db.add(material_in)
        await db.commit()
        await db.refresh(material_in)
        return material_in

    async def _generate_unique_pass_no(self, db: AsyncSession) -> str:
        today = datetime.now()
        date_str = today.strftime("%Y%m%d")
        prefix = f"NEW-{date_str}/"

        result = await db.execute(
            text(
                "SELECT pass_number FROM material_in_entries "
                "WHERE pass_number LIKE :prefix "
                "ORDER BY CAST(SUBSTRING(pass_number FROM 14) AS INTEGER) DESC LIMIT 1"
            ),
            {"prefix": f"{prefix}%"},
        )
        last_pass = result.scalar_one_or_none()

        if not last_pass:
            next_num = 1
        else:
            try:
                next_num = int(last_pass.split("/")[-1]) + 1
            except (IndexError, ValueError):
                next_num = 1

        return f"{prefix}{next_num:04d}"

material_pass_crud = MaterialPassCRUD()
material_in_crud = MaterialInCRUD()
admission_crud = AdmissionVisitorCRUD()
general_visitor_crud = GeneralVisitorCRUD()
