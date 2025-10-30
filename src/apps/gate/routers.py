from fastapi import APIRouter, Request
from components.middleware import public_route, is_superadmin
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
