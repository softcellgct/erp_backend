from common.models.admission.consultancy import Consultancy
from common.schemas.admission.consultancy import (
    ConsultancyCreate,
    ConsultancyResponse,
    ConsultancyUpdate,
)
from components.db.db import get_db_session
from fastapi import APIRouter, Depends, HTTPException, status

from components.generator.routes import create_crud_routes
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect
from fastapi_pagination import add_pagination, Page
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_querybuilder.dependencies import QueryBuilder
from fastapi import Request

from common.models.admission.admission_entry import AdmissionStudent, AdmissionStatusEnum
from common.models.admission.lead_followup import LeadFollowUp
from common.schemas.admission.admission_entry import (
    AdmissionStudentCreate,
    AdmissionStudentResponse,
    AdmissionStudentUpdate,
    AdmissionStudentGrantAdmission,
)
from common.schemas.admission.lead_followup import (
    LeadFollowUpCreate,
    LeadFollowUpResponse,
    LeadFollowUpUpdate,
)
from common.models.gate.visitor_model import AdmissionVisitor
from apps.admission.services import generate_enquiry_number
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List


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


# Custom GET endpoint with eager loading
@admission_entry_router.get(
    "/admission-students/{id}",
    response_model=AdmissionStudentResponse,
    name="Get Admission Student",
    tags=["Admission - Admission Students"]
)
async def get_admission_student(
    id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    query = select(AdmissionStudent).options(
        selectinload(AdmissionStudent.sslc_details),
        selectinload(AdmissionStudent.hsc_details),
        selectinload(AdmissionStudent.diploma_details),
        selectinload(AdmissionStudent.pg_details),
    ).where(AdmissionStudent.id == id)
    
    result = await db.execute(query)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission student with ID {id} not found"
        )
        
    return student

admission_entry_router.include_router(
    admission_entry_crud_router, prefix="/admission-students", tags=["Admission - Admission Students"]
)

