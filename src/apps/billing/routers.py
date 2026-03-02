from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from components.db.db import get_db_session
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from components.generator.routes import create_crud_routes
from common.models.billing.application_fees import FeeHead
from common.schemas.billing.fee_head_schemas import (
    FeeHeadCreate,
    FeeHeadUpdate,
    FeeHeadResponse,
)

# paginate import removed since not used here
from common.schemas.billing.invoice_schemas import (
    InvoiceCreate,
    InvoiceResponse,
    PaymentCreate,
    PaymentResponse,
)
from common.models.billing.application_fees import Invoice
from apps.billing.services import billing_service

router = APIRouter()


# Fee Head CRUD
fee_head_crud = create_crud_routes(
    model=FeeHead,
    CreateSchema=FeeHeadCreate,
    UpdateSchema=FeeHeadUpdate,
    AllResponseSchema=FeeHeadResponse,
)

router.include_router(fee_head_crud, prefix="/fee-heads", tags=["Billing - Fee Heads"])

# Financial Year CRUD
from common.models.billing.financial_year import FinancialYear
from common.schemas.billing.financial_year_schemas import (
    FinancialYearCreate,
    FinancialYearUpdate,
    FinancialYearResponse,
)

financial_year_crud = create_crud_routes(
    model=FinancialYear,
    CreateSchema=FinancialYearCreate,
    UpdateSchema=FinancialYearUpdate,
    AllResponseSchema=FinancialYearResponse,
)

router.include_router(
    financial_year_crud, prefix="/financial-years", tags=["Billing - Financial Years"]
)


@router.post(
    "/financial-years/{fy_id}/activate",
    response_model=FinancialYearResponse,
    tags=["Billing - Financial Years"],
)
async def activate_financial_year(
    fy_id: str, db: AsyncSession = Depends(get_db_session)
):
    try:
        fy = await billing_service.set_active_financial_year(db, fy_id)
        return fy
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/financial-years/active",
    response_model=FinancialYearResponse,
    tags=["Billing - Financial Years"],
)
async def get_active_financial_year(
    institution_id: str, db: AsyncSession = Depends(get_db_session)
):
    stmt = select(FinancialYear).where(
        FinancialYear.institution_id == institution_id, FinancialYear.active.is_(True)
    )
    result = await db.execute(stmt)
    fy = result.scalar_one_or_none()
    if not fy:
        raise HTTPException(
            status_code=404, detail="Active financial year not found for institution"
        )
    return fy


# Fee SubHeads CRUD
from common.models.billing.fee_subhead import FeeSubHead
from common.schemas.billing.fee_subhead_schemas import (
    FeeSubHeadCreate,
    FeeSubHeadUpdate,
    FeeSubHeadResponse,
)

fee_subhead_crud = create_crud_routes(
    model=FeeSubHead,
    CreateSchema=FeeSubHeadCreate,
    UpdateSchema=FeeSubHeadUpdate,
    AllResponseSchema=FeeSubHeadResponse,
)

router.include_router(
    fee_subhead_crud, prefix="/fee-subheads", tags=["Billing - Fee SubHeads"]
)

# Fee Structures CRUD
from common.models.billing.fee_structure import FeeStructure
from common.schemas.billing.fee_structure_schemas import (
    FeeStructureCreate,
    FeeStructureUpdate,
    FeeStructureResponse,
)

fee_structure_crud = create_crud_routes(
    model=FeeStructure,
    CreateSchema=FeeStructureCreate,
    UpdateSchema=FeeStructureUpdate,
    AllResponseSchema=FeeStructureResponse,
)

router.include_router(
    fee_structure_crud, prefix="/fee-structures", tags=["Billing - Fee Structures"]
)

# Custom endpoints
from common.schemas.billing.financial_year_schemas import FinancialYearResponse
from common.schemas.billing.fee_structure_schemas import (
    FeeStructureCreate as FeeStructureCreateSchema,
    FeeStructureResponse,
)


