from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from apps.master.services import MasterService
from common.schemas.master.academic_year import AcademicYearResponse, AcademicYearSchema, UpdateAcademicYearSchema
from components.db.db import get_db_session
from components.middleware import is_superadmin
from typing import List
from uuid import UUID
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
)

# Router
# Institution Router
institution_router = APIRouter(prefix="/institutions", tags=["Institution"])


@institution_router.post(
    "", response_model=InstitutionResponse, summary="Create a new institution"
)
@is_superadmin
async def create_institution(
    request: Request,
    data: InstitutionCreate,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new institution."""
    return await MasterService(db).create_institution(data)


@institution_router.get(
    "",  summary="List all institutions"
)
@is_superadmin
async def list_institutions(
    request: Request, db: AsyncSession = Depends(get_db_session)
):
    """Get a list of all institutions."""
    return await MasterService(db).list_institutions()


@institution_router.get(
    "/{institution_id}",
    response_model=InstitutionResponse,
    summary="Get institution by ID",
)
@is_superadmin
async def get_institution(
    request: Request, institution_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """Get details of a specific institution by ID."""
    return await MasterService(db).get_institution(institution_id)


@institution_router.put(
    "/{institution_id}",
    response_model=InstitutionResponse,
    summary="Update institution by ID",
)
@is_superadmin
async def update_institution(
    request: Request,
    institution_id: UUID,
    data: InstitutionUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update an existing institution by ID."""
    return await MasterService(db).update_institution(institution_id, data)


@institution_router.delete("/{institution_id}", summary="Delete institution by ID")
@is_superadmin
async def delete_institution(
    request: Request, institution_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """Delete an institution by ID."""
    return await MasterService(db).delete_institution(institution_id)


# Department Router
department_router = APIRouter(prefix="/departments", tags=["Department"])


@department_router.post(
    "", response_model=DepartmentResponse, summary="Create a new department"
)
@is_superadmin
async def create_department(
    request: Request, data: DepartmentCreate, db: AsyncSession = Depends(get_db_session)
):
    """Create a new department."""
    return await MasterService(db).create_department(data)


@department_router.get(
    "", response_model=List[DepartmentResponse], summary="List all departments"
)
@is_superadmin
async def list_departments(
    request: Request, db: AsyncSession = Depends(get_db_session)
):
    """Get a list of all departments."""
    return await MasterService(db).list_departments()


@department_router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Get department by ID",
)
@is_superadmin
async def get_department(
    request: Request, department_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """Get details of a specific department by ID."""
    return await MasterService(db).get_department(department_id)


@department_router.put(
    "/{department_id}",
    response_model=DepartmentResponse,
    summary="Update department by ID",
)
@is_superadmin
async def update_department(
    request: Request,
    department_id: UUID,
    data: DepartmentUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update an existing department by ID."""
    return await MasterService(db).update_department(department_id, data)


@department_router.delete("/{department_id}", summary="Delete department by ID")
@is_superadmin
async def delete_department(
    request: Request, department_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """Delete a department by ID."""
    return await MasterService(db).delete_department(department_id)


# Course Router
course_router = APIRouter(prefix="/courses", tags=["Course"])


@course_router.post("", response_model=CourseResponse, summary="Create a new course")
@is_superadmin
async def create_course(
    request: Request, data: CourseCreate, db: AsyncSession = Depends(get_db_session)
):
    """Create a new course."""
    return await MasterService(db).create_course(data)


@course_router.get("", response_model=List[CourseResponse], summary="List all courses")
@is_superadmin
async def list_courses(request: Request, db: AsyncSession = Depends(get_db_session)):
    """Get a list of all courses."""
    return await MasterService(db).list_courses()


@course_router.get(
    "/{course_id}", response_model=CourseResponse, summary="Get course by ID"
)
@is_superadmin
async def get_course(
    request: Request, course_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """Get details of a specific course by ID."""
    return await MasterService(db).get_course(course_id)


@course_router.put(
    "/{course_id}", response_model=CourseResponse, summary="Update course by ID"
)
@is_superadmin
async def update_course(
    request: Request,
    course_id: UUID,
    data: CourseUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update an existing course by ID."""
    return await MasterService(db).update_course(course_id, data)


@course_router.delete("/{course_id}", summary="Delete course by ID")
@is_superadmin
async def delete_course(
    request: Request, course_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """Delete a course by ID."""
    return await MasterService(db).delete_course(course_id)


# Class Router
class_router = APIRouter(prefix="/classes", tags=["Class"])


@class_router.post("", response_model=ClassResponse, summary="Create a new class")
@is_superadmin
async def create_class(
    request: Request, data: ClassCreate, db: AsyncSession = Depends(get_db_session)
):
    """Create a new class."""
    return await MasterService(db).create_class(data)


@class_router.get("", response_model=List[ClassResponse], summary="List all classes")
@is_superadmin
async def list_classes(request: Request, db: AsyncSession = Depends(get_db_session)):
    """Get a list of all classes."""
    return await MasterService(db).list_classes()


@class_router.get(
    "/{class_id}", response_model=ClassResponse, summary="Get class by ID"
)
@is_superadmin
async def get_class(
    request: Request, class_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """Get details of a specific class by ID."""
    return await MasterService(db).get_class(class_id)


@class_router.put(
    "/{class_id}", response_model=ClassResponse, summary="Update class by ID"
)
@is_superadmin
async def update_class(
    request: Request,
    class_id: UUID,
    data: ClassUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update an existing class by ID."""
    return await MasterService(db).update_class(class_id, data)


@class_router.delete("/{class_id}", summary="Delete class by ID")
@is_superadmin
async def delete_class(
    request: Request, class_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """Delete a class by ID."""
    return await MasterService(db).delete_class(class_id)


academic_year_router = APIRouter(prefix="/academic-years", tags=["Academic Years"])


@academic_year_router.post(
    "",
    status_code=201,
    name="Create Academic Year",
    description="Create a new academic year",
)
@is_superadmin
async def create_academic_year(
    request: Request,
    data: AcademicYearSchema,
    db: AsyncSession = Depends(get_db_session),
):
    return await MasterService(db).create_academic_year(data)


@academic_year_router.get(
    "",
    response_model=List[AcademicYearResponse],
    name="List Academic Years",
    description="Get a list of all academic years",
)
async def list_academic_years(
    request: Request, db: AsyncSession = Depends(get_db_session)
):
    """Get a list of all academic years."""
    return await MasterService(db).list_academic_years()

@academic_year_router.get(
    "/{academic_year_id}",
    response_model=AcademicYearResponse,
    name="Get Academic Year",
    description="Get details of a specific academic year by ID",
)
async def get_academic_year(
    request: Request, academic_year_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """Get details of a specific academic year by ID."""
    return await MasterService(db).get_academic_year(academic_year_id)

@academic_year_router.put(
    "/{academic_year_id}",
    response_model=UpdateAcademicYearSchema,
    name="Update Academic Year",
    description="Update an existing academic year by ID",
)
@is_superadmin
async def update_academic_year(
    request: Request,
    academic_year_id: UUID,
    data: UpdateAcademicYearSchema,
    db: AsyncSession = Depends(get_db_session),
):
    """Update an existing academic year by ID."""
    return await MasterService(db).update_academic_year(academic_year_id, data)

@academic_year_router.delete(
    "/{academic_year_id}",
    name="Delete Academic Year",
    description="Delete an academic year by ID",
)
@is_superadmin
async def delete_academic_year( 
    request: Request, academic_year_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """Delete an academic year by ID."""
    return await MasterService(db).delete_academic_year(academic_year_id)