from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from apps.master.services.institution import InstitutionService
from common.models.master.institution import Institution, Department, Course, Class, Hostel
from common.schemas.master.institution import (
    InstitutionCreate, InstitutionUpdate, InstitutionResponse,
    DepartmentCreate, DepartmentUpdate, DepartmentResponse,
    CourseCreate, CourseUpdate, CourseResponse,
    ClassCreate, ClassUpdate, ClassResponse,
    HostelCreate, HostelUpdate, HostelResponse
)
from components.db.db import get_db_session
from components.generator.routes import create_crud_routes
from components.middleware import is_superadmin

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

@institution_router.get(
    "/list", response_model=List[InstitutionResponse], tags=["Institution"]
)
@is_superadmin
async def get_institutions_list(
    request: Request, db: AsyncSession = Depends(get_db_session)
):
    """Get a simple list of all institutions."""
    return await InstitutionService(db).list_institutions()


# Department Router
department_router = APIRouter()

@department_router.get("/departments/list", response_model=List[DepartmentResponse], tags=["Department"])
@is_superadmin
async def list_departments_legacy(
    request: Request,
    academic_year_id: str | None = None,
    db: AsyncSession = Depends(get_db_session)
):
    """Legacy compatibility endpoint kept for older clients (calls same service)."""
    return await InstitutionService(db).list_departments(academic_year_id)

@department_router.get("/departments/academic-year", response_model=List[DepartmentResponse], tags=["Department"])
@is_superadmin
async def list_departments_by_academic_year(
    request: Request,
    academic_year_id: str | None = None,
    db: AsyncSession = Depends(get_db_session)
):
    """Get departments filtered by academic year (avoid collision with /{id})."""
    return await InstitutionService(db).list_departments(academic_year_id)

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


# Hostel Router
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

@hostel_router.get("/list", response_model=List[HostelResponse], tags=["Hostels"])
@is_superadmin
async def list_hostels(institution_id: str | None = None, db: AsyncSession = Depends(get_db_session)):
    return await InstitutionService(db).list_hostels(institution_id)
