"""SIS class/section management and student→class assignment.

A "class" row = one (course + academic_year + section) group with a capacity.
Student assignment is a single FK (AdmissionStudent.class_id) with the section
name mirrored onto AdmissionStudent.section for backward compatibility.
"""
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.admission.admission_entry import (
    AdmissionStatusEnum,
    AdmissionStudent,
    AdmissionStudentProgramDetails,
)
from common.models.master.annual_task import AcademicYear
from common.models.master.institution import Class, Course


def _year_slug(year_name) -> str:
    if not year_name:
        return ""
    import re
    m = re.search(r"(\d{4})", str(year_name))
    return m.group(1) if m else "".join(ch for ch in str(year_name) if ch.isdigit())[:4]


def _serialize_class(cls: Class, enrolled_count: int = 0) -> dict:
    return {
        "id": str(cls.id),
        "code": cls.code,
        "title": cls.title,
        "course_id": str(cls.course_id) if cls.course_id else None,
        "course_title": cls.course.title if cls.course else None,
        "academic_year_id": str(cls.academic_year_id) if cls.academic_year_id else None,
        "academic_year_name": cls.academic_year.year_name if cls.academic_year else None,
        "institution_id": str(cls.institution_id) if cls.institution_id else None,
        "section_name": cls.section_name,
        "capacity": cls.capacity,
        "enrolled_count": enrolled_count,
        "is_active": cls.is_active,
    }


async def _enrolled_counts(session: AsyncSession, class_ids: list) -> dict:
    if not class_ids:
        return {}
    rows = (
        await session.execute(
            select(AdmissionStudent.class_id, func.count())
            .where(AdmissionStudent.class_id.in_(class_ids), AdmissionStudent.deleted_at.is_(None))
            .group_by(AdmissionStudent.class_id)
        )
    ).all()
    return {str(cid): cnt for cid, cnt in rows}


async def create_class(session: AsyncSession, data: dict, user_id) -> dict:
    course = await session.get(Course, data["course_id"])
    if not course:
        raise ValueError("Course not found")

    academic_year_id = data.get("academic_year_id")
    ay = await session.get(AcademicYear, academic_year_id) if academic_year_id else None
    section = (data.get("section_name") or "A").strip() or "A"

    # Duplicate guard (course + year + section)
    dup_q = select(Class).where(
        Class.course_id == data["course_id"],
        Class.section_name == section,
        Class.deleted_at.is_(None),
    )
    dup_q = dup_q.where(
        cast(Class.academic_year_id, String) == str(academic_year_id)
        if academic_year_id else Class.academic_year_id.is_(None)
    )
    if (await session.execute(dup_q)).scalar_one_or_none():
        raise ValueError("A class for this course, academic year and section already exists.")

    institution_id = data.get("institution_id")
    if not institution_id and course.department:
        institution_id = course.department.institution_id

    code_base = (course.short_name or course.code or "CLS").upper().replace(" ", "")
    yr = _year_slug(ay.year_name if ay else None)
    base_code = "-".join(p for p in [code_base, yr, section.upper()] if p)
    # Ensure the (unique) code does not collide
    code = base_code
    suffix = 1
    while (await session.execute(select(Class.id).where(Class.code == code))).scalar_one_or_none():
        suffix += 1
        code = f"{base_code}-{suffix}"

    title_parts = [course.title or code_base]
    if ay:
        title_parts.append(ay.year_name)
    title = f"{' '.join(title_parts)} — Section {section}"

    cls = Class(
        code=code,
        title=title,
        course_id=data["course_id"],
        academic_year_id=academic_year_id,
        institution_id=institution_id,
        section_name=section,
        capacity=data.get("capacity"),
        is_active=True,
        created_by=user_id,
    )
    session.add(cls)
    await session.commit()
    await session.refresh(cls)
    return _serialize_class(cls, 0)


async def list_classes(session: AsyncSession, filters: dict) -> list:
    stmt = select(Class).where(Class.deleted_at.is_(None)).order_by(Class.code.asc())
    f = filters or {}
    if f.get("institution_id"):
        stmt = stmt.where(cast(Class.institution_id, String) == f["institution_id"])
    if f.get("course_id"):
        stmt = stmt.where(cast(Class.course_id, String) == f["course_id"])
    if f.get("academic_year_id"):
        stmt = stmt.where(cast(Class.academic_year_id, String) == f["academic_year_id"])
    classes = (await session.execute(stmt)).scalars().all()
    counts = await _enrolled_counts(session, [c.id for c in classes])
    return [_serialize_class(c, counts.get(str(c.id), 0)) for c in classes]


