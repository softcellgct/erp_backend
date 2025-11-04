from uuid import UUID
from common.models.gate.visitor_model import AdmissionVisitor
from components.db.db import get_db_session
from fastapi import APIRouter, Depends, Request
from components.middleware import is_superadmin
from components.generator.routes import create_crud_routes
from common.models import Visitor, PersonType
from common.schemas.gate.visitor_schemas import (
    PersonTypeCreate,
    PersonTypeUpdate,
    PersonTypeResponse,
    VisitorCreate,
    VisitorUpdate,
    VisitorResponse,
)
from common.schemas.gate.admission_visitor import (
    AdmissionVisitorCreate,
    AdmissionVisitorUpdate,
    AdmissionVisitorRead,
)
from fastapi_pagination import Page, add_pagination
from fastapi_querybuilder import QueryBuilder
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get(
    "/check",
    name="Health Check",
    description="A simple health check endpoint to verify the service is running.",
)
def check(request: Request):
    return {"status": "ok", "request": request}


# =====================================================
# Person Type CRUD Routes
# =====================================================
person_type_router = APIRouter()
person_type_crud = create_crud_routes(
    PersonType,
    CreateSchema=PersonTypeCreate,
    UpdateSchema=PersonTypeUpdate,
    AllResponseSchema=PersonTypeResponse,
    IdResponseSchema=PersonTypeResponse,
    decorators=[is_superadmin],
)
person_type_router.include_router(
    person_type_crud, prefix="/person-types", tags=["Gate - Person Types"]
)


# =====================================================
# Visitor CRUD Routes
# =====================================================
visitor_router = APIRouter()
visitor_crud = create_crud_routes(
    Visitor,
    CreateSchema=VisitorCreate,
    UpdateSchema=VisitorUpdate,
    AllResponseSchema=VisitorResponse,
    IdResponseSchema=VisitorResponse,
)
visitor_router.include_router(
    visitor_crud, prefix="/visitors", tags=["Gate - Visitors"]
)


from .services import admission_crud

admission_visitor_router = APIRouter(
    prefix="/admission-visitors",
    tags=["Gate - Admission Visitors"],
)

@admission_visitor_router.post(
    "",
    name="Create Admission Visitor",
    description="Create a new admission visitor record.",
)
async def create_admission_visitor(
    request: Request,
    payload: AdmissionVisitorCreate,
    db: AsyncSession = Depends(get_db_session),
):
        visitor = await admission_crud.create(db, payload)
        return visitor

@admission_visitor_router.get(
    "/{visitor_id}",
    response_model=AdmissionVisitorRead,
    name="Get Admission Visitor",
    description="Retrieve an admission visitor record by ID.",
)
async def get_admission_visitor(
    request: Request,
    visitor_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
        visitor = await admission_crud.get_one(db, visitor_id)
        return visitor

@admission_visitor_router.get(
    "",
    response_model=Page[AdmissionVisitorRead],
    name="Get All Admission Visitors",
    description="Retrieve all admission visitor records.",
)
async def get_all_admission_visitors(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    query = QueryBuilder(AdmissionVisitor),
):
    visitors = await admission_crud.get_all(db, query)
    return visitors


add_pagination(admission_visitor_router)