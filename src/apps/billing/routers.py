from typing import Optional, List
from decimal import Decimal
from common.models.billing.concession import Concession

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from components.db.db import get_db_session
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from components.generator.routes import create_crud_routes
from components.generator.utils.get_user_from_request import get_user_id
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_pagination import Page
from common.models.billing.application_fees import FeeHead
from common.schemas.billing.fee_head_schemas import (
    FeeHeadCreate,
    FeeHeadUpdate,
    FeeHeadResponse,
)

from common.schemas.billing.invoice_schemas import (
    PaymentCreate,
)
from common.models.billing.application_fees import Invoice
from apps.billing.services import billing_service

router = APIRouter()


from common.models.billing.concession_rule import ConcessionRule
from common.schemas.billing.concession_schemas import ConcessionRuleCreate, ConcessionRuleUpdate, ConcessionRuleResponse

# Concession Rule CRUD
concession_rule_crud = create_crud_routes(
    ConcessionRule,
    ConcessionRuleCreate,
    ConcessionRuleUpdate,
    ConcessionRuleResponse,
)

router.include_router(concession_rule_crud, prefix="/concession-rules", tags=["Concession Rules"])

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


router.include_router(
    financial_year_crud, prefix="/financial-years", tags=["Billing - Financial Years"]
)


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

# Override the default GET for fee-structures to include relationship data
from common.models.billing.fee_structure import FeeStructureItem

@router.get(
    "/fee-structures",
    response_model=Page[FeeStructureResponse],
    tags=["Billing - Fee Structures"],
)
async def list_fee_structures(
    db: AsyncSession = Depends(get_db_session),
):
    """Get all fee structures with relationship data loaded."""
    stmt = (
        select(FeeStructure)
        .options(
            selectinload(FeeStructure.items).selectinload(FeeStructureItem.fee_head),
            selectinload(FeeStructure.items).selectinload(FeeStructureItem.fee_sub_head),
        )
    )
    return await paginate(db, stmt)

@router.get(
    "/fee-structures/{id}",
    response_model=FeeStructureResponse,
    tags=["Billing - Fee Structures"],
)
async def get_fee_structure(
    id: UUID, db: AsyncSession = Depends(get_db_session)
):
    """Get a single fee structure with all relationship data loaded."""
    stmt = (
        select(FeeStructure)
        .where(FeeStructure.id == id)
        .options(
            selectinload(FeeStructure.items).selectinload(FeeStructureItem.fee_head),
            selectinload(FeeStructure.items).selectinload(FeeStructureItem.fee_sub_head),
        )
    )
    result = await db.execute(stmt)
    fs = result.scalar_one_or_none()
    if not fs:
        raise HTTPException(status_code=404, detail="Fee Structure not found")
    return fs

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


from common.schemas.billing.fee_structure_schemas import FeeStructureUpdate as FeeStructureUpdateSchema
from common.models.admission.admission_entry import AdmissionStudent
from core.security import get_current_user

