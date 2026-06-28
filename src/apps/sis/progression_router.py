"""HTTP endpoints for the SIS Academic Progression module.

Mounted at /api/sis/academic-progression (registered in apps/__init__.py).
Business logic lives in apps/sis/progression_service.py; this layer only
validates input, extracts the user, and maps ValueError → HTTP errors —
mirroring the rest of the SIS module.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.sis import progression_service as svc
from apps.sis.schemas import (
    GraduateStudentsRequest,
    LateralEntryUpdate,
    PromoteStudentsRequest,
    RolloverCommitRequest,
)
from components.db.db import get_db_session
from components.generator.utils.get_user_from_request import get_user_id

router = APIRouter(
    prefix="/sis/academic-progression", tags=["SIS Academic Progression"]
)


# ── Promotion ────────────────────────────────────────────────────────────────

@router.get("/promotable-students")
async def list_promotable_students(
    page: int = 1,
    size: int = 20,
    search: str = "",
    institution_id: str = "",
    department_id: str = "",
    course_id: str = "",
    academic_year_id: str = "",
    section: str = "",
    year_of_study: str = "",
    status: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    """Enrolled students with computed promotion eligibility."""
    filters = {
        "search": search,
        "institution_id": institution_id,
        "department_id": department_id,
        "course_id": course_id,
        "academic_year_id": academic_year_id,
        "section": section,
        "year_of_study": year_of_study,
        "status": status,
    }
    return await svc.list_promotable_students(session, filters, page, size)


@router.post("/promote")
async def promote_students(
    payload: PromoteStudentsRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Bulk-promote the selected students (atomic — aborts if any is ineligible)."""
    try:
        user_id = await get_user_id(request)
        return await svc.promote_students(
            session,
            [str(sid) for sid in payload.student_ids],
            {
                "promote_to_year": payload.promote_to_year,
                "promote_to_semester": payload.promote_to_semester,
                "target_academic_year_id": (
                    str(payload.target_academic_year_id)
                    if payload.target_academic_year_id else None
                ),
                "remarks": payload.remarks,
            },
            str(user_id) if user_id else None,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


# ── Promotion history ────────────────────────────────────────────────────────

@router.get("/history")
async def list_promotion_history(
    page: int = 1,
    size: int = 20,
    search: str = "",
    student_id: str = "",
    department_id: str = "",
    academic_year_id: str = "",
    promotion_type: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    filters = {
        "search": search,
        "student_id": student_id,
        "department_id": department_id,
        "academic_year_id": academic_year_id,
        "promotion_type": promotion_type,
    }
    return await svc.list_promotion_history(session, filters, page, size)


@router.get("/student/{student_id}/history")
async def student_history(
    student_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    return await svc.student_history(session, str(student_id))


# ── Academic year roll over ──────────────────────────────────────────────────

@router.get("/rollover/preview")
async def rollover_preview(
    source_academic_year_id: str,
    target_academic_year_id: str = "",
    department_id: str = "",
    course_id: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await svc.rollover_preview(
            session,
            {
                "source_academic_year_id": source_academic_year_id,
                "target_academic_year_id": target_academic_year_id or None,
                "department_id": department_id or None,
                "course_id": course_id or None,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/rollover/commit")
async def rollover_commit(
    payload: RolloverCommitRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    try:
        user_id = await get_user_id(request)
        return await svc.rollover_commit(
            session,
            {
                "source_academic_year_id": str(payload.source_academic_year_id),
                "target_academic_year_id": str(payload.target_academic_year_id),
                "department_id": str(payload.department_id) if payload.department_id else None,
                "course_id": str(payload.course_id) if payload.course_id else None,
                "remarks": payload.remarks,
            },
            str(user_id) if user_id else None,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


# ── Lateral entry ────────────────────────────────────────────────────────────

@router.get("/lateral-entry-students")
async def list_lateral_entry_students(
    page: int = 1,
    size: int = 20,
    search: str = "",
    institution_id: str = "",
    department_id: str = "",
    course_id: str = "",
    academic_year_id: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    filters = {
        "search": search,
        "institution_id": institution_id,
        "department_id": department_id,
        "course_id": course_id,
        "academic_year_id": academic_year_id,
    }
    return await svc.list_lateral_entry_students(session, filters, page, size)


@router.put("/lateral-entry-students/{student_id}")
async def update_lateral_entry(
    student_id: UUID,
    payload: LateralEntryUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    try:
        user_id = await get_user_id(request)
        return await svc.update_lateral_entry(
            session,
            str(student_id),
            payload.model_dump(exclude_unset=True),
            str(user_id) if user_id else None,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


# ── Graduation ───────────────────────────────────────────────────────────────

@router.get("/graduation-candidates")
async def list_graduation_candidates(
    page: int = 1,
    size: int = 20,
    search: str = "",
    institution_id: str = "",
    department_id: str = "",
    course_id: str = "",
    academic_year_id: str = "",
    batch: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    filters = {
        "search": search,
        "institution_id": institution_id,
        "department_id": department_id,
        "course_id": course_id,
        "academic_year_id": academic_year_id,
        "batch": batch,
    }
    return await svc.list_graduation_candidates(session, filters, page, size)


@router.post("/graduate")
async def graduate_students(
    payload: GraduateStudentsRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    try:
        user_id = await get_user_id(request)
        return await svc.graduate_students(
            session,
            [str(sid) for sid in payload.student_ids],
            str(user_id) if user_id else None,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
