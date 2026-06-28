"""Academic Progression service layer.

Pure async functions (no classes), mirroring apps/sis/classes.py and
apps/sis/service.py. Routers catch ``ValueError`` and map it to HTTP errors.

Core rule (see common/models/sis/academic_progression.py): a student's CURRENT
position lives on SISStudentProfile; every transition appends an immutable
SISStudentAcademicHistory row. We never overwrite year/semester without first
recording history.
"""
from datetime import datetime, timezone

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.sis.service import get_or_create_sis_profile
from common.models.admission.admission_entry import (
    AdmissionStatusEnum,
    AdmissionStudent,
    AdmissionStudentPersonalDetails,
    AdmissionStudentProgramDetails,
)
from common.models.master.annual_task import AcademicYear
from common.models.master.institution import Course
from common.models.sis.academic_progression import (
    PromotionTypeEnum,
    SISStudentAcademicHistory,
)
from common.models.sis.sis_student import (
    AcademicStatusEnum,
    EntryModeEnum,
    SISStudentProfile,
)

# Statuses that make a student ineligible for any further progression.
_TERMINAL_STATUSES = {
    AcademicStatusEnum.GRADUATED,
    AcademicStatusEnum.DISCONTINUED,
    AcademicStatusEnum.TRANSFERRED,
    AcademicStatusEnum.ALUMNI,
}

# How many list rows a rollover preview returns per bucket (counts are exact).
_PREVIEW_SAMPLE_CAP = 200


def _now() -> datetime:
    """Timezone-aware UTC — history columns are TIMESTAMP WITH TIME ZONE."""
    return datetime.now(timezone.utc)


def _year_slug(year_name) -> str:
    if not year_name:
        return ""
    import re

    m = re.search(r"(\d{4})", str(year_name))
    return m.group(1) if m else ""


def _derive_year(student: AdmissionStudent) -> int | None:
    """Best-effort current year-of-study from the admission program year string."""
    prog = student.program_details
    if not prog or not prog.year:
        return None
    import re

    m = re.search(r"(\d+)", str(prog.year))
    return int(m.group(1)) if m else None


# ── Outstanding fees (reuses the billing tables; never hard-fails progression) ──

async def _batch_outstanding_fees(session: AsyncSession, student_ids: list) -> dict:
    """{student_id_str: outstanding_amount} computed in two aggregate queries.

    Outstanding = unpaid invoice balance + uninvoiced *student* demand. Wrapped
    defensively: if the billing schema is unavailable, fees never block.
    """
    result = {str(sid): 0.0 for sid in student_ids}
    if not student_ids:
        return result
    try:
        from common.models.billing.application_fees import Invoice
        from common.models.billing.demand import DemandItem
        from common.models.billing.fee_structure import PayerTypeEnum

        inv_rows = (
            await session.execute(
                select(
                    Invoice.student_id,
                    func.coalesce(func.sum(Invoice.balance_due), 0),
                )
                .where(
                    Invoice.student_id.in_(student_ids),
                    Invoice.deleted_at.is_(None),
                )
                .group_by(Invoice.student_id)
            )
        ).all()
        for sid, bal in inv_rows:
            result[str(sid)] = result.get(str(sid), 0.0) + float(bal or 0)

        dem_rows = (
            await session.execute(
                select(
                    DemandItem.student_id,
                    func.coalesce(func.sum(DemandItem.amount), 0),
                )
                .where(
                    DemandItem.student_id.in_(student_ids),
                    DemandItem.deleted_at.is_(None),
                    DemandItem.payer_type == PayerTypeEnum.STUDENT,
                    DemandItem.invoice_id.is_(None),
                    DemandItem.status == "pending",
                )
                .group_by(DemandItem.student_id)
            )
        ).all()
        for sid, amt in dem_rows:
            result[str(sid)] = result.get(str(sid), 0.0) + float(amt or 0)
    except Exception:
        # Billing tables changed/unavailable — treat fees as non-blocking.
        pass
    return result