@router.post(
    "/financial-years/{fy_id}/activate",
    response_model=FinancialYearResponse,
    tags=["Billing - Financial Years"],
)
async def activate_financial_year(
    fy_id: str, db: AsyncSession = Depends(get_db_session)
):
    try:
        fy = await billing_service.set_active_financial_year(db, fy_id)
        return fy
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/fee-structures/create",
    response_model=FeeStructureResponse,
    tags=["Billing - Fee Structures"],
)
async def create_fee_structure(
    payload: FeeStructureCreateSchema, db: AsyncSession = Depends(get_db_session)
):
    try:
        fs = await billing_service.create_fee_structure(db, payload)
        return fs
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Search endpoints for dropdowns
@router.get(
    "/fee-heads/search",
    tags=["Billing - Fee Heads"],
)
async def search_fee_heads(query: str | None = None, institution_id: str | None = None, db: AsyncSession = Depends(get_db_session)):
    stmt = select(FeeHead)
    if institution_id:
        stmt = stmt.where(FeeHead.institution_id == institution_id)
    if query:
        stmt = stmt.where(FeeHead.name.ilike(f"%{query}%"))
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get(
    "/fee-subheads/search",
    tags=["Billing - Fee SubHeads"],
)
async def search_fee_subheads(query: str | None = None, fee_head_id: str | None = None, institution_id: str | None = None, db: AsyncSession = Depends(get_db_session)):
    stmt = select(FeeSubHead)
    if fee_head_id:
        stmt = stmt.where(FeeSubHead.fee_head_id == fee_head_id)
    if institution_id:
        stmt = stmt.where(FeeSubHead.institution_id == institution_id)
    if query:
        stmt = stmt.where(FeeSubHead.name.ilike(f"%{query}%"))
    res = await db.execute(stmt)
    return res.scalars().all()


# Demand endpoints
from common.schemas.billing.demand_schemas import (
    DemandBatchCreate,
    DemandBatchResponse,
    DemandPreviewResponse,
    GeneralDemandCreateRequest,
    GeneralDemandCreateResponse,
    ResolveGeneralDemandStudentsRequest,
    ResolveGeneralDemandStudentsResponse,
)
from common.schemas.billing.ledger_schemas import LedgerResponse


