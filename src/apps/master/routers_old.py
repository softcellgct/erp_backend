from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from apps.master.services import MasterService
from common.models.master.user import Role
from common.models.master.institution import Class, Course, Department, Institution
from common.models.master.annual_task import AcademicYear, SemesterPeriod
from common.schemas.master.user import (
    RoleCreateSchema,
    RoleResponse,
    RoleUpdateSchema,
)
from common.schemas.master.annual_task import (
    AcademicYearResponse,
    AcademicYearSchema,
    UpdateAcademicYearSchema,
    AcademicYearDepartmentCreate,
    AcademicYearDepartmentResponse,
)
from components.db.db import get_db_session
from components.generator.routes import create_crud_routes
from components.middleware import is_superadmin
from typing import List
from common.schemas.master_schemas import (
    SemesterPeriodCreate,
    SemesterPeriodResponse,
    SemesterPeriodUpdate,
)
from common.schemas.master.institution import (
    InstitutionCreate,
    InstitutionUpdate,
    InstitutionResponse,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    ClassCreate,
    ClassUpdate,
    ClassResponse,
)

# Router
# Institution Router


institution_router = APIRouter()
institution_crud = create_crud_routes(
    Institution,
    InstitutionCreate,
    InstitutionUpdate,
    InstitutionResponse,
    InstitutionResponse,
    decorators=[is_superadmin],
)
institution_router.include_router(
    institution_crud, prefix="/institutions", tags=["Institution"]
)


# Additional endpoint for getting institutions list (non-paginated)
@institution_router.get(
    "/list", response_model=List[InstitutionResponse], tags=["Institution"]
)
@is_superadmin
async def get_institutions_list(
    request: Request, db: AsyncSession = Depends(get_db_session)
):
    """Get a simple list of all institutions."""
    return await MasterService(db).list_institutions()




# Department Router
department_router = APIRouter()

department_crud = create_crud_routes(
    Department,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    DepartmentResponse,
    decorators=[is_superadmin],
)
department_router.include_router(
    department_crud, prefix="/departments", tags=["Department"]
)


# Course Router
course_router = APIRouter()
course_crud = create_crud_routes(
    Course,
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    CourseResponse,
    decorators=[is_superadmin],
)
course_router.include_router(course_crud, prefix="/courses", tags=["Course"])


# Class Router
class_router = APIRouter()

class_crud = create_crud_routes(
    Class,
    ClassCreate,
    ClassUpdate,
    ClassResponse,
    ClassResponse,
    decorators=[is_superadmin],
)
class_router.include_router(class_crud, prefix="/classes", tags=["Class"])


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
    "/academic-years/{academic_year_id}/departments",
    response_model=AcademicYearDepartmentResponse,
    tags=["Academic Years"],
)
@is_superadmin
async def assign_department_to_academic_year(
    academic_year_id: str,
    data: AcademicYearDepartmentCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Assign a department to an academic year with configuration (fee, status).
    """
    return await MasterService(db).assign_department_to_academic_year(academic_year_id, data)

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

# Hostel master
from common.models.master.hostel import Hostel
from common.schemas.master.institution import (
    HostelCreate,
    HostelUpdate,
    HostelResponse,
)

hostel_router = APIRouter()

hostel_crud = create_crud_routes(
    Hostel,
    HostelCreate,
    HostelUpdate,
    HostelResponse,
    HostelResponse,
    decorators=[is_superadmin],
)
hostel_router.include_router(hostel_crud, prefix="/hostels", tags=["Hostels"])

# Simple list endpoint for hostels
@hostel_router.get("/list", response_model=list[HostelResponse], tags=["Hostels"])  # type: ignore
@is_superadmin
async def list_hostels(institution_id: str | None = None, db: AsyncSession = Depends(get_db_session)):
    stmt = None
    from sqlalchemy import select
    stmt = select(Hostel)
    if institution_id:
        stmt = stmt.where(Hostel.institution_id == institution_id)
    res = await db.execute(stmt)
    return res.scalars().all()
