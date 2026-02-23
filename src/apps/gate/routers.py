from datetime import date
from urllib.parse import unquote
from uuid import UUID

from common.models.gate.visitor_model import AdmissionVisitor, VisitStatus
from components.db.db import get_db_session
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
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
    AdmissionVisitorPassOutRequest,
    AdmissionVisitorPassOutResponse,
    AdmissionVisitorReportResponse,
    AdmissionVisitorUpdate,
    AdmissionVisitorRead,
)
from fastapi_pagination import Page, add_pagination
from sqlalchemy.ext.asyncio import AsyncSession
from io import BytesIO

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
from components.utils.query_builder import SafeQueryBuilder

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
    "/by-pass/{gate_pass_no:path}",
    response_model=AdmissionVisitorRead,
    name="Get Admission Visitor By Gate Pass Number",
    description="Retrieve an admission visitor record by gate pass number.",
)
async def get_admission_visitor_by_gate_pass(
    request: Request,
    gate_pass_no: str,
    db: AsyncSession = Depends(get_db_session),
):
    decoded_gate_pass_no = unquote(gate_pass_no).strip()
    visitor = await admission_crud.get_by_gate_pass_no(db, decoded_gate_pass_no)
    if not visitor:
        raise HTTPException(status_code=404, detail="Admission visitor not found")
    return visitor


@admission_visitor_router.post(
    "/{visitor_id}/pass-out",
    response_model=AdmissionVisitorPassOutResponse,
    name="Pass Out Admission Visitor",
    description="Mark an admission visitor as checked out.",
)
async def pass_out_admission_visitor(
    request: Request,
    visitor_id: UUID,
    payload: AdmissionVisitorPassOutRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        visitor, already_checked_out = await admission_crud.pass_out(
            db, visitor_id, payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not visitor:
        raise HTTPException(status_code=404, detail="Admission visitor not found")
    return {"visitor": visitor, "already_checked_out": already_checked_out}


@admission_visitor_router.get(
    "/reports",
    response_model=AdmissionVisitorReportResponse,
    name="Get Admission Visitor Reports",
    description="Get admission visitor report rows with summary counts.",
)
async def get_admission_visitor_reports(
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    visit_status: VisitStatus | None = Query(default=None),
    institution_id: UUID | None = Query(default=None),
    reference_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
):
    return await admission_crud.get_report(
        db,
        date_from=date_from,
        date_to=date_to,
        visit_status=visit_status,
        institution_id=institution_id,
        reference_type=reference_type,
        search=search,
        page=page,
        size=size,
    )


@admission_visitor_router.get(
    "/reports/export",
    name="Export Admission Visitor Reports CSV",
    description="Export admission visitor reports as CSV.",
)
async def export_admission_visitor_reports(
    request: Request,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    visit_status: VisitStatus | None = Query(default=None),
    institution_id: UUID | None = Query(default=None),
    reference_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
):
    csv_text, filename = await admission_crud.export_report_csv(
        db,
        date_from=date_from,
        date_to=date_to,
        visit_status=visit_status,
        institution_id=institution_id,
        reference_type=reference_type,
        search=search,
    )
    stream = BytesIO(csv_text.encode("utf-8"))
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(stream, media_type="text/csv", headers=headers)


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
    if not visitor:
        raise HTTPException(status_code=404, detail="Admission visitor not found")
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
    query = SafeQueryBuilder(
        AdmissionVisitor,
        searchable_fields=[
            "student_name",
            "gate_pass_no",
            "mobile_number",
            "parent_or_guardian_name",
            "aadhar_number",
            "native_place",
            "vehicle_number",
            "reference_type",
        ],
    ),

):
    visitors = await admission_crud.get_all(db, query)
    return visitors


add_pagination(admission_visitor_router)
