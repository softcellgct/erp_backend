from common.models.admission.consultancy import Consultancy
from common.schemas.admission.consultancy import (
    ConsultancyCreate,
    ConsultancyResponse,
    ConsultancyUpdate,
)
from fastapi import APIRouter

from components.generator.routes import create_crud_routes


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