# Custom POST endpoint for granting admission
@admission_entry_router.post(
    "/admission-students",
    response_model=AdmissionStudentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Admission - Admission Students"],
    name="Create Admission Student",
    description="Create an admission student record and update the visitor status to APPLIED"
)
async def create_admission_student(
    payload: AdmissionStudentGrantAdmission,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create admission student record with automatic application number generation.
    
    If visitor_id is provided in the payload:
    1. Generates a unique application number
    2. Updates the admission_visitors record status to APPLIED
    3. Creates a new admission_students record with the provided payload and application number
    
    If visitor_id is not provided:
    1. Creates admission_students record without updating visitor status
    
    Args:
        payload: Admission student details (may include visitor_id)
        
    Returns:
        Created admission student record with generated application number
    """
    try:
        # Extract visitor_id from payload if present
        visitor_id = payload.visitor_id
        
        # Handle visitor status update if visitor_id is provided
        if visitor_id:
            # Fetch the admission visitor
            visitor_result = await db.execute(
                select(AdmissionVisitor).where(AdmissionVisitor.id == visitor_id)
            )
            admission_visitor = visitor_result.scalar_one_or_none()
            
            if not admission_visitor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Admission visitor with ID {visitor_id} not found"
                )
            
            # Generate unique enquiry number
            enquiry_number = await generate_enquiry_number(db, admission_visitor.institution_id)
            
            # Update admission visitor status to APPLIED (not ADMISSION_GRANTED)
            # Status flow: ENQUIRY -> APPLIED -> ... -> ADMISSION_GRANTED
            admission_visitor.status = AdmissionStatusEnum.APPLIED.value
            db.add(admission_visitor)
        else:
            # Generate enquiry number even without visitor_id
            enquiry_number = await generate_enquiry_number(db)
        
        # Create new admission student record with enquiry number
        student_data = payload.dict(exclude_unset=True)
        
        # Remove non-model fields
        student_data.pop('visitor_id', None)  # Remove visitor_id from payload
        
        # Add enquiry number
        student_data['enquiry_number'] = enquiry_number
        
        # Ensure status is set to APPLIED by default if not provided
        if 'status' not in student_data or student_data['status'] is None:
            student_data['status'] = AdmissionStatusEnum.APPLIED.value
        
        # Handle nested relationships - convert dicts to model instances
        mapper = inspect(AdmissionStudent)
        for rel_name, rel in mapper.relationships.items():
            if rel_name in student_data and student_data[rel_name] is not None:
                rel_data = student_data[rel_name]
                related_model = rel.mapper.class_
                # If a single related object is provided as a dict -> create instance
                if not rel.uselist and isinstance(rel_data, dict):
                    student_data[rel_name] = related_model(**rel_data)
                # If a list of related objects is provided -> convert each
                elif rel.uselist and isinstance(rel_data, list):
                    new_list = []
                    for item in rel_data:
                        if isinstance(item, dict):
                            new_list.append(related_model(**item))
                        else:
                            new_list.append(item)
                    student_data[rel_name] = new_list
        
        # Create admission student
        admission_student = AdmissionStudent(**student_data)
        
        db.add(admission_student)
        await db.commit()
        await db.refresh(admission_student)
        
        return admission_student
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create admission student: {str(e)}"
        )


# Dashboard Analytics Endpoints
@admission_entry_router.get("/dashboard/metrics", tags=["Admission - Dashboard"])
async def get_admission_dashboard_metrics(
    db: AsyncSession = Depends(get_db_session)
):
    """Get dashboard metrics for pre-admission analytics."""
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Today's enquiries (both AdmissionStudent and AdmissionVisitor)
    stmt_students_today = select(func.count(AdmissionStudent.id)).where(
        func.date(AdmissionStudent.created_at) == today,
        AdmissionStudent.status == AdmissionStatusEnum.ENQUIRY
    )
    stmt_visitors_today = select(func.count(AdmissionVisitor.id)).where(
        func.date(AdmissionVisitor.created_at) == today,
        AdmissionVisitor.status == AdmissionStatusEnum.ENQUIRY
    )
    
    res_students_today = await db.execute(stmt_students_today)
    res_visitors_today = await db.execute(stmt_visitors_today)
    enquiries_today = res_students_today.scalar() + res_visitors_today.scalar()
    
    # This week's enquiries
    stmt_students_week = select(func.count(AdmissionStudent.id)).where(
        func.date(AdmissionStudent.created_at) >= week_ago,
        AdmissionStudent.status.in_([AdmissionStatusEnum.ENQUIRY, AdmissionStatusEnum.APPLIED])
    )
    stmt_visitors_week = select(func.count(AdmissionVisitor.id)).where(
        func.date(AdmissionVisitor.created_at) >= week_ago,
        AdmissionVisitor.status == AdmissionStatusEnum.ENQUIRY
    )
    
    res_students_week = await db.execute(stmt_students_week)
    res_visitors_week = await db.execute(stmt_visitors_week)
    enquiries_week = res_students_week.scalar() + res_visitors_week.scalar()
    
    # This month's enquiries
    stmt_students_month = select(func.count(AdmissionStudent.id)).where(
        func.date(AdmissionStudent.created_at) >= month_ago,
        AdmissionStudent.status.in_([AdmissionStatusEnum.ENQUIRY, AdmissionStatusEnum.APPLIED])
    )
    stmt_visitors_month = select(func.count(AdmissionVisitor.id)).where(
        func.date(AdmissionVisitor.created_at) >= month_ago,
        AdmissionVisitor.status == AdmissionStatusEnum.ENQUIRY
    )
    
    res_students_month = await db.execute(stmt_students_month)
    res_visitors_month = await db.execute(stmt_visitors_month)
    enquiries_month = res_students_month.scalar() + res_visitors_month.scalar()
    
    # Status breakdown (only AdmissionStudent has detailed statuses)
    stmt_status = select(
        AdmissionStudent.status,
        func.count(AdmissionStudent.id)
    ).group_by(AdmissionStudent.status)
    
    res_status = await db.execute(stmt_status)
    status_breakdown = {str(status): count for status, count in res_status.all()}
    
    # Add ENQUIRY visitors to status breakdown
    enquiry_visitors = await db.execute(
        select(func.count(AdmissionVisitor.id)).where(
            AdmissionVisitor.status == AdmissionStatusEnum.ENQUIRY
        )
    )
    status_breakdown["ENQUIRY"] = status_breakdown.get("ENQUIRY", 0) + enquiry_visitors.scalar()
    
    # Follow-up pending count (students with status ENQUIRY/APPLIED and no follow-up in last 3 days)
    three_days_ago = datetime.now() - timedelta(days=3)
    
    # Get students needing follow-up
    stmt_followup_pending = select(func.count(AdmissionStudent.id.distinct())).where(
        AdmissionStudent.status.in_([AdmissionStatusEnum.ENQUIRY, AdmissionStatusEnum.APPLIED]),
        ~AdmissionStudent.id.in_(
            select(LeadFollowUp.student_id).where(
                LeadFollowUp.created_at >= three_days_ago
            )
        )
    )
    
    res_followup = await db.execute(stmt_followup_pending)
    followup_pending = res_followup.scalar()
    
    # Conversion rate (ENQUIRY -> APPLIED+)
    total_enquiries = await db.execute(select(func.count(AdmissionStudent.id)))
    total_applied = await db.execute(
        select(func.count(AdmissionStudent.id)).where(
            AdmissionStudent.status.in_([
                AdmissionStatusEnum.APPLIED,
                AdmissionStatusEnum.DOCUMENTS_VERIFIED,
                AdmissionStatusEnum.ADMISSION_GRANTED
            ])
        )
    )
    
    total_enq = total_enquiries.scalar()
    total_app = total_applied.scalar()
    conversion_rate = round((total_app / total_enq * 100), 2) if total_enq > 0 else 0
    
    # Source breakdown (from AdmissionVisitor reference_type)
    stmt_source = select(
        AdmissionVisitor.reference_type,
        func.count(AdmissionVisitor.id)
    ).group_by(AdmissionVisitor.reference_type)
    
    res_source = await db.execute(stmt_source)
    source_breakdown = {str(ref_type): count for ref_type, count in res_source.all() if ref_type}
    
    # Recent activity (last 7 days trend)
    stmt_trend = select(
        func.date(AdmissionStudent.created_at).label("date"),
        func.count(AdmissionStudent.id).label("count")
    ).where(
        func.date(AdmissionStudent.created_at) >= week_ago
    ).group_by(func.date(AdmissionStudent.created_at)).order_by(func.date(AdmissionStudent.created_at))
    
    res_trend = await db.execute(stmt_trend)
    trend_data = [{"date": str(date), "count": count} for date, count in res_trend.all()]
    
    return {
        "enquiries_today": enquiries_today,
        "enquiries_week": enquiries_week,
        "enquiries_month": enquiries_month,
        "status_breakdown": status_breakdown,
        "followup_pending": followup_pending,
        "conversion_rate": conversion_rate,
        "source_breakdown": source_breakdown,
        "trend_data": trend_data
    }


@admission_entry_router.get("/reports/enquiries", tags=["Admission - Reports"])
async def get_enquiry_reports(
    start_date: str = None,
    end_date: str = None,
    status: str = None,
    reference_type: str = None,
    db: AsyncSession = Depends(get_db_session)
):
    """Get detailed enquiry reports with filters."""
    from datetime import datetime
    
    # Build query for AdmissionStudents
    query_students = select(AdmissionStudent)
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query_students = query_students.where(AdmissionStudent.created_at >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query_students = query_students.where(AdmissionStudent.created_at <= end)
        except ValueError:
            pass
    
    if status:
        query_students = query_students.where(AdmissionStudent.status == status)
    
    res_students = await db.execute(query_students)
    students = res_students.scalars().all()
    
    # Build query for AdmissionVisitors
    query_visitors = select(AdmissionVisitor).where(AdmissionVisitor.status == AdmissionStatusEnum.ENQUIRY)
    
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query_visitors = query_visitors.where(AdmissionVisitor.created_at >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query_visitors = query_visitors.where(AdmissionVisitor.created_at <= end)
        except ValueError:
            pass
    
    if reference_type:
        query_visitors = query_visitors.where(AdmissionVisitor.reference_type == reference_type)
    
    res_visitors = await db.execute(query_visitors)
    visitors = res_visitors.scalars().all()
    
    # Normalize data
    normalized_students = [{
        "id": str(s.id),
        "enquiry_number": s.enquiry_number,
        "name": s.name,
        "mobile": s.student_mobile,
        "status": s.status,
        "source": None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in students]
    
    normalized_visitors = [{
        "id": str(v.id),
        "enquiry_number": v.gate_pass_no,
        "name": v.student_name,
        "mobile": v.mobile_number,
        "status": v.status,
        "source": v.reference_type,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    } for v in visitors]
    
    all_enquiries = normalized_students + normalized_visitors
    
    return {
        "total": len(all_enquiries),
        "data": all_enquiries
    }


lead_followup_router = APIRouter()

lead_followup_crud_router = create_crud_routes(
    LeadFollowUp,
    LeadFollowUpCreate,
    LeadFollowUpUpdate,
    LeadFollowUpResponse,
)

@lead_followup_router.get(
    "/student/{student_id}",
    response_model=List[LeadFollowUpResponse],
    tags=["Admission - Lead Follow-up"]
)
async def get_student_followup_history(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Get follow-up history for a specific student."""
    query = select(LeadFollowUp).where(LeadFollowUp.student_id == student_id).order_by(desc(LeadFollowUp.created_at))
    result = await db.execute(query)
    return result.scalars().all()

lead_followup_router.include_router(
    lead_followup_crud_router, prefix="/records", tags=["Admission - Lead Follow-up"]
)


@lead_followup_router.get(
    "/leads",
    response_model=Page[AdmissionStudentResponse],
    tags=["Admission - Lead Follow-up"],
    summary="Get Lead Students (excluding Admitted/Paid)"
)
async def get_lead_students(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    query=QueryBuilder(AdmissionStudent)
):
    """
    Get all admission students who are in the 'lead' stage.
    Excludes students who have paid the full application fee (indicating admission).
    """
    from common.models.billing.application_fees import Invoice, InvoiceLineItem, PaymentStatusEnum, FeeHead
    
    # 1. Find 'Application Fee' Head ID(s)
    stmt_head = select(FeeHead.id).where(FeeHead.name.ilike("%Application Fee%"))
    res_head = await db.execute(stmt_head)
    fee_head_ids = res_head.scalars().all()
    
    paid_student_ids = []
    if fee_head_ids:
        # Finding students with PAID invoices for Application Fee
        stmt_paid = (
            select(Invoice.student_id)
            .join(InvoiceLineItem, Invoice.id == InvoiceLineItem.invoice_id)
            .where(
                Invoice.status == PaymentStatusEnum.PAID,
                InvoiceLineItem.fee_head_id.in_(fee_head_ids)
            )
        )
        res_paid = await db.execute(stmt_paid)
        paid_student_ids = res_paid.scalars().all()
    
    # 2. Add filters to the query builder query
    # Show only ENQUIRY status students (initial enquiries)
    query = query.where(
        AdmissionStudent.status.in_([AdmissionStatusEnum.ENQUIRY, AdmissionStatusEnum.APPLIED, AdmissionStatusEnum.DOCUMENTS_VERIFIED])
    )
    
    # 3. Exclude paid students
    if paid_student_ids:
        query = query.where(AdmissionStudent.id.notin_(paid_student_ids))

    # -----------------------------
    # Combine AdmissionStudent + AdmissionVisitor (ENQUIRY) into a single paginated response
    # - Use QueryBuilder-built `query` to fetch ALL matching AdmissionStudent rows (we'll paginate after merging)
    # - Fetch AdmissionVisitor rows with status ENQUIRY and apply simple search if provided
    # - Map AdmissionVisitor fields to match AdmissionStudentResponse shape
    # -----------------------------
    # Parse pagination params from request
    try:
        page = int(request.query_params.get("page", 1))
    except Exception:
        page = 1
    try:
        size = int(request.query_params.get("size", 50))
    except Exception:
        size = 50

    # Execute student query (all matching rows)
    res_students = await db.execute(query)
    student_objs = res_students.scalars().all()

    # Build visitor query (only ENQUIRY visitors)
    visitor_q = select(AdmissionVisitor).where(AdmissionVisitor.status == AdmissionStatusEnum.ENQUIRY)

    # Apply simple search on visitors if 'search' present in query params
    search_term = request.query_params.get("search")
    if search_term:
        visitor_q = visitor_q.where(
            (AdmissionVisitor.student_name.ilike(f"%{search_term}%")) |
            (AdmissionVisitor.gate_pass_no.ilike(f"%{search_term}%")) |
            (AdmissionVisitor.mobile_number.ilike(f"%{search_term}%"))
        )

    res_visitors = await db.execute(visitor_q)
    visitor_objs = res_visitors.scalars().all()

    # Map visitors into AdmissionStudent-like dicts so frontend schema matches
    # — but exclude visitors that already have a corresponding AdmissionStudent
    # (dedupe by enquiry_number OR mobile number). This prevents the same lead
    # from appearing twice when both tables contain the same person.
    student_enq_set = {s.enquiry_number for s in student_objs if getattr(s, "enquiry_number", None)}
    student_mobile_set = {s.student_mobile for s in student_objs if getattr(s, "student_mobile", None)}

    mapped_visitors = []
    for v in visitor_objs:
        # if visitor matches an existing AdmissionStudent by enquiry_number or mobile, skip it
        if (v.gate_pass_no and v.gate_pass_no in student_enq_set) or (
            v.mobile_number and v.mobile_number in student_mobile_set
        ):
            continue

        mapped_visitors.append({
            "id": v.id,
            "enquiry_number": v.gate_pass_no,
            "name": v.student_name,
            "student_mobile": v.mobile_number,
            "status": v.status,
            "institution_id": v.institution_id,
            "created_at": v.created_at,
            "updated_at": v.updated_at,
        })

    # Normalize student objects to dicts (Pydantic/JSON friendly)
    normalized_students = []
    for s in student_objs:
        normalized_students.append({
            "id": s.id,
            "enquiry_number": s.enquiry_number,
            "name": s.name,
            "student_mobile": s.student_mobile,
            "status": s.status,
            "institution_id": s.institution_id,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        })

    # Merge, sort by created_at desc
    combined = sorted(normalized_students + mapped_visitors, key=lambda x: x.get("created_at") or 0, reverse=True)

    total = len(combined)
    pages = (total + size - 1) // size if size > 0 else 1
    start = (page - 1) * size
    end = start + size
    page_items = combined[start:end]

    return {
        "items": page_items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


admission_router = APIRouter()

@admission_router.get("/applied", tags=["Admission - Admission Students"])
async def get_applied_admission_students(
    db: AsyncSession = Depends(get_db_session)
):
    """Get all admission students with status 'Applied'."""
    result = await db.execute(
        select(AdmissionStudent).where(AdmissionStudent.status == AdmissionStatusEnum.APPLIED.value)
    )
    return result.scalars().all()


# Import schemas
from common.schemas.admission.admission_entry import BookAdmissionRequest, UpdateCourseRequest
from apps.billing.services import billing_service

@admission_router.post(
    "/admission-students/{student_id}/book-admission",
    tags=["Admission - Admission Students"],
    summary="Book Admission (Generate App No & Assign Fees)"
)
async def book_admission(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    # 1. Fetch Student
    stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    if student.application_number:
        raise HTTPException(status_code=400, detail="Admission already booked (App Number exists)")
        
    try:
        # 2. Generate App Number
        app_num = await billing_service.generate_application_number(db, student.institution_id)
        student.application_number = app_num
        student.status = AdmissionStatusEnum.FEE_PENDING.value # Or ADMISSION_GRANTED?
        
        # 3. Assign Fees (Auto-resolve if not provided)
        # We pass None for fee_structure_id to let the service find it based on student details
        await billing_service.assign_course_fees(db, student_id, fee_structure_id=None)
        

        # 4. Assign Application Fee (if configured)
        demand = await billing_service.assign_application_fee(db, student_id)
        if demand:
            # Auto-Invoice the application fee for Cash Counter availability
            await billing_service.create_invoice_from_demands(db, [demand])
        
        await db.commit()
        await db.refresh(student)
        return student
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@admission_router.post(
    "/admission-students/{student_id}/update-course",
    tags=["Admission - Admission Students"],
    summary="Update Course & Re-assign Fees"
)
async def update_course_and_fees(
    student_id: UUID,
    payload: UpdateCourseRequest,
    db: AsyncSession = Depends(get_db_session)
):
    # 1. Fetch Student
    stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    try:
        # 2. Update Student Course/Department
        student.course_id = payload.course_id
        if payload.department_id:
            student.department_id = payload.department_id
            
        # 3. Handle Fee Logic
        await billing_service.handle_course_change(db, student_id, payload.fee_structure_id)
        
        await db.commit()
        await db.refresh(student)
        return student
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@admission_router.post(
    "/admission-students/{student_id}/grant-admission",
    tags=["Admission - Admission Students"],
    summary="Grant Admission to Student"
)
async def grant_admission(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Grant admission to a student - update their status to ADMISSION_GRANTED
    This endpoint should be called after fee is received and admission is approved.
    """
    # 1. Fetch Student
    stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check if student is in a valid status to grant admission
    valid_statuses = [
        AdmissionStatusEnum.APPLIED.value,
        AdmissionStatusEnum.DOCUMENTS_VERIFIED.value,
        AdmissionStatusEnum.FEE_PENDING.value,
        AdmissionStatusEnum.FEE_RECEIVED.value,
        AdmissionStatusEnum.ON_HOLD.value
    ]
    
    if student.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Student with status '{student.status}' cannot be granted admission"
        )
    
    try:
        # Update status to ADMISSION_GRANTED
        student.status = AdmissionStatusEnum.ADMISSION_GRANTED.value
        db.add(student)
        await db.commit()
        await db.refresh(student)
        return student
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


add_pagination(admission_router)
add_pagination(lead_followup_router)
add_pagination(admission_entry_router)