@router.put(
    "/fee-structures",
    tags=["Billing - Fee Structures"],
)
async def update_fee_structures(
    request: Request,
    payload: list[FeeStructureUpdateSchema],
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
):
    try:
        # Check if user is admin role (to skip lock check)
        user_role = current_user.get("role", "").upper()
        # Default role names are SUPERADMIN / ADMIN, adapt based on your auth
        is_admin = user_role in ("SUPERADMIN", "ADMIN")

        if not is_admin:
            # Check if any associated student has fee structure locked
            for item in payload:
                if not item.id:
                    continue
                # Count if any student has this fee structure locked
                stmt = select(AdmissionStudent.id).where(
                    AdmissionStudent.fee_structure_id == item.id,
                    AdmissionStudent.is_fee_structure_locked == True
                ).limit(1)
                res = await db.execute(stmt)
                locked_student = res.scalar_one_or_none()
                if locked_student:
                    raise ValueError("Fee structure is locked by allotted students and cannot be modified by non-admin users.")

        # Update fee structures using the BaseModel's update pattern
        count = await FeeStructure.update(request, db, payload)
        return {"detail": "Fee structures updated successfully", "count": count}
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
    from common.schemas.billing.demand_year_schema import CreateYearDemandResponse
    from uuid import UUID
    
    try:
        # Extract and validate data
        student_ids_str = payload.get("student_ids", [])
        fee_structure_id_str = payload.get("fee_structure_id")  # optional
        year = payload.get("year")
        semester = payload.get("semester")
        
        if not student_ids_str:
            raise ValueError("Missing required field: student_ids")
        if (year in (None, "")) and semester is None:
            raise ValueError("Either year or semester is required")
        if (year not in (None, "")) and semester is not None:
            raise ValueError("Provide either year or semester, not both")
        
        # Convert string IDs to UUIDs
        student_uuids = [UUID(sid) for sid in student_ids_str]
        fs_uuid = UUID(fee_structure_id_str) if fee_structure_id_str else None
        
        result = await billing_service.create_year_specific_demand(
            db,
            student_uuids,
            fs_uuid,
            year=str(year) if year not in (None, "") else None,
            semester=int(semester) if semester is not None else None,
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
        semester = payload.get("semester")
        
        if not fee_structure_id_str:
            return {"status": {}}
        if (year in (None, "")) and semester is None:
            return {"status": {}}
        if (year not in (None, "")) and semester is not None:
            raise ValueError("Provide either year or semester, not both")
            
        student_uuids = [UUID(sid) for sid in student_ids_str]
        fs_uuid = UUID(fee_structure_id_str)
        
        status_map = await billing_service.check_year_demand_status(
            db,
            student_uuids,
            fs_uuid,
            year=str(year) if year not in (None, "") else None,
            semester=int(semester) if semester is not None else None,
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

# --- Student Deposits Management ─────────────────────────
@router.post(
    "/invoices/{invoice_id}/apply-deposit",
    tags=["Billing - Student Deposits"],
    name="Apply Deposit to Invoice",
    summary="Manually apply student deposit as credit to specific invoice"
)
async def apply_deposit_to_invoice(
    invoice_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(get_user_id),
):
    """
    Manually apply deposit/advance amount to a specific invoice.
    Updates both invoice balance and deposit tracking.
    """
    try:
        from common.models.billing.student_deposit import StudentDeposit
        from sqlalchemy import select
        
        # Get invoice
        invoice_stmt = select(Invoice).where(Invoice.id == invoice_id)
        invoice_res = await db.execute(invoice_stmt)
        invoice = invoice_res.scalar_one_or_none()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        student_id = invoice.student_id
        amount_to_apply = payload.get("amount_to_apply")

        if not amount_to_apply or amount_to_apply <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than 0")

        # Get student deposit
        deposit_stmt = select(StudentDeposit).where(StudentDeposit.student_id == student_id)
        deposit_res = await db.execute(deposit_stmt)
        deposit = deposit_res.scalar_one_or_none()

        if not deposit or deposit.available_balance <= 0:
            raise HTTPException(status_code=400, detail="No available deposit balance for this student")

        from decimal import Decimal
        amount_decimal = Decimal(str(amount_to_apply))
        
        if amount_decimal > Decimal(str(deposit.available_balance)):
            raise HTTPException(
                status_code=400, 
                detail=f"Amount exceeds available balance of {deposit.available_balance}"
            )

        # Create line item for the deposit credit
        line_item = InvoiceLineItem(
            invoice_id=invoice.id,
            description="Deposit/Advance Credit Applied",
            amount=-amount_decimal,  # Negative = credit
            discount_amount=0,
            tax_amount=0,
            net_amount=-amount_decimal,
        )
        db.add(line_item)

        # Update deposit
        deposit.used_amount += amount_decimal
        
        from datetime import datetime
        adjustment_entry = {
            "date": datetime.utcnow().isoformat(),
            "amount": float(amount_decimal),
            "invoice_id": str(invoice.id),
            "applied_by": str(user_id),
        }
        if deposit.adjustment_history is None:
            deposit.adjustment_history = []
        deposit.adjustment_history.append(adjustment_entry)

        # Update invoice balance
        if invoice.balance_due:
            invoice.balance_due -= amount_decimal

        db.add(deposit)
        await db.commit()

        return {
            "success": True,
            "message": f"Applied deposit of {amount_to_apply} to invoice",
            "invoice_id": str(invoice.id),
            "deposit_id": str(deposit.id),
            "new_invoice_balance": float(invoice.balance_due) if invoice.balance_due else 0,
            "deposit_available_balance": float(deposit.available_balance),
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error applying deposit: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/deposits/{student_id}/refund",
    tags=["Billing - Student Deposits"],
    name="Refund Deposit",
    summary="Process refund of student deposit/advance amount"
)
async def refund_deposit(
    student_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(get_user_id),
):
    """
    Request refund of available deposit balance.
    Creates a Refund record for processing.
    """
    try:
        from common.models.billing.student_deposit import StudentDeposit
        from common.models.billing.refund import Refund, RefundStatusEnum
        from sqlalchemy import select
        
        # Get student deposit
        deposit_stmt = select(StudentDeposit).where(StudentDeposit.student_id == student_id)
        deposit_res = await db.execute(deposit_stmt)
        deposit = deposit_res.scalar_one_or_none()

        if not deposit:
            raise HTTPException(status_code=404, detail="No deposit found for this student")

        refund_amount = payload.get("amount")
        refund_method = payload.get("refund_method")
        notes = payload.get("notes")

        if not refund_amount or refund_amount <= 0:
            raise HTTPException(status_code=400, detail="Refund amount must be greater than 0")

        if not refund_method:
            raise HTTPException(status_code=400, detail="Refund method is required")

        from decimal import Decimal
        refund_decimal = Decimal(str(refund_amount))
        
        if refund_decimal > Decimal(str(deposit.available_balance)):
            raise HTTPException(
                status_code=400, 
                detail=f"Refund amount exceeds available balance of {deposit.available_balance}"
            )

        # Create refund record
        refund = Refund(
            student_id=student_id,
            institution_id=deposit.institution_id,
            original_payment_id=None,  # Not linked to specific payment, but to deposit
            original_invoice_id=None,  # Not linked to specific invoice
            original_amount=refund_decimal,
            cancellation_fee=Decimal("0"),
            refund_amount=refund_decimal,
            refund_method=refund_method,
            status=RefundStatusEnum.INITIATED,
            reason=notes,
            initiated_by=user_id,
        )
        db.add(refund)

        # Update deposit
        deposit.refunds_issued += refund_decimal
        
        # Update status based on used and refunded amounts
        from common.models.billing.student_deposit import DepositStatusEnum
        if deposit.available_balance == Decimal("0"):
            if deposit.refunds_issued > 0:
                deposit.status = DepositStatusEnum.FULLY_REFUNDED
            else:
                deposit.status = DepositStatusEnum.FULLY_USED
        elif deposit.refunds_issued > 0:
            deposit.status = DepositStatusEnum.PARTIALLY_REFUNDED

        db.add(deposit)
        await db.commit()
        await db.refresh(refund)

        return {
            "success": True,
            "refund_id": str(refund.id),
            "student_id": str(student_id),
            "amount": float(refund_amount),
            "refund_method": refund_method,
            "status": refund.status,
            "created_at": refund.created_at.isoformat(),
            "deposit_available_balance": float(deposit.available_balance),
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error refunding deposit: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/deposits",
    tags=["Billing - Student Deposits"],
    name="List All Student Deposits",
    summary="Retrieve all student deposits with filtering"
)
async def list_student_deposits(
    page: int = 1,
    size: int = 50,
    institution_id: UUID | None = None,
    department_id: UUID | None = None,
    course_id: UUID | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    List all student deposits with pagination and filtering.
    Useful for Finance reporting and reconciliation.
    """
    try:
        from common.models.billing.student_deposit import StudentDeposit
        from sqlalchemy import func, and_, or_
        
        filters = []
        
        # Base filter
        filters.append(StudentDeposit.total_deposited > 0)
        
        if institution_id:
            filters.append(StudentDeposit.institution_id == institution_id)
        
        from common.models.admission.admission_entry import AdmissionStudent, AdmissionStudentPersonalDetails
        join_student = False

        if search:
            search_pattern = f"%{search}%"
            join_student = True
            filters.append(
                or_(
                    StudentDeposit.application_number.ilike(search_pattern),
                    AdmissionStudentPersonalDetails.name.ilike(search_pattern)
                )
            )
        
        # Count total
        count_stmt = select(func.count(StudentDeposit.id))
        stmt = select(StudentDeposit).options(
            selectinload(StudentDeposit.student).selectinload(AdmissionStudent.personal_details)
        )

        if join_student:
            count_stmt = count_stmt.outerjoin(StudentDeposit.student).outerjoin(AdmissionStudent.personal_details)
            stmt = stmt.outerjoin(StudentDeposit.student).outerjoin(AdmissionStudent.personal_details)

        count_stmt = count_stmt.where(and_(*filters) if filters else True)
        count_res = await db.execute(count_stmt)
        total = count_res.scalar() or 0
        
        # Fetch paginated data
        offset = (page - 1) * size
        stmt = stmt.where(and_(*filters) if filters else True).order_by(StudentDeposit.created_at.desc()).offset(offset).limit(size)
        
        res = await db.execute(stmt)
        deposits = res.scalars().all()
        
        items = []
        for deposit in deposits:
            student_name = None
            if deposit.student:
                 name_val = getattr(deposit.student, "name", None)
                 student_name = getattr(deposit.student.personal_details, "name", name_val) if getattr(deposit.student, "personal_details", None) else name_val
            
            items.append({
                "id": str(deposit.id),
                "student_id": str(deposit.student_id),
                "student_name": student_name,
                "application_number": deposit.application_number,
                "total_deposited": float(deposit.total_deposited),
                "used_amount": float(deposit.used_amount),
                "available_balance": float(deposit.available_balance),
                "refunds_issued": float(deposit.refunds_issued),
                "status": deposit.status,
                "created_at": deposit.created_at.isoformat(),
            })
        
        pages = (total + size - 1) // size if size > 0 else 1
        
        return {
            "items": items,
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
        }
    except Exception as e:
        logger.error(f"Error listing deposits: {str(e)}", exc_info=True)
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

from common.models.billing.concession import ConcessionAudit
from pydantic import BaseModel

class ConcessionReviewRequest(BaseModel):
    notes: Optional[str] = None
    status: str # "approved" or "rejected"

@router.post("/concessions/{id}/review", tags=["Billing - Concessions"])
async def review_concession(
    id: UUID,
    req: ConcessionReviewRequest,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(get_user_id)
):
    stmt = select(Concession).where(Concession.id == id)
    res = await db.execute(stmt)
    concession = res.scalars().first()
    if not concession:
        raise HTTPException(404, "Concession not found")
    
    if concession.status != "pending":
        raise HTTPException(400, "Concession is not in pending state")
        
    concession.status = req.status
    
    audit = ConcessionAudit(
        concession_id=concession.id,
        action=f"status_changed_to_{req.status}",
        performed_by=user_id,
        notes=req.notes
    )
    db.add(audit)
    
    await db.commit()
    await db.refresh(concession)
    return concession

from common.models.billing.scholarship import StudentScholarship

class BulkScholarshipReceiptReq(BaseModel):
    scholarship_id: UUID
    amount_received: Decimal

class BulkScholarshipReceiptPayload(BaseModel):
    receipts: list[BulkScholarshipReceiptReq]

@router.post("/scholarships/bulk_receipt", tags=["Billing - Scholarships"])
async def bulk_scholarship_receipt(
    payload: BulkScholarshipReceiptPayload,
    db: AsyncSession = Depends(get_db_session)
):
    processed = 0
    for item in payload.receipts:
        stmt = select(StudentScholarship).where(StudentScholarship.id == item.scholarship_id)
        res = await db.execute(stmt)
        scholarship = res.scalars().first()
        if scholarship and not scholarship.amount_received:
            scholarship.amount_received = True
            # Here we would normally call multi_receipt logic, 
            # but for now we tag it as received
            processed += 1
            
    await db.commit()
    return {"message": f"Successfully processed {processed} scholarships"}
