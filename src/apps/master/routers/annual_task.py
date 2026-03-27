from fastapi import APIRouter, Depends,Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.master.services.annual_task import AnnualTaskService
from common.models.master.annual_task import AcademicYear, SemesterPeriod
from common.schemas.master.annual_task import (
    AcademicYearResponse,
    AcademicYearSchema,
    UpdateAcademicYearSchema,
    UpdateAcademicYearSchema,
    AcademicYearCourseCreate,
    AcademicYearCourseResponse,
    SemesterPeriodCreate,
    SemesterPeriodResponse,
    SemesterPeriodUpdate,
)
from components.db.db import get_db_session
from components.generator.routes import create_crud_routes
from components.middleware import is_superadmin
from typing import List

# Academic Year Router
academic_year_router = APIRouter()

# ========== Specific routes (registered BEFORE CRUD) ==========

@academic_year_router.get(
    "/academic-years/admission-active",
    response_model=List[AcademicYearResponse],
    tags=["Academic Years"],
)
@is_superadmin
async def get_admission_active_years(
    request: Request,
    institution_id: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get academic years where admission is active and status is active.
    Optionally filtered by institution_id.
    """
    from apps.master.services.institution import InstitutionService
    from uuid import UUID
    inst_id = UUID(institution_id) if institution_id else None
    return await InstitutionService(db).list_admission_active_years(inst_id)


@academic_year_router.get(
    "/academic-years/{academic_year_id}/active-courses",
    response_model=list,
    tags=["Academic Years"],
)
@is_superadmin
async def get_active_courses_for_year(
    request: Request,
    academic_year_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get active courses assigned to a specific academic year.
    """
    from apps.master.services.institution import InstitutionService
    from uuid import UUID
    return await InstitutionService(db).list_active_courses_for_year(UUID(academic_year_id))


@academic_year_router.get(
    "/academic-years/{academic_year_id}/eligible-programs",
    tags=["Academic Years"],
)
async def get_admission_eligible_programs(
    request: Request,
    academic_year_id: str,
    institution_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get admission-eligible departments and courses for one institution + academic year.

    Eligibility:
    - department active
    - course active
    - academic year course config active
    - application_fee > 0
    """
    from apps.master.services.institution import InstitutionService
    from uuid import UUID

    return await InstitutionService(db).list_admission_eligible_programs(
        UUID(institution_id), UUID(academic_year_id)
    )

@academic_year_router.post(
    "/academic-years/{academic_year_id}/courses",
    response_model=AcademicYearCourseResponse,
    tags=["Academic Years"],
)
@is_superadmin
async def assign_course_to_academic_year(
    request: Request,
    academic_year_id: str, # UUID via Pydantic or str? service expects UUID. FastAPI converts path param if annotated. But here it's str in signature.
    data: AcademicYearCourseCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Assign a course to an academic year with configuration (fee, status).
    """
    from uuid import UUID
    return await AnnualTaskService(db).assign_course_to_academic_year(UUID(academic_year_id), data)

@academic_year_router.get(
    "/academic-years/{academic_year_id}/courses",
    response_model=List[AcademicYearCourseResponse],
    tags=["Academic Years"],
)
@is_superadmin
async def get_courses_for_academic_year(
    request: Request,
    academic_year_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get all courses assigned to an academic year.
    """
    from uuid import UUID
    return await AnnualTaskService(db).get_courses_for_academic_year(UUID(academic_year_id))

# custom create handler -- important to pop course_configs and delegate to service
@academic_year_router.post(
    "/academic-years",
    response_model=AcademicYearResponse,
    tags=["Academic Years"],
)
@is_superadmin
async def create_academic_year(
    request: Request,
    data: AcademicYearSchema,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a new academic year and optionally configure courses for it.
    This uses the service method which knows how to handle the
    `course_configs` key; without it the generic CRUD route would merely
    ignore that field (or in older versions crash).
    """
    return await AnnualTaskService(db).create_academic_year(data)


@academic_year_router.put(
    "/academic-years/{academic_year_id}",
    response_model=AcademicYearResponse,
    tags=["Academic Years"],
)
@is_superadmin
async def update_academic_year(
    request: Request,
    academic_year_id: str,
    data: UpdateAcademicYearSchema,
    db: AsyncSession = Depends(get_db_session),
):
    """Update a single academic year using service logic."""
    from uuid import UUID
    return await AnnualTaskService(db).update_academic_year(UUID(academic_year_id), data)


@academic_year_router.post(
    "/academic-years/{academic_year_id}/activate",
    response_model=AcademicYearResponse,
    tags=["Academic Years"],
)
@is_superadmin
async def activate_academic_year(
    request: Request,
    academic_year_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    from uuid import UUID
    return await AnnualTaskService(db).set_active_academic_year(UUID(academic_year_id))


@academic_year_router.post(
    "/academic-years/{academic_year_id}/admissions/open",
    response_model=AcademicYearResponse,
    tags=["Academic Years"],
)
@is_superadmin
async def open_admissions_for_year(
    request: Request,
    academic_year_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Mark this academic year as the one where admission is active.

    Any other year belonging to the same institution will have its
    `admission_active` flag cleared automatically.
    """
    from uuid import UUID
    return await AnnualTaskService(db).set_admission_active(UUID(academic_year_id))

@academic_year_router.put(
    "/academic-years/{academic_year_id}/courses/{course_id}",
    response_model=AcademicYearCourseResponse,
    tags=["Academic Years"],
)
@is_superadmin
async def update_course_config(
    request: Request,
    academic_year_id: str,
    course_id: str,
    data: AcademicYearCourseCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Update configuration (fee, status) for a specific course in an academic year.
    """
    from uuid import UUID
    return await AnnualTaskService(db).update_course_config(UUID(academic_year_id), UUID(course_id), data)

@academic_year_router.delete(
    "/academic-years/{academic_year_id}/courses/{course_id}",
    tags=["Academic Years"],
)
@is_superadmin
async def remove_course_from_academic_year(
    request: Request,
    academic_year_id: str,
    course_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Remove a course from an academic year.
    """
    from uuid import UUID
    return await AnnualTaskService(db).remove_course_from_academic_year(UUID(academic_year_id), UUID(course_id))

# ========== CRUD routes (registered AFTER specific routes) ==========

academic_year_crud = create_crud_routes(
    AcademicYear,
    AcademicYearSchema,
    UpdateAcademicYearSchema,
    AcademicYearResponse,
    AcademicYearResponse,
    decorators=[is_superadmin],
)
academic_year_router.include_router(
    academic_year_crud, prefix="/academic-years", tags=["Academic Years"]
)

# Semester Period Router
sem_period_router = APIRouter()
sem_period_crud = create_crud_routes(
    SemesterPeriod,
    SemesterPeriodCreate,
    SemesterPeriodUpdate,
    SemesterPeriodResponse,
    SemesterPeriodResponse,
)
sem_period_router.include_router(
    sem_period_crud, prefix="/semester-periods", tags=["Semester Periods"]
)
