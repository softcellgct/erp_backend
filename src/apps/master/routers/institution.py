from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from apps.master.services.institution import InstitutionService
from common.models.master.institution import Institution, Department, Course, Class, Hostel, Staff
from common.schemas.master.institution import (
    InstitutionCreate, InstitutionUpdate, InstitutionResponse,
    DepartmentCreate, DepartmentUpdate, DepartmentResponse,
    CourseCreate, CourseUpdate, CourseResponse,
    ClassCreate, ClassUpdate, ClassResponse,
    HostelCreate, HostelUpdate, HostelResponse,
    StaffCreate, StaffUpdate, StaffResponse
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
    apply_decorators_on_read=False,
)
institution_router.include_router(
    institution_crud, prefix="/institutions", tags=["Institution"]
)

@institution_router.get(
    "/list", response_model=List[InstitutionResponse], tags=["Institution"]
)
async def get_institutions_list(
    request: Request, db: AsyncSession = Depends(get_db_session)
):
    """Get a simple list of all institutions."""
    return await InstitutionService(db).list_institutions()


# Department Router
department_router = APIRouter()

# ========== Specific routes (registered BEFORE CRUD) ==========

@department_router.get("/departments/by-institution", response_model=List[DepartmentResponse], tags=["Department"])
async def list_departments_by_institution(
    request: Request,
    institution_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get active departments filtered by institution."""
    from uuid import UUID as PyUUID
    return await InstitutionService(db).list_departments_by_institution(PyUUID(institution_id))

@department_router.get("/departments/list", response_model=List[DepartmentResponse], tags=["Department"])
async def list_departments_legacy(
    request: Request,
    academic_year_id: str | None = None,
    db: AsyncSession = Depends(get_db_session)
):
    """Legacy compatibility endpoint kept for older clients (calls same service)."""
    return await InstitutionService(db).list_departments(academic_year_id)

@department_router.get("/departments/academic-year", response_model=List[DepartmentResponse], tags=["Department"])
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
    apply_decorators_on_read=False,
)
department_router.include_router(
    department_crud, prefix="/departments", tags=["Department"]
)


# Course Router
course_router = APIRouter()

@course_router.get("/courses/by-department", response_model=List[CourseResponse], tags=["Course"])
async def list_courses_by_department(
    request: Request,
    department_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get active courses filtered by department."""
    from uuid import UUID as PyUUID
    return await InstitutionService(db).list_courses_by_department(PyUUID(department_id))

course_crud = create_crud_routes(
    Course,
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    CourseResponse,
    decorators=[is_superadmin],
    apply_decorators_on_read=False,
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
    apply_decorators_on_read=False,
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
    apply_decorators_on_read=False,
)
hostel_router.include_router(hostel_crud, prefix="/hostels", tags=["Hostels"])

@hostel_router.get("/list", response_model=List[HostelResponse], tags=["Hostels"])
async def list_hostels(institution_id: str | None = None, db: AsyncSession = Depends(get_db_session)):
    return await InstitutionService(db).list_hostels(institution_id)


# Staff Router
staff_router = APIRouter()
staff_crud = create_crud_routes(
    Staff,
    StaffCreate,
    StaffUpdate,
    StaffResponse,
    StaffResponse,
    decorators=[is_superadmin],
    apply_decorators_on_read=False,
)
staff_router.include_router(staff_crud, prefix="/staff", tags=["Staff"])

@staff_router.get("/staff/by-department/{department_id}", response_model=List[StaffResponse], tags=["Staff"])
async def list_staff_by_department(
    request: Request,
    department_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get staff members filtered by department."""
    from sqlalchemy import select
    stmt = select(Staff).where(
        Staff.department_id == department_id,
        Staff.deleted_at.is_(None),
    ).order_by(Staff.name)
    result = await db.execute(stmt)
    return result.scalars().all()
