from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from apps.master.services import MasterService
from common.models.auth.user import Class, Course, Department, Institution, Role
from common.models.master.academic_year import AcademicYear, SemesterPeriod
from common.schemas.auth.role_schemas import (
    RoleCreateSchema,
    RoleResponse,
    RoleUpdateSchema,
)
from common.schemas.master.academic_year import (
    AcademicYearResponse,
    AcademicYearSchema,
    UpdateAcademicYearSchema,
)
from components.db.db import get_db_session
from components.generator.routes import create_crud_routes
from components.middleware import is_superadmin
from typing import List
from common.schemas.master_schemas import (
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
    SemesterPeriodCreate,
    SemesterPeriodResponse,
    SemesterPeriodUpdate,
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


role_router = APIRouter()

role_crud = create_crud_routes(
    Role,
    RoleCreateSchema,
    RoleUpdateSchema,
    RoleResponse,
    RoleResponse,
    decorators=[is_superadmin],
)
role_router.include_router(role_crud, prefix="/roles", tags=["Role"])

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