async def update_class(session: AsyncSession, class_id, data: dict, user_id) -> dict:
    cls = await session.get(Class, class_id)
    if not cls or cls.deleted_at is not None:
        raise ValueError("Class not found")
    for field in ("capacity", "section_name", "is_active"):
        if field in data and data[field] is not None:
            setattr(cls, field, data[field])
    cls.updated_by = user_id
    await session.commit()
    await session.refresh(cls)
    counts = await _enrolled_counts(session, [cls.id])
    return _serialize_class(cls, counts.get(str(cls.id), 0))


async def delete_class(session: AsyncSession, class_id, user_id) -> dict:
    cls = await session.get(Class, class_id)
    if not cls or cls.deleted_at is not None:
        raise ValueError("Class not found")
    counts = await _enrolled_counts(session, [cls.id])
    if counts.get(str(cls.id), 0) > 0:
        raise ValueError("Cannot delete a class that has students assigned. Unassign them first.")
    from datetime import datetime
    cls.deleted_at = datetime.utcnow()
    cls.deleted_by = user_id
    await session.commit()
    return {"deleted": str(class_id)}


# ── Student assignment ───────────────────────────────────────────────────────

def _serialize_assignment_student(s: AdmissionStudent) -> dict:
    prog = s.program_details
    return {
        "id": str(s.id),
        "name": s.name,
        "roll_number": s.roll_number,
        "application_number": s.application_number,
        "department_name": prog.department.name if (prog and prog.department) else None,
        "course_title": prog.course.title if (prog and prog.course) else None,
        "class_id": str(s.class_id) if s.class_id else None,
        "class_code": s.assigned_class.code if s.assigned_class else None,
        "section": s.section,
    }


async def list_assignable_students(session: AsyncSession, filters: dict) -> list:
    """ENROLLED students (roll number assigned), optionally filtered by assigned state."""
    stmt = (
        select(AdmissionStudent)
        .join(
            AdmissionStudentProgramDetails,
            AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id,
            isouter=True,
        )
        .where(
            AdmissionStudent.deleted_at.is_(None),
            AdmissionStudent.status == AdmissionStatusEnum.ENROLLED,
            AdmissionStudent.roll_number.isnot(None),
        )
        .order_by(AdmissionStudent.roll_number.asc().nullslast(), AdmissionStudent.name.asc())
    )
    f = filters or {}
    if f.get("institution_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.institution_id, String) == f["institution_id"])
    if f.get("department_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.department_id, String) == f["department_id"])
    if f.get("course_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.course_id, String) == f["course_id"])
    if f.get("academic_year_id"):
        stmt = stmt.where(cast(AdmissionStudentProgramDetails.academic_year_id, String) == f["academic_year_id"])
    if f.get("assigned") == "true":
        stmt = stmt.where(AdmissionStudent.class_id.isnot(None))
    elif f.get("assigned") == "false":
        stmt = stmt.where(AdmissionStudent.class_id.is_(None))

    students = (await session.execute(stmt)).scalars().all()
    return [_serialize_assignment_student(s) for s in students]


async def assign_students_to_class(session: AsyncSession, class_id, student_ids: list) -> dict:
    cls = await session.get(Class, class_id)
    if not cls or cls.deleted_at is not None:
        raise ValueError("Class not found")
    if not student_ids:
        raise ValueError("No students selected.")

    current = (
        await session.execute(
            select(func.count()).select_from(AdmissionStudent).where(
                AdmissionStudent.class_id == class_id,
                AdmissionStudent.deleted_at.is_(None),
            )
        )
    ).scalar() or 0

    students = (
        await session.execute(
            select(AdmissionStudent).where(
                AdmissionStudent.id.in_(student_ids),
                AdmissionStudent.deleted_at.is_(None),
            )
        )
    ).scalars().all()

    for s in students:
        if s.status != AdmissionStatusEnum.ENROLLED:
            raise ValueError(f"{s.name} is not enrolled and cannot be assigned to a class.")

    new_assignees = [s for s in students if str(s.class_id) != str(class_id)]
    if cls.capacity is not None:
        remaining = cls.capacity - current
        if len(new_assignees) > remaining:
            raise ValueError(
                f"Capacity exceeded: {max(remaining, 0)} seat(s) left in {cls.code}, "
                f"but {len(new_assignees)} new student(s) selected."
            )

    for s in students:
        s.class_id = cls.id
        s.section = cls.section_name

    await session.commit()
    return {"assigned": len(students), "class_id": str(cls.id)}


async def unassign_students(session: AsyncSession, student_ids: list) -> dict:
    if not student_ids:
        raise ValueError("No students selected.")
    students = (
        await session.execute(
            select(AdmissionStudent).where(
                AdmissionStudent.id.in_(student_ids),
                AdmissionStudent.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for s in students:
        s.class_id = None
        s.section = None
    await session.commit()
    return {"unassigned": len(students)}
