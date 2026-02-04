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
