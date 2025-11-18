from common.models.admission.consultancy import Consultancy
from common.schemas.admission.consultancy import (
    ConsultancyCreate,
    ConsultancyResponse,
    ConsultancyUpdate,
)
from components.db.db import get_db_session
from fastapi import APIRouter, Depends

from components.generator.routes import create_crud_routes
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.admission.admission_entry import AdmissionStudent
from common.schemas.admission.admission_entry import AdmissionStudentCreate, AdmissionStudentResponse, AdmissionStudentUpdate
from sqlalchemy import select

consultancy_router = APIRouter()

consultancy_crud_router = create_crud_routes(
    Consultancy,
    ConsultancyCreate,
    ConsultancyUpdate,
    ConsultancyResponse,
)

consultancy_router.include_router(
    consultancy_crud_router, prefix="/consultancies", tags=["Admission - Consultancies"]
)


admission_entry_router = APIRouter()

admission_entry_crud_router = create_crud_routes(
    AdmissionStudent,
    AdmissionStudentCreate,
    AdmissionStudentUpdate,
    AdmissionStudentResponse,
    AdmissionStudentResponse
)

admission_entry_router.include_router(
    admission_entry_crud_router, prefix="/admission-students", tags=["Admission - Admission Students"]
)


admission_router = APIRouter()

@admission_router.get("/applied", tags=["Admission - Admission Students"])
async def get_applied_admission_students(
    db: AsyncSession = Depends(get_db_session)
):
    """Get all admission students with status 'APPLIED'."""
    result = await db.execute(
        select(AdmissionStudent).where(AdmissionStudent.status == "APPLIED")
    )
    return result.scalars().all()