def _evaluate(
    student: AdmissionStudent, profile, outstanding: float, fees_block: bool = False
) -> dict:
    """The eligibility engine. Returns a structured verdict.

    Outstanding fees are a NON-blocking WARNING by default — a student with
    pending dues can still be promoted (the institution recovers fees later).
    Pass ``fees_block=True`` to treat dues as a hard block (used for graduation,
    where the degree is withheld until fees are cleared).

    Hard blockers (always): terminal academic status, disciplinary / academic
    hold, ON_HOLD admission status.
    """
    reasons: list[str] = []
    warnings: list[str] = []

    status = profile.academic_status if profile else None
    if status and status in _TERMINAL_STATUSES:
        reasons.append(f"Student is {status.value}")

    if profile and profile.disciplinary_hold:
        reasons.append(
            "Disciplinary hold"
            + (f" — {profile.hold_reason}" if profile.hold_reason else "")
        )
    if profile and profile.academic_hold:
        reasons.append(
            "Academic hold"
            + (f" — {profile.hold_reason}" if profile.hold_reason else "")
        )

    if student.status == AdmissionStatusEnum.ON_HOLD:
        reasons.append("Admission status is ON_HOLD")

    has_dues = bool(outstanding and outstanding > 0)
    if has_dues:
        fee_msg = f"Outstanding fees: ₹{outstanding:,.2f}"
        (reasons if fees_block else warnings).append(fee_msg)

    return {
        "eligible": not reasons,
        "eligibility": "ELIGIBLE" if not reasons else "NOT_ELIGIBLE",
        "reasons": reasons,
        "warnings": warnings,
        "has_dues": has_dues,
        "outstanding_fees": round(float(outstanding or 0), 2),
    }


# ── Serializers ──────────────────────────────────────────────────────────────

def _student_row(student: AdmissionStudent, profile, eligibility: dict) -> dict:
    prog = student.program_details
    pd = student.personal_details
    return {
        "id": str(student.id),
        "name": student.name,
        "register_number": profile.register_number if profile else None,
        "roll_number": student.roll_number,
        "student_mobile": pd.student_mobile if pd else None,
        "institution_id": str(prog.institution_id) if (prog and prog.institution_id) else None,
        "department_id": str(prog.department_id) if (prog and prog.department_id) else None,
        "department_name": prog.department.name if (prog and prog.department) else None,
        "course_id": str(prog.course_id) if (prog and prog.course_id) else None,
        "course_title": prog.course.title if (prog and prog.course) else None,
        "academic_year_id": str(prog.academic_year_id) if (prog and prog.academic_year_id) else None,
        "section": student.section,
        "current_year_of_study": profile.current_year_of_study if profile else None,
        "current_semester": profile.current_semester if profile else None,
        "entry_mode": profile.entry_mode.value if (profile and profile.entry_mode) else None,
        "academic_status": (
            profile.academic_status.value if (profile and profile.academic_status) else None
        ),
        "eligibility": eligibility["eligibility"],
        "eligible": eligibility["eligible"],
        "reasons": eligibility["reasons"],
        "warnings": eligibility.get("warnings", []),
        "has_dues": eligibility.get("has_dues", False),
        "outstanding_fees": eligibility["outstanding_fees"],
    }


def _history_row(rec: SISStudentAcademicHistory) -> dict:
    return {
        "id": str(rec.id),
        "date": rec.created_at.isoformat() if rec.created_at else None,
        "effective_from": rec.effective_from.isoformat() if rec.effective_from else None,
        "effective_to": rec.effective_to.isoformat() if rec.effective_to else None,
        "student_id": str(rec.student_id),
        "student_name": rec.student.name if rec.student else None,
        "register_number": rec.register_number,
        "roll_number": rec.roll_number,
        "department_id": str(rec.department_id) if rec.department_id else None,
        "department_name": rec.department.name if rec.department else None,
        "course_id": str(rec.course_id) if rec.course_id else None,
        "course_title": rec.course.title if rec.course else None,
        "academic_year_id": str(rec.academic_year_id) if rec.academic_year_id else None,
        "academic_year_name": rec.academic_year.year_name if rec.academic_year else None,
        "year_of_study": rec.year_of_study,
        "semester": rec.semester,
        "section": rec.section,
        "promotion_type": rec.promotion_type.value if rec.promotion_type else None,
        "entry_mode": rec.entry_mode.value if rec.entry_mode else None,
        "status": rec.status.value if rec.status else None,
        "remarks": rec.remarks,
        "created_by": str(rec.created_by) if rec.created_by else None,
    }