@router.post(
    "/demand-batches",
    response_model=DemandBatchResponse,
    tags=["Billing - Demands"],
)
async def create_demand_batch(payload: DemandBatchCreate, db: AsyncSession = Depends(get_db_session)):
    try:
        # Create the batch record
        batch = await billing_service.create_demand_batch(db, payload)
        # Automatically generate demands (async in a real app, strict await here)
        await billing_service.generate_demands_for_batch(db, batch.id)
        return batch
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/demand-batches/preview",
    response_model=DemandPreviewResponse,
    tags=["Billing - Demands"],
)
@router.post(
    "/demands/preview",
    response_model=DemandPreviewResponse,
    tags=["Billing - Demands"],
)
async def preview_demand_creation(
    payload: DemandBatchCreate, db: AsyncSession = Depends(get_db_session)
):
    try:
        res = await billing_service.preview_demand_batch(db, payload)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/ledgers/general",
    response_model=LedgerResponse,
    tags=["Billing - Ledger"],
    summary="General ledger for an institution with optional student filters",
)
async def get_general_ledger(
    institution_id: UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    student_id: UUID | None = None,
    degree_id: UUID | None = None,
    department_id: UUID | None = None,
    batch: str | None = None,
    gender: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await billing_service.get_general_ledger(
            db=db,
            institution_id=institution_id,
            from_date=from_date,
            to_date=to_date,
            student_id=student_id,
            degree_id=degree_id,
            department_id=department_id,
            batch=batch,
            gender=gender,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/ledgers/students/{student_id}",
    response_model=LedgerResponse,
    tags=["Billing - Ledger"],
    summary="Student-specific ledger",
)
async def get_student_ledger(
    student_id: UUID,
    from_date: date | None = None,
    to_date: date | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await billing_service.get_student_ledger(
            db=db,
            student_id=student_id,
            from_date=from_date,
            to_date=to_date,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/demand-batches/{batch_id}/generate",
    tags=["Billing - Demands"],
)
async def generate_batch(batch_id: str, dry_run: bool = False, db: AsyncSession = Depends(get_db_session)):
    try:
        res = await billing_service.generate_demands_for_batch(db, batch_id, dry_run=dry_run)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/demands/student",
    tags=["Billing - Demands"],
)
async def create_student_demand(student_id: str, fee_structure_id: str, db: AsyncSession = Depends(get_db_session)):
    try:
        from uuid import UUID

        student_uuid = UUID(student_id)
        fee_structure_uuid = UUID(fee_structure_id)
        count = await billing_service.create_student_demand(db, student_uuid, fee_structure_uuid)
        return {"created": count}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/demands/year",
    tags=["Billing - Demands"],
    summary="Create year-specific demands for multiple students"
)
async def create_year_specific_demand(
    payload: dict,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create demand items for multiple students for a specific year only.
    This is useful when you want to raise demands year by year instead of all at once.
    
    Request body:
        {
            "student_ids": ["uuid1", "uuid2"],
            "fee_structure_id": "uuid",
            "year": "1"
        }
    
    Returns:
        Created count, total amount, and success message
    """
    from common.schemas.billing.demand_year_schema import CreateYearDemandRequest, CreateYearDemandResponse
    from uuid import UUID
    
    try:
        # Extract and validate data
        student_ids_str = payload.get("student_ids", [])
        fee_structure_id_str = payload.get("fee_structure_id")
        year = payload.get("year")
        
        if not student_ids_str or not fee_structure_id_str or not year:
            raise ValueError("Missing required fields: student_ids, fee_structure_id, or year")
        
        # Convert string IDs to UUIDs
        student_uuids = [UUID(sid) for sid in student_ids_str]
        fs_uuid = UUID(fee_structure_id_str)
        
        result = await billing_service.create_year_specific_demand(
            db, student_uuids, fs_uuid, year
        )
        return CreateYearDemandResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/demands/check-status",
    tags=["Billing - Demands"],
    summary="Check if demands exist for students/year"
)
async def check_demand_status(
    payload: dict,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Check status for list of students.
    Payload: { student_ids: [], fee_structure_id: str, year: str }
    Returns: { status: { student_id: bool } }
    """
    from uuid import UUID
    try:
        student_ids_str = payload.get("student_ids", [])
        fee_structure_id_str = payload.get("fee_structure_id")
        year = payload.get("year")
        
        if not fee_structure_id_str or not year:
            return {"status": {}}
            
        student_uuids = [UUID(sid) for sid in student_ids_str]
        fs_uuid = UUID(fee_structure_id_str)
        
        status_map = await billing_service.check_year_demand_status(
            db, student_uuids, fs_uuid, year
        )
        return {"status": status_map}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/demands/students/resolve",
    response_model=ResolveGeneralDemandStudentsResponse,
    tags=["Billing - Demands"],
    summary="Resolve students by application number / roll number"
)
async def resolve_general_demand_students(
    payload: ResolveGeneralDemandStudentsRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await billing_service.resolve_students_by_identifiers(
            db=db,
            institution_id=payload.institution_id,
            identifiers=payload.identifiers,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/demands/general",
    response_model=GeneralDemandCreateResponse,
    tags=["Billing - Demands"],
    summary="Create general demand by fee head/subhead for students"
)
async def create_general_demand(
    payload: GeneralDemandCreateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await billing_service.create_general_demand(db=db, payload=payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



from common.schemas.billing.demand_schemas import BulkMiscellaneousFeeRequest

@router.post(
    "/demands/bulk-miscellaneous",
    tags=["Billing - Demands"],
    summary="Assign Miscellaneous Fees to multiple students"
)
async def bulk_miscellaneous_fees(
    payload: BulkMiscellaneousFeeRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a DemandBatch and individual DemandItems for miscellaneous fees.
    """
    from common.models.billing.demand import DemandBatch, DemandItem
    from datetime import datetime
    
    try:
        # 1. Create Batch
        batch = DemandBatch(
            name=f"Misc Fee: {payload.description}",
            institution_id=None, # Warning: Batch needs institution_id usually. 
            # We must fetch an institution_id from one of the students or require it in payload.
            # Let's assume payload.student_ids[0] has existing institution.
            # Better approach: Add institution_id to payload.
            # Update Plan? Or just infer.
            # Let's infer from the first student for now to proceed, but ideally payload should have it.
            # I will assume checking first student.
            status="generated",
            generated_at=datetime.utcnow()
        )
        
        # We need institution_id. Let's fetch first student.
        from common.models.admission.admission_entry import AdmissionStudent
        if not payload.student_ids:
            return {"message": "No students provided"}
            
        stmt = select(AdmissionStudent.institution_id).where(AdmissionStudent.id == payload.student_ids[0])
        res = await db.execute(stmt)
        inst_id = res.scalar_one_or_none()
        
        if not inst_id:
             raise HTTPException(status_code=400, detail="Could not determine institution from students")
             
        batch.institution_id = inst_id # type: ignore
        # Note: We need null checks for fee_structure_id etc as they are nullable.
        
        db.add(batch)
        await db.flush()
        
        # 2. Create items
        count = 0
        for sid in payload.student_ids:
            di = DemandItem(
                batch_id=batch.id,
                student_id=sid,
                amount=payload.amount,
                description=payload.description,
                fee_head_id=payload.fee_head_id,
                status="pending"
            )
            db.add(di)
            count += 1
            
        await db.commit()
        return {"batch_id": batch.id, "created_count": count}
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# --- Hostel Fee Structures ---
from common.models.billing.hostel import HostelFeeStructure, HostelRoom
from common.schemas.billing.hostel_schemas import (
    HostelFeeStructureCreate,
    HostelFeeStructureUpdate,
    HostelFeeStructureResponse,
    HostelRoomCreate,
    HostelRoomResponse,
)

hostel_fee_crud = create_crud_routes(
    model=HostelFeeStructure,
    CreateSchema=HostelFeeStructureCreate,
    UpdateSchema=HostelFeeStructureUpdate,
    AllResponseSchema=HostelFeeStructureResponse,
)
router.include_router(hostel_fee_crud, prefix="/hostel/structures", tags=["Billing - Hostel Fees"])

hostel_room_crud = create_crud_routes(
    model=HostelRoom,
    CreateSchema=HostelRoomCreate,
    UpdateSchema=HostelRoomCreate,
    AllResponseSchema=HostelRoomResponse,
)
router.include_router(hostel_room_crud, prefix="/hostel/rooms", tags=["Billing - Hostel Fees"])


# --- Transport Routes & Fees ---
from common.models.billing.transport import TransportRoute, TransportBus, TransportFeeStructure
from common.schemas.billing.transport_schemas import (
    TransportRouteCreate,
    TransportRouteResponse,
    TransportBusCreate,
    TransportBusResponse,
    TransportFeeStructureCreate,
    TransportFeeStructureResponse,
)

transport_route_crud = create_crud_routes(
    model=TransportRoute,
    CreateSchema=TransportRouteCreate,
    UpdateSchema=TransportRouteCreate,
    AllResponseSchema=TransportRouteResponse,
)
router.include_router(transport_route_crud, prefix="/transport/routes", tags=["Billing - Transport"])

transport_bus_crud = create_crud_routes(
    model=TransportBus,
    CreateSchema=TransportBusCreate,
    UpdateSchema=TransportBusCreate,
    AllResponseSchema=TransportBusResponse,
)
router.include_router(transport_bus_crud, prefix="/transport/buses", tags=["Billing - Transport"])

transport_fee_crud = create_crud_routes(
    model=TransportFeeStructure,
    CreateSchema=TransportFeeStructureCreate,
    UpdateSchema=TransportFeeStructureCreate,
    AllResponseSchema=TransportFeeStructureResponse,
)
router.include_router(transport_fee_crud, prefix="/transport/structures", tags=["Billing - Transport"])


# --- Concessions ---
from common.models.billing.concession import Concession
from common.schemas.billing.concession_schemas import (
    ConcessionCreate,
    ConcessionUpdate,
    ConcessionResponse,
)

concession_crud = create_crud_routes(
    model=Concession,
    CreateSchema=ConcessionCreate,
    UpdateSchema=ConcessionUpdate,
    AllResponseSchema=ConcessionResponse,
)
router.include_router(concession_crud, prefix="/concessions", tags=["Billing - Concessions"])

@router.post("/concessions/{concession_id}/approve", tags=["Billing - Concessions"])
async def approve_concession(concession_id: str, approver_id: str | None = None, db: AsyncSession = Depends(get_db_session)):
    try:
        res = await billing_service.approve_concession(db, concession_id, approver_id)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Payment Recall Requests ---
from common.models.billing.recall import PaymentRecallRequest
from common.schemas.billing.recall_schemas import (
    PaymentRecallRequestCreate,
    PaymentRecallRequestResponse,
)

recall_crud = create_crud_routes(
    model=PaymentRecallRequest,
    CreateSchema=PaymentRecallRequestCreate,
    UpdateSchema=PaymentRecallRequestCreate,
    AllResponseSchema=PaymentRecallRequestResponse,
)
router.include_router(recall_crud, prefix="/payments/recall", tags=["Billing - Recall"])

@router.post("/payments/recall/{recall_id}/process", tags=["Billing - Recall"])
async def process_recall(recall_id: str, approve: bool = False, processor_id: str | None = None, db: AsyncSession = Depends(get_db_session)):
    try:
        pr = await billing_service.process_payment_recall(db, recall_id, processor_id, approve=approve)
        return pr
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Cash Counter Operations ---
from common.schemas.billing.cash_counter_schemas import (
    StudentDuesResponse,
    CashCounterPaymentRequest,
)

@router.get(
    "/cash-counters/search",
    response_model=StudentDuesResponse,
    tags=["Billing - Cash Counters"],
    summary="Search student dues by application number"
)
async def search_student_dues(
    application_number: str,
    db: AsyncSession = Depends(get_db_session)
):
    try:
        return await billing_service.get_student_dues_by_application_number(db, application_number)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/cash-counters/pay",
    tags=["Billing - Cash Counters"],
    summary="Accept payment at cash counter"
)
async def cash_counter_pay(
    request: Request,
    payload: CashCounterPaymentRequest,
    db: AsyncSession = Depends(get_db_session)
):
    try:
        # Determine counter_id if available (e.g. from token)
        counter_id = None
        if hasattr(request, "state") and hasattr(request.state, "auth_payload"):
             counter_id = request.state.auth_payload.get("counter_id")

        # Reuse existing apply_payment service
        # Map CashCounterPaymentRequest to PaymentCreate
        payment_create = PaymentCreate(
            amount=payload.amount,
            payment_method=payload.payment_method,
            notes=payload.notes,
            transaction_id=None, # Auto-generate or optional
            receipt_number=None, # Auto-generate
        )
        
        return await billing_service.apply_payment(
            db, 
            invoice_id=payload.invoice_id, 
            payload=payment_create, 
            counter_id=counter_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Cash Counters CRUD (Generic /{id} routes must be last) ---
from common.models.billing.cash_counter import CashCounter
from common.schemas.billing.cash_counter_schemas import (
    CashCounterCreate,
    CashCounterUpdate,
    CashCounterResponse,
)

cash_counter_crud = create_crud_routes(
    model=CashCounter,
    CreateSchema=CashCounterCreate,
    UpdateSchema=CashCounterUpdate,
    AllResponseSchema=CashCounterResponse,
)
router.include_router(cash_counter_crud, prefix="/cash-counters", tags=["Billing - Cash Counters"])
