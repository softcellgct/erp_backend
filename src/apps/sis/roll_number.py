"""Roll-number generation: a pure template renderer plus batch preview/commit.

Token vocabulary (each token is a dict in the ``tokens`` list):
  {"type": "academic_year", "digits": 4|2}
  {"type": "department_code"}
  {"type": "course_code"}
  {"type": "literal", "value": "/"}
  {"type": "running_number", "padding": 3, "start": 1, "reset_scope": "course_year"}

``reset_scope`` ∈ {global, institution, department, course, course_year} controls
how the running counter is grouped/continued.
"""
import re
from datetime import datetime, timezone

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.admission.admission_entry import (
    AdmissionStatusEnum,
    AdmissionStudent,
    AdmissionStudentPersonalDetails,
    AdmissionStudentProgramDetails,
)
from common.models.sis.roll_number_template import RollNumberTemplate

VALID_RESET_SCOPES = {"global", "institution", "department", "course", "course_year"}


# ── Pure rendering ───────────────────────────────────────────────────────────

def _academic_year_token(year_name, digits: int) -> str:
    """Render the academic-year portion. Accepts "2026", "2026-27", "2026-2027"."""
    if not year_name:
        return ""
    m = re.search(r"(\d{4})", str(year_name))
    yr = m.group(1) if m else "".join(ch for ch in str(year_name) if ch.isdigit())[:4]
    if not yr:
        return ""
    return yr[-2:] if int(digits or 4) == 2 else yr


def render_roll_number(tokens, separator, ctx, running_n: int) -> str:
    """Render a single roll number from a token list. Pure / unit-testable.

    ``ctx`` provides: academic_year_name, department_code, course_code.
    Unknown token types are ignored; empty parts are dropped before joining.
    """
    parts = []
    for tok in tokens or []:
        t = (tok or {}).get("type")
        if t == "academic_year":
            parts.append(_academic_year_token(ctx.get("academic_year_name"), tok.get("digits", 4)))
        elif t == "department_code":
            parts.append(str(ctx.get("department_code") or ""))
        elif t == "course_code":
            parts.append(str(ctx.get("course_code") or ""))
        elif t == "literal":
            parts.append(str(tok.get("value", "")))
        elif t == "running_number":
            padding = int(tok.get("padding") or 0)
            parts.append(str(int(running_n)).zfill(padding))
    return (separator or "").join(p for p in parts if p != "")


def _running_config(tokens):
    """Extract (start, reset_scope) from the running_number token, with defaults."""
    for tok in tokens or []:
        if (tok or {}).get("type") == "running_number":
            start = tok.get("start")
            scope = tok.get("reset_scope")
            return (
                int(start) if start is not None else 1,
                scope if scope in VALID_RESET_SCOPES else "course_year",
            )
    return 1, "course_year"


# ── Context / scope helpers ──────────────────────────────────────────────────

def student_context(student: AdmissionStudent) -> dict:
    """Build the render context + scope identifiers for a student."""
    prog = student.program_details
    dept = prog.department if prog else None
    course = prog.course if prog else None
    ay = prog.academic_year if prog else None
    return {
        "academic_year_name": ay.year_name if ay else None,
        "department_code": (dept.code if dept else None),
        "course_code": (course.short_name or course.code) if course else None,
        "institution_id": str(prog.institution_id) if (prog and prog.institution_id) else None,
        "department_id": str(prog.department_id) if (prog and prog.department_id) else None,
        "course_id": str(prog.course_id) if (prog and prog.course_id) else None,
        "academic_year_id": str(prog.academic_year_id) if (prog and prog.academic_year_id) else None,
    }


def _scope_key(ctx: dict, reset_scope: str) -> tuple:
    if reset_scope == "institution":
        return (ctx.get("institution_id"),)
    if reset_scope == "department":
        return (ctx.get("department_id"),)
    if reset_scope == "course":
        return (ctx.get("course_id"),)
    if reset_scope == "course_year":
        return (ctx.get("course_id"), ctx.get("academic_year_id"))
    return ("__global__",)


# ── DB queries ───────────────────────────────────────────────────────────────

def _eligible_query(filters: dict, only_unassigned: bool):
    """Finalized, PROVISIONALLY_ALLOTTED students matching the filters, ordered
    deterministically so preview and commit agree."""
    stmt = (
        select(AdmissionStudent)
        .join(
            AdmissionStudentProgramDetails,
            AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id,
            isouter=True,
        )
        .where(
            AdmissionStudent.deleted_at.is_(None),
            AdmissionStudent.status == AdmissionStatusEnum.PROVISIONALLY_ALLOTTED,
            AdmissionStudent.perfect_entry_finalized.is_(True),
        )
        .order_by(
            AdmissionStudent.application_number.asc().nullslast(),
            AdmissionStudent.created_at.asc().nullslast(),
            AdmissionStudent.id.asc(),
        )
    )
    if only_unassigned:
        stmt = stmt.where(AdmissionStudent.roll_number.is_(None))

    f = filters or {}
    if f.get("institution_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.institution_id, String) == f["institution_id"])
    if f.get("department_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.department_id, String) == f["department_id"])
    if f.get("course_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.course_id, String) == f["course_id"])
    if f.get("academic_year_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.academic_year_id, String) == f["academic_year_id"])
    if f.get("quota"):
        stmt = stmt.where(AdmissionStudentProgramDetails.quota_type.ilike(f"%{f['quota']}%"))
    if f.get("section"):
        stmt = stmt.where(AdmissionStudent.section == f["section"])
    return stmt


async def _base_counts(session: AsyncSession, reset_scope: str) -> dict:
    """For each scope group, how many students already have a roll number.
    Used to continue the running sequence across batches."""
    PD = AdmissionStudentProgramDetails
    cols = []
    if reset_scope == "institution":
        cols = [PD.institution_id]
    elif reset_scope == "department":
        cols = [PD.department_id]
    elif reset_scope == "course":
        cols = [PD.course_id]
    elif reset_scope == "course_year":
        cols = [PD.course_id, PD.academic_year_id]

    base = (
        select(*cols, func.count())
        .select_from(AdmissionStudent)
        .join(PD, PD.admission_student_id == AdmissionStudent.id, isouter=True)
        .where(
            AdmissionStudent.deleted_at.is_(None),
            AdmissionStudent.roll_number.isnot(None),
        )
    )
    if cols:
        base = base.group_by(*cols)
    rows = (await session.execute(base)).all()

    counts = {}
    for row in rows:
        *key_vals, cnt = row
        key = tuple(str(v) if v is not None else None for v in key_vals) or ("__global__",)
        if not cols:
            key = ("__global__",)
        counts[key] = cnt
    return counts


async def _existing_roll_pairs(session: AsyncSession) -> set:
    """All (institution_id, roll_number) pairs already in use (non-deleted)."""
    PD = AdmissionStudentProgramDetails
    rows = (
        await session.execute(
            select(cast(PD.institution_id, String), AdmissionStudent.roll_number)
            .select_from(AdmissionStudent)
            .join(PD, PD.admission_student_id == AdmissionStudent.id, isouter=True)
            .where(
                AdmissionStudent.deleted_at.is_(None),
                AdmissionStudent.roll_number.isnot(None),
            )
        )
    ).all()
    return {(r[0], r[1]) for r in rows}


async def _build_rows(session, students, tokens, separator, start_value, reset_scope):
    """Render generated roll numbers for the given students and flag conflicts."""
    base_counts = await _base_counts(session, reset_scope)
    existing_pairs = await _existing_roll_pairs(session)

    group_index = {}
    batch_seen = set()
    rows = []
    for st in students:
        ctx = student_context(st)
        key = _scope_key(ctx, reset_scope)
        idx = group_index.get(key, 0)
        running_n = start_value + base_counts.get(key, 0) + idx
        group_index[key] = idx + 1

        generated = render_roll_number(tokens, separator, ctx, running_n)
        pair = (ctx.get("institution_id"), generated)
        conflict = (not generated) or pair in existing_pairs or pair in batch_seen
        if generated:
            batch_seen.add(pair)

        rows.append({
            "student_id": str(st.id),
            "name": st.name,
            "application_number": st.application_number,
            "department_name": st.program_details.department.name if (st.program_details and st.program_details.department) else None,
            "course_title": st.program_details.course.title if (st.program_details and st.program_details.course) else None,
            "current_roll_number": st.roll_number,
            "generated_roll_number": generated,
            "conflict": conflict,
            "_student": st,
        })
    return rows


# ── Public service API ───────────────────────────────────────────────────────

async def get_roll_template(session: AsyncSession, department_id: str, academic_year_id: str):
    if not (department_id and academic_year_id):
        return None
    result = await session.execute(
        select(RollNumberTemplate).where(
            cast(RollNumberTemplate.department_id, String) == department_id,
            cast(RollNumberTemplate.academic_year_id, String) == academic_year_id,
            RollNumberTemplate.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def upsert_roll_template(session: AsyncSession, data: dict, user_id):
    """Insert or update the template for (department_id, academic_year_id)."""
    existing = await get_roll_template(
        session, str(data.get("department_id")), str(data.get("academic_year_id"))
    )
    if existing:
        for field in ("institution_id", "course_id", "name", "tokens", "separator"):
            if field in data and data[field] is not None:
                setattr(existing, field, data[field])
        existing.updated_by = user_id
        template = existing
    else:
        template = RollNumberTemplate(
            institution_id=data.get("institution_id"),
            department_id=data.get("department_id"),
            course_id=data.get("course_id"),
            academic_year_id=data.get("academic_year_id"),
            name=data.get("name"),
            tokens=data.get("tokens") or [],
            separator=data.get("separator") or "",
            created_by=user_id,
        )
        session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def preview_batch_roll_numbers(session: AsyncSession, payload: dict) -> dict:
    """Read-only preview. Returns rows with generated roll numbers + conflicts."""
    tokens = payload.get("tokens") or []
    separator = payload.get("separator") or ""
    start_value, reset_scope = _running_config(tokens)
    only_unassigned = payload.get("only_unassigned", True)

    result = await session.execute(_eligible_query(payload.get("filters") or {}, only_unassigned))
    students = result.scalars().all()

    rows = await _build_rows(session, students, tokens, separator, start_value, reset_scope)
    conflicts = [{"student_id": r["student_id"], "name": r["name"], "roll_number": r["generated_roll_number"]}
                 for r in rows if r["conflict"]]
    for r in rows:
        r.pop("_student", None)
    return {
        "items": rows,
        "total": len(rows),
        "conflicts": conflicts,
        "reset_scope": reset_scope,
        "start_value": start_value,
    }


async def commit_batch_roll_numbers(session: AsyncSession, payload: dict, enrolled_by) -> dict:
    """Atomically assign roll numbers + enroll. Aborts (raises) on any conflict."""
    tokens = payload.get("tokens") or []
    separator = payload.get("separator") or ""
    start_value, reset_scope = _running_config(tokens)
    only_unassigned = payload.get("only_unassigned", True)

    # Lock candidate rows for the duration of the transaction.
    stmt = _eligible_query(payload.get("filters") or {}, only_unassigned).with_for_update(of=AdmissionStudent)
    students = (await session.execute(stmt)).scalars().all()

    if not students:
        raise ValueError("No finalized students match the selected filters.")

    rows = await _build_rows(session, students, tokens, separator, start_value, reset_scope)
    conflicts = [{"student_id": r["student_id"], "name": r["name"], "roll_number": r["generated_roll_number"]}
                 for r in rows if r["conflict"]]
    if conflicts:
        await session.rollback()
        raise ValueError(
            f"Generation aborted — {len(conflicts)} roll number(s) conflict with existing "
            f"or duplicate values. Adjust the template and preview again."
        )

    from apps.sis.service import get_or_create_sis_profile

    now = datetime.utcnow()
    assigned = 0
    for r in rows:
        st = r["_student"]
        st.roll_number = r["generated_roll_number"]
        st.status = AdmissionStatusEnum.ENROLLED
        st.enrolled_at = now
        if st.current_semester is None:
            st.current_semester = 1
        st.is_sem1_active = True
        await get_or_create_sis_profile(session, str(st.id))
        assigned += 1

    await session.commit()

    # Save the template after the assignments are committed (separate commit).
    f = payload.get("filters") or {}
    if payload.get("save_template") and f.get("department_id") and f.get("academic_year_id"):
        await upsert_roll_template(
            session,
            {
                "institution_id": f.get("institution_id"),
                "department_id": f.get("department_id"),
                "course_id": f.get("course_id"),
                "academic_year_id": f.get("academic_year_id"),
                "name": payload.get("template_name"),
                "tokens": tokens,
                "separator": separator,
            },
            enrolled_by,
        )

    return {"assigned": assigned, "reset_scope": reset_scope}
