from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
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
router = APIRouter()

# Institution CRUD
@router.post("/institutions", response_model=InstitutionResponse)
@is_superadmin
async def create_institution(request: Request, data: InstitutionCreate, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).create_institution(data)

@router.get("/institutions", response_model=List[InstitutionResponse])
@is_superadmin
async def list_institutions(request: Request, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).list_institutions()

@router.get("/institutions/{institution_id}", response_model=InstitutionResponse)
@is_superadmin
async def get_institution(request: Request, institution_id: UUID, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).get_institution(institution_id)

@router.put("/institutions/{institution_id}", response_model=InstitutionResponse)
@is_superadmin
async def update_institution(request: Request, institution_id: UUID, data: InstitutionUpdate, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).update_institution(institution_id, data)

@router.delete("/institutions/{institution_id}")
@is_superadmin
async def delete_institution(request: Request, institution_id: UUID, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).delete_institution(institution_id)

# Department CRUD
@router.post("/departments", response_model=DepartmentResponse)
@is_superadmin
async def create_department(request: Request, data: DepartmentCreate, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).create_department(data)

@router.get("/departments", response_model=List[DepartmentResponse])
@is_superadmin
async def list_departments(request: Request, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).list_departments()

@router.get("/departments/{department_id}", response_model=DepartmentResponse)
@is_superadmin
async def get_department(request: Request, department_id: UUID, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).get_department(department_id)

@router.put("/departments/{department_id}", response_model=DepartmentResponse)
@is_superadmin
async def update_department(request: Request, department_id: UUID, data: DepartmentUpdate, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).update_department(department_id, data)

@router.delete("/departments/{department_id}")
@is_superadmin
async def delete_department(request: Request, department_id: UUID, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).delete_department(department_id)

# Course CRUD
@router.post("/courses", response_model=CourseResponse)
@is_superadmin
async def create_course(request: Request, data: CourseCreate, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).create_course(data)

@router.get("/courses", response_model=List[CourseResponse])
@is_superadmin
async def list_courses(request: Request, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).list_courses()

@router.get("/courses/{course_id}", response_model=CourseResponse)
@is_superadmin
async def get_course(request: Request, course_id: UUID, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).get_course(course_id)

@router.put("/courses/{course_id}", response_model=CourseResponse)
@is_superadmin
async def update_course(request: Request, course_id: UUID, data: CourseUpdate, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).update_course(course_id, data)

@router.delete("/courses/{course_id}")
@is_superadmin
async def delete_course(request: Request, course_id: UUID, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).delete_course(course_id)

# Class CRUD
@router.post("/classes", response_model=ClassResponse)
@is_superadmin
async def create_class(request: Request, data: ClassCreate, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).create_class(data)

@router.get("/classes", response_model=List[ClassResponse])
@is_superadmin
async def list_classes(request: Request, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).list_classes()

@router.get("/classes/{class_id}", response_model=ClassResponse)
@is_superadmin
async def get_class(request: Request, class_id: UUID, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).get_class(class_id)

@router.put("/classes/{class_id}", response_model=ClassResponse)
@is_superadmin
async def update_class(request: Request, class_id: UUID, data: ClassUpdate, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).update_class(class_id, data)

@router.delete("/classes/{class_id}")
@is_superadmin
async def delete_class(request: Request, class_id: UUID, db: AsyncSession = Depends(get_db_session)):
    from apps.master.services import MasterService
    return await MasterService(db).delete_class(class_id)