# ── History helpers ──────────────────────────────────────────────────────────

async def _load_profiles_map(session: AsyncSession, student_ids: list) -> dict:
    if not student_ids:
        return {}
    rows = (
        await session.execute(
            select(SISStudentProfile).where(
                SISStudentProfile.admission_student_id.in_(student_ids)
            )
        )
    ).scalars().all()
    return {str(p.admission_student_id): p for p in rows}


async def _close_open_history(session: AsyncSession, student_id, now: datetime) -> None:
    """Close the currently-open interval(s) for a student (set effective_to)."""
    rows = (
        await session.execute(
            select(SISStudentAcademicHistory).where(
                SISStudentAcademicHistory.student_id == student_id,
                SISStudentAcademicHistory.effective_to.is_(None),
                SISStudentAcademicHistory.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for r in rows:
        r.effective_to = now


def _append_history(
    session: AsyncSession,
    student: AdmissionStudent,
    profile: SISStudentProfile,
    promotion_type: PromotionTypeEnum,
    *,
    year,
    semester,
    academic_year_id,
    status: AcademicStatusEnum,
    remarks,
    user_id,
    now: datetime,
    entry_mode=None,
) -> SISStudentAcademicHistory:
    prog = student.program_details
    rec = SISStudentAcademicHistory(
        student_id=student.id,
        institution_id=prog.institution_id if prog else None,
        department_id=prog.department_id if prog else None,
        course_id=prog.course_id if prog else None,
        academic_year_id=academic_year_id or (prog.academic_year_id if prog else None),
        semester=semester,
        year_of_study=year,
        section=student.section,
        roll_number=student.roll_number,
        register_number=profile.register_number if profile else None,
        promotion_type=promotion_type,
        entry_mode=entry_mode or (profile.entry_mode if profile else None),
        status=status,
        effective_from=now,
        remarks=remarks,
        created_by=user_id,
    )
    session.add(rec)
    return rec


def _backfill_batch(profile: SISStudentProfile, student: AdmissionStudent) -> None:
    """Set admission_batch from the admission academic year if not already set."""
    if profile.admission_batch:
        return
    prog = student.program_details
    if prog and prog.academic_year:
        slug = _year_slug(prog.academic_year.year_name)
        if slug:
            profile.admission_batch = slug


# ── Promotable students list ─────────────────────────────────────────────────

async def list_promotable_students(
    session: AsyncSession, filters: dict, page: int, size: int
) -> dict:
    f = filters or {}
    stmt = (
        select(AdmissionStudent, SISStudentProfile)
        .select_from(AdmissionStudent)
        .outerjoin(
            SISStudentProfile,
            SISStudentProfile.admission_student_id == AdmissionStudent.id,
        )
        .options(
            selectinload(AdmissionStudent.program_details),
            selectinload(AdmissionStudent.personal_details),
        )
        .where(
            AdmissionStudent.deleted_at.is_(None),
            AdmissionStudent.status == AdmissionStatusEnum.ENROLLED,
        )
        .order_by(AdmissionStudent.roll_number.asc().nullslast(), AdmissionStudent.name.asc())
    )

    if any(
        f.get(k)
        for k in ("institution_id", "department_id", "course_id", "academic_year_id")
    ):
        stmt = stmt.join(
            AdmissionStudentProgramDetails,
            AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id,
            isouter=True,
        )
        if f.get("institution_id"):
            stmt = stmt.where(cast(AdmissionStudentProgramDetails.institution_id, String) == f["institution_id"])
        if f.get("department_id"):
            stmt = stmt.where(cast(AdmissionStudentProgramDetails.department_id, String) == f["department_id"])
        if f.get("course_id"):
            stmt = stmt.where(cast(AdmissionStudentProgramDetails.course_id, String) == f["course_id"])
        if f.get("academic_year_id"):
            stmt = stmt.where(cast(AdmissionStudentProgramDetails.academic_year_id, String) == f["academic_year_id"])

    if f.get("section"):
        stmt = stmt.where(AdmissionStudent.section == f["section"])
    if f.get("year_of_study"):
        stmt = stmt.where(SISStudentProfile.current_year_of_study == int(f["year_of_study"]))
    if f.get("status"):
        stmt = stmt.where(cast(SISStudentProfile.academic_status, String) == f["status"])

    if f.get("search"):
        pattern = f"%{f['search']}%"
        stmt = stmt.outerjoin(
            AdmissionStudentPersonalDetails,
            AdmissionStudentPersonalDetails.admission_student_id == AdmissionStudent.id,
        ).where(
            or_(
                AdmissionStudent.name.ilike(pattern),
                AdmissionStudent.roll_number.ilike(pattern),
                SISStudentProfile.register_number.ilike(pattern),
                AdmissionStudentPersonalDetails.student_mobile.ilike(pattern),
            )
        )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar() or 0

    offset = (page - 1) * size
    rows = (await session.execute(stmt.offset(offset).limit(size))).all()

    student_ids = [s.id for s, _ in rows]
    outstanding = await _batch_outstanding_fees(session, student_ids)
    items = [
        _student_row(s, p, _evaluate(s, p, outstanding.get(str(s.id), 0.0)))
        for s, p in rows
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, -(-total // size)),
    }


# ── Bulk promotion (atomic) ──────────────────────────────────────────────────

async def promote_students(
    session: AsyncSession, student_ids: list, payload: dict, user_id
) -> dict:
    if not student_ids:
        raise ValueError("No students selected.")
    promote_to_year = payload.get("promote_to_year")
    promote_to_semester = payload.get("promote_to_semester")
    target_academic_year_id = payload.get("target_academic_year_id")
    remarks = payload.get("remarks")

    if promote_to_year is None or promote_to_semester is None:
        raise ValueError("Promote-to year and semester are required.")

    students = (
        await session.execute(
            select(AdmissionStudent)
            .where(
                AdmissionStudent.id.in_(student_ids),
                AdmissionStudent.deleted_at.is_(None),
            )
            .options(selectinload(AdmissionStudent.program_details))
            .with_for_update(of=AdmissionStudent)
        )
    ).scalars().all()
    if not students:
        raise ValueError("Selected students not found.")

    profiles = await _load_profiles_map(session, [s.id for s in students])
    outstanding = await _batch_outstanding_fees(session, [s.id for s in students])

    blocked = []
    for s in students:
        verdict = _evaluate(s, profiles.get(str(s.id)), outstanding.get(str(s.id), 0.0))
        if not verdict["eligible"]:
            blocked.append(f"{s.name} ({', '.join(verdict['reasons'])})")
    if blocked:
        raise ValueError(
            f"Promotion aborted — {len(blocked)} student(s) not eligible: "
            + "; ".join(blocked)
        )

    now = _now()
    for s in students:
        profile = profiles.get(str(s.id)) or await get_or_create_sis_profile(session, str(s.id))
        await _close_open_history(session, s.id, now)
        _backfill_batch(profile, s)
        _append_history(
            session, s, profile, PromotionTypeEnum.PROMOTION,
            year=promote_to_year, semester=promote_to_semester,
            academic_year_id=target_academic_year_id,
            status=AcademicStatusEnum.ACTIVE, remarks=remarks,
            user_id=user_id, now=now,
        )
        profile.current_year_of_study = promote_to_year
        profile.current_semester = promote_to_semester
        if target_academic_year_id:
            profile.current_academic_year_id = target_academic_year_id
        profile.academic_status = AcademicStatusEnum.ACTIVE
        profile.updated_by = user_id

    await session.commit()
    return {
        "promoted": len(students),
        "promote_to_year": promote_to_year,
        "promote_to_semester": promote_to_semester,
        "target_academic_year_id": str(target_academic_year_id) if target_academic_year_id else None,
    }


# ── Promotion history ────────────────────────────────────────────────────────

async def list_promotion_history(
    session: AsyncSession, filters: dict, page: int, size: int
) -> dict:
    f = filters or {}
    stmt = (
        select(SISStudentAcademicHistory)
        .where(SISStudentAcademicHistory.deleted_at.is_(None))
        .order_by(SISStudentAcademicHistory.created_at.desc().nullslast())
    )
    if f.get("student_id"):
        stmt = stmt.where(cast(SISStudentAcademicHistory.student_id, String) == f["student_id"])
    if f.get("department_id"):
        stmt = stmt.where(cast(SISStudentAcademicHistory.department_id, String) == f["department_id"])
    if f.get("academic_year_id"):
        stmt = stmt.where(cast(SISStudentAcademicHistory.academic_year_id, String) == f["academic_year_id"])
    if f.get("promotion_type"):
        stmt = stmt.where(cast(SISStudentAcademicHistory.promotion_type, String) == f["promotion_type"])
    if f.get("search"):
        pattern = f"%{f['search']}%"
        stmt = stmt.where(
            or_(
                SISStudentAcademicHistory.roll_number.ilike(pattern),
                SISStudentAcademicHistory.register_number.ilike(pattern),
            )
        )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar() or 0

    offset = (page - 1) * size
    rows = (await session.execute(stmt.offset(offset).limit(size))).scalars().all()
    return {
        "items": [_history_row(r) for r in rows],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, -(-total // size)),
    }


async def student_history(session: AsyncSession, student_id: str) -> dict:
    rows = (
        await session.execute(
            select(SISStudentAcademicHistory)
            .where(
                cast(SISStudentAcademicHistory.student_id, String) == str(student_id),
                SISStudentAcademicHistory.deleted_at.is_(None),
            )
            .order_by(SISStudentAcademicHistory.effective_from.asc().nullsfirst(),
                      SISStudentAcademicHistory.created_at.asc())
        )
    ).scalars().all()
    return {"student_id": str(student_id), "timeline": [_history_row(r) for r in rows]}


# ── Academic year rollover (mass promotion) ──────────────────────────────────

async def _rollover_candidates(session: AsyncSession, payload: dict):
    f = payload or {}
    source = f.get("source_academic_year_id")
    if not source:
        raise ValueError("Source academic year is required.")
    stmt = (
        select(AdmissionStudent, SISStudentProfile)
        .select_from(AdmissionStudent)
        .join(
            SISStudentProfile,
            SISStudentProfile.admission_student_id == AdmissionStudent.id,
        )
        .options(selectinload(AdmissionStudent.program_details))
        .where(
            AdmissionStudent.deleted_at.is_(None),
            AdmissionStudent.status == AdmissionStatusEnum.ENROLLED,
            cast(SISStudentProfile.current_academic_year_id, String) == str(source),
        )
        .order_by(AdmissionStudent.name.asc())
    )
    if f.get("department_id") or f.get("course_id"):
        stmt = stmt.join(
            AdmissionStudentProgramDetails,
            AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id,
            isouter=True,
        )
        if f.get("department_id"):
            stmt = stmt.where(cast(AdmissionStudentProgramDetails.department_id, String) == f["department_id"])
        if f.get("course_id"):
            stmt = stmt.where(cast(AdmissionStudentProgramDetails.course_id, String) == f["course_id"])
    return (await session.execute(stmt)).all()


async def rollover_preview(session: AsyncSession, payload: dict) -> dict:
    rows = await _rollover_candidates(session, payload)
    outstanding = await _batch_outstanding_fees(session, [s.id for s, _ in rows])

    eligible, blocked = [], []
    for s, p in rows:
        verdict = _evaluate(s, p, outstanding.get(str(s.id), 0.0))
        bucket = eligible if verdict["eligible"] else blocked
        if len(bucket) < _PREVIEW_SAMPLE_CAP:
            bucket.append(_student_row(s, p, verdict))
    eligible_count = sum(
        1 for s, p in rows if _evaluate(s, p, outstanding.get(str(s.id), 0.0))["eligible"]
    )
    return {
        "source_academic_year_id": payload.get("source_academic_year_id"),
        "target_academic_year_id": payload.get("target_academic_year_id"),
        "total": len(rows),
        "eligible_count": eligible_count,
        "blocked_count": len(rows) - eligible_count,
        "sample_cap": _PREVIEW_SAMPLE_CAP,
        "eligible": eligible,
        "blocked": blocked,
    }


async def rollover_commit(session: AsyncSession, payload: dict, user_id) -> dict:
    target = (payload or {}).get("target_academic_year_id")
    if not target:
        raise ValueError("Target academic year is required.")
    remarks = (payload or {}).get("remarks")
    rows = await _rollover_candidates(session, payload)
    if not rows:
        raise ValueError("No active students found in the source academic year.")

    outstanding = await _batch_outstanding_fees(session, [s.id for s, _ in rows])
    now = _now()
    promoted, skipped = 0, 0
    for s, profile in rows:
        verdict = _evaluate(s, profile, outstanding.get(str(s.id), 0.0))
        if not verdict["eligible"]:
            skipped += 1
            continue
        cur_year = profile.current_year_of_study or _derive_year(s) or 1
        cur_sem = profile.current_semester or (cur_year * 2 - 1)
        new_year, new_sem = cur_year + 1, cur_sem + 2

        await _close_open_history(session, s.id, now)
        _backfill_batch(profile, s)
        _append_history(
            session, s, profile, PromotionTypeEnum.PROMOTION,
            year=new_year, semester=new_sem, academic_year_id=target,
            status=AcademicStatusEnum.ACTIVE, remarks=remarks or "Academic year roll over",
            user_id=user_id, now=now,
        )
        profile.current_year_of_study = new_year
        profile.current_semester = new_sem
        profile.current_academic_year_id = target
        profile.academic_status = AcademicStatusEnum.ACTIVE
        profile.updated_by = user_id
        promoted += 1

    await session.commit()
    return {
        "promoted": promoted,
        "skipped": skipped,
        "target_academic_year_id": str(target),
    }


# ── Lateral entry ────────────────────────────────────────────────────────────

async def list_lateral_entry_students(
    session: AsyncSession, filters: dict, page: int, size: int
) -> dict:
    f = filters or {}
    stmt = (
        select(AdmissionStudent, SISStudentProfile)
        .select_from(AdmissionStudent)
        .outerjoin(
            SISStudentProfile,
            SISStudentProfile.admission_student_id == AdmissionStudent.id,
        )
        .options(
            selectinload(AdmissionStudent.program_details),
            selectinload(AdmissionStudent.personal_details),
        )
        .where(
            AdmissionStudent.deleted_at.is_(None),
            or_(
                AdmissionStudent.is_lateral_entry.is_(True),
                cast(SISStudentProfile.entry_mode, String) == EntryModeEnum.LATERAL_ENTRY.value,
            ),
        )
        .order_by(AdmissionStudent.name.asc())
    )
    if f.get("department_id") or f.get("course_id") or f.get("institution_id") or f.get("academic_year_id"):
        stmt = stmt.join(
            AdmissionStudentProgramDetails,
            AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id,
            isouter=True,
        )
        if f.get("institution_id"):
            stmt = stmt.where(cast(AdmissionStudentProgramDetails.institution_id, String) == f["institution_id"])
        if f.get("department_id"):
            stmt = stmt.where(cast(AdmissionStudentProgramDetails.department_id, String) == f["department_id"])
        if f.get("course_id"):
            stmt = stmt.where(cast(AdmissionStudentProgramDetails.course_id, String) == f["course_id"])
        if f.get("academic_year_id"):
            stmt = stmt.where(cast(AdmissionStudentProgramDetails.academic_year_id, String) == f["academic_year_id"])
    if f.get("search"):
        pattern = f"%{f['search']}%"
        stmt = stmt.where(
            or_(
                AdmissionStudent.name.ilike(pattern),
                AdmissionStudent.roll_number.ilike(pattern),
                SISStudentProfile.register_number.ilike(pattern),
                SISStudentProfile.diploma_register_number.ilike(pattern),
            )
        )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar() or 0
    offset = (page - 1) * size
    rows = (await session.execute(stmt.offset(offset).limit(size))).all()

    def _lateral_row(s, p):
        base = _student_row(s, p, _evaluate(s, p, 0.0))
        base.update(
            {
                "is_lateral_entry": s.is_lateral_entry,
                "diploma_institution": p.diploma_institution if p else None,
                "diploma_board": p.diploma_board if p else None,
                "diploma_register_number": p.diploma_register_number if p else None,
                "diploma_completion_year": p.diploma_completion_year if p else None,
                "diploma_percentage": p.diploma_percentage if p else None,
                "diploma_cgpa": p.diploma_cgpa if p else None,
                "diploma_branch": p.diploma_branch if p else None,
                "diploma_certificate_number": p.diploma_certificate_number if p else None,
            }
        )
        return base

    return {
        "items": [_lateral_row(s, p) for s, p in rows],
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, -(-total // size)),
    }


_LATERAL_FIELDS = {
    "diploma_institution", "diploma_board", "diploma_register_number",
    "diploma_completion_year", "diploma_percentage", "diploma_cgpa",
    "diploma_branch", "diploma_certificate_number",
}


async def update_lateral_entry(
    session: AsyncSession, student_id: str, payload: dict, user_id
) -> dict:
    student = await session.get(AdmissionStudent, student_id)
    if not student:
        raise ValueError("Student not found")
    profile = await get_or_create_sis_profile(session, str(student_id))

    for field in _LATERAL_FIELDS:
        if field in payload and payload[field] is not None:
            setattr(profile, field, payload[field])

    profile.entry_mode = EntryModeEnum.LATERAL_ENTRY
    student.is_lateral_entry = True

    # Lateral entrants begin in year 2 / semester 3 unless explicitly given.
    year = payload.get("current_year_of_study") or 2
    semester = payload.get("current_semester") or 3
    profile.current_year_of_study = year
    profile.current_semester = semester
    if not profile.academic_status:
        profile.academic_status = AcademicStatusEnum.ACTIVE
    _backfill_batch(profile, student)
    profile.updated_by = user_id

    # Record the lateral-entry transition once (idempotent on re-edit).
    existing = (
        await session.execute(
            select(func.count())
            .select_from(SISStudentAcademicHistory)
            .where(
                SISStudentAcademicHistory.student_id == student.id,
                SISStudentAcademicHistory.promotion_type == PromotionTypeEnum.LATERAL_ENTRY,
                SISStudentAcademicHistory.deleted_at.is_(None),
            )
        )
    ).scalar() or 0
    if existing == 0:
        now = _now()
        _append_history(
            session, student, profile, PromotionTypeEnum.LATERAL_ENTRY,
            year=year, semester=semester, academic_year_id=None,
            status=AcademicStatusEnum.ACTIVE,
            remarks=payload.get("remarks") or "Lateral entry admission",
            user_id=user_id, now=now, entry_mode=EntryModeEnum.LATERAL_ENTRY,
        )

    await session.commit()
    await session.refresh(profile)
    await session.refresh(student)
    return {
        "id": str(student.id),
        "entry_mode": profile.entry_mode.value if profile.entry_mode else None,
        "current_year_of_study": profile.current_year_of_study,
        "current_semester": profile.current_semester,
    }


# ── Graduation ───────────────────────────────────────────────────────────────

def _graduation_eligible(profile, course) -> tuple[bool, str]:
    if not course:
        return False, "No course mapped"
    if not profile or profile.current_year_of_study is None or profile.current_semester is None:
        return False, "Academic position not set"
    if profile.current_year_of_study != course.course_duration_years:
        return False, (
            f"Not in final year (year {profile.current_year_of_study}/"
            f"{course.course_duration_years})"
        )
    if profile.current_semester != course.total_semesters:
        return False, (
            f"Final semester not completed (sem {profile.current_semester}/"
            f"{course.total_semesters})"
        )
    return True, ""


async def list_graduation_candidates(
    session: AsyncSession, filters: dict, page: int, size: int
) -> dict:
    f = filters or {}
    stmt = (
        select(AdmissionStudent, SISStudentProfile, Course)
        .select_from(AdmissionStudent)
        .join(
            SISStudentProfile,
            SISStudentProfile.admission_student_id == AdmissionStudent.id,
        )
        .join(
            AdmissionStudentProgramDetails,
            AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id,
        )
        .join(Course, Course.id == AdmissionStudentProgramDetails.course_id)
        .options(selectinload(AdmissionStudent.program_details))
        .where(
            AdmissionStudent.deleted_at.is_(None),
            AdmissionStudent.status == AdmissionStatusEnum.ENROLLED,
            SISStudentProfile.current_year_of_study == Course.course_duration_years,
        )
        .order_by(AdmissionStudent.name.asc())
    )
    if f.get("institution_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.institution_id, String) == f["institution_id"])
    if f.get("department_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.department_id, String) == f["department_id"])
    if f.get("course_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.course_id, String) == f["course_id"])
    if f.get("academic_year_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.academic_year_id, String) == f["academic_year_id"])
    if f.get("batch"):
        stmt = stmt.where(SISStudentProfile.admission_batch == f["batch"])
    if f.get("search"):
        pattern = f"%{f['search']}%"
        stmt = stmt.where(
            or_(
                AdmissionStudent.name.ilike(pattern),
                AdmissionStudent.roll_number.ilike(pattern),
                SISStudentProfile.register_number.ilike(pattern),
            )
        )

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar() or 0
    offset = (page - 1) * size
    rows = (await session.execute(stmt.offset(offset).limit(size))).all()

    outstanding = await _batch_outstanding_fees(session, [s.id for s, _, _ in rows])
    items = []
    for s, p, course in rows:
        # Graduation withholds the degree until fees are cleared → fees_block.
        verdict = _evaluate(s, p, outstanding.get(str(s.id), 0.0), fees_block=True)
        grad_ok, grad_reason = _graduation_eligible(p, course)
        row = _student_row(s, p, verdict)
        row.update(
            {
                "course_duration_years": course.course_duration_years if course else None,
                "total_semesters": course.total_semesters if course else None,
                "graduation_eligible": grad_ok and verdict["eligible"],
                "graduation_reason": grad_reason or (
                    "" if verdict["eligible"] else "; ".join(verdict["reasons"])
                ),
            }
        )
        items.append(row)

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, -(-total // size)),
    }


async def graduate_students(session: AsyncSession, student_ids: list, user_id) -> dict:
    if not student_ids:
        raise ValueError("No students selected.")
    students = (
        await session.execute(
            select(AdmissionStudent)
            .where(
                AdmissionStudent.id.in_(student_ids),
                AdmissionStudent.deleted_at.is_(None),
            )
            .options(selectinload(AdmissionStudent.program_details))
            .with_for_update(of=AdmissionStudent)
        )
    ).scalars().all()
    if not students:
        raise ValueError("Selected students not found.")

    profiles = await _load_profiles_map(session, [s.id for s in students])
    outstanding = await _batch_outstanding_fees(session, [s.id for s in students])

    errors = []
    course_map = {}
    for s in students:
        prog = s.program_details
        course = course_map.get(prog.course_id) if (prog and prog.course_id) else None
        if prog and prog.course_id and prog.course_id not in course_map:
            course = await session.get(Course, prog.course_id)
            course_map[prog.course_id] = course
        profile = profiles.get(str(s.id))
        # Graduation withholds the degree until fees are cleared → fees_block.
        verdict = _evaluate(s, profile, outstanding.get(str(s.id), 0.0), fees_block=True)
        grad_ok, grad_reason = _graduation_eligible(profile, course)
        if not verdict["eligible"]:
            errors.append(f"{s.name} ({', '.join(verdict['reasons'])})")
        elif not grad_ok:
            errors.append(f"{s.name} ({grad_reason})")
    if errors:
        raise ValueError(
            f"Graduation aborted — {len(errors)} student(s) not eligible: "
            + "; ".join(errors)
        )

    now = _now()
    for s in students:
        profile = profiles.get(str(s.id)) or await get_or_create_sis_profile(session, str(s.id))
        await _close_open_history(session, s.id, now)
        grad_year = now.year
        if profile.current_academic_year_id:
            ay = await session.get(AcademicYear, profile.current_academic_year_id)
            slug = _year_slug(ay.year_name) if ay else None
            if slug:
                grad_year = int(slug) + (profile.current_year_of_study or 1)
        _append_history(
            session, s, profile, PromotionTypeEnum.GRADUATION,
            year=profile.current_year_of_study, semester=profile.current_semester,
            academic_year_id=profile.current_academic_year_id,
            status=AcademicStatusEnum.GRADUATED, remarks="Graduation processed",
            user_id=user_id, now=now,
        )
        profile.academic_status = AcademicStatusEnum.GRADUATED
        profile.graduation_year = grad_year
        profile.updated_by = user_id

    await session.commit()
    return {"graduated": len(students)}
