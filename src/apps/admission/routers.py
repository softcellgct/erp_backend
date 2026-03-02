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

from common.models.admission.admission_entry import AdmissionStudent, AdmissionStatusEnum, SourceEnum
from common.models.admission.lead_followup import LeadFollowUp
from common.schemas.admission.admission_entry import (
    AdmissionStudentCreate,
    AdmissionStudentResponse,
    AdmissionStudentUpdate,
    AdmissionStudentGrantAdmission,
    AssignRollNumberRequest,
    AssignSectionRequest,
    ActivateSem1Request,
    SetFeeStructureLockRequest,
    BulkAdmissionStatusUpdateRequest,
    BulkAdmissionStatusUpdateResponse,
    BulkAdmissionStatusUpdateResult,
)
from common.schemas.admission.lead_followup import (
    LeadFollowUpCreate,
    LeadFollowUpResponse,
    LeadFollowUpUpdate,
)
from apps.admission.services import generate_enquiry_number
from sqlalchemy import select, desc, and_, or_, cast, String
from sqlalchemy import func
from sqlalchemy.orm import selectinload, raiseload
from uuid import UUID
from typing import List
from datetime import datetime, time
from common.models.master.institution import Department, Course
from common.models.master.annual_task import AcademicYear

from common.models.billing.application_fees import Invoice, InvoiceLineItem, PaymentStatusEnum as InvoicePaymentStatus
from components.generator.utils.get_user_from_request import get_user_id
import logging

logger = logging.getLogger(__name__)


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
    name="Get Admission Student",
    tags=["Admission - Admission Students"]
)
async def get_admission_student(
    id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    query = select(AdmissionStudent).options(
        raiseload("*")
    ).where(AdmissionStudent.id == id)
    
    result = await db.execute(query)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission student with ID {id} not found"
        )
    
    # Return as dict to avoid circular reference encoding issues
    return {
        "id": str(student.id),
        "name": student.name,
        "email": student.email,
        "student_mobile": student.student_mobile,
        "enquiry_number": student.enquiry_number,
        "application_number": student.application_number,
        "status": student.status,
        "source": student.source,
        "department_id": str(student.department_id) if student.department_id else None,
        "course_id": str(student.course_id) if student.course_id else None,
        "institution_id": str(student.institution_id) if student.institution_id else None,
        "created_at": student.created_at,
        "updated_at": student.updated_at,
        "fee_structure_id": str(student.fee_structure_id) if student.fee_structure_id else None,
        "is_fee_structure_locked": student.is_fee_structure_locked,
        "fee_structure_locked_at": student.fee_structure_locked_at,
        "fee_structure_locked_by": str(student.fee_structure_locked_by) if student.fee_structure_locked_by else None
    }


@admission_entry_router.get(
    "/booked-paid",
    tags=["Admission - Admission Students"],
    name="Get Booked Paid Students"
)
async def get_booked_paid_students(
    page: int = 1,
    size: int = 50,
    q: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Return students with status BOOKED or APPLIED (both paid and unpaid invoices).
    """
    try:
        # Base filters: student.status == BOOKED or APPLIED
        from sqlalchemy import or_
        filters = [
            or_(
                AdmissionStudent.status == AdmissionStatusEnum.BOOKED.value,
                AdmissionStudent.status == AdmissionStatusEnum.APPLIED.value,
            )
        ]

        if q:
            qfilter = f"%{q}%"
            filters.append(
                (AdmissionStudent.name.ilike(qfilter)) | (AdmissionStudent.application_number.ilike(qfilter))
            )

        # Total count
        count_stmt = select(func.count(AdmissionStudent.id)).where(*filters)
        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        # Paging
        offset = (page - 1) * size

        stmt = select(AdmissionStudent).options(
            selectinload(AdmissionStudent.department),
            selectinload(AdmissionStudent.course),
        ).where(*filters).order_by(desc(AdmissionStudent.created_at)).offset(offset).limit(size)
        res = await db.execute(stmt)
        students = res.scalars().all()

        items = []
        for s in students:
            # Get latest application-fee invoice for this student (paid or unpaid)
            inv_stmt = select(Invoice).join(InvoiceLineItem).where(
                Invoice.student_id == s.id,
                InvoiceLineItem.description.ilike("%Application Fee%"),
            ).order_by(desc(Invoice.issue_date)).limit(1)
            inv_res = await db.execute(inv_stmt)
            inv = inv_res.scalar_one_or_none()

            dept_name = None
            course_title = None
            if getattr(s, "department", None):
                dept_name = getattr(s.department, "name", None)
            if getattr(s, "course", None):
                course_title = getattr(s.course, "title", None)

            items.append(
                {
                    "id": str(s.id),
                    "application_number": s.application_number,
                    "name": s.name,
                    "department": dept_name,
                    "course": course_title,
                    "booking_date": s.created_at.isoformat() if getattr(s, "created_at", None) else None,
                    "amount_paid": float(inv.paid_amount) if inv and inv.paid_amount is not None else None,
                    "invoice_id": str(inv.id) if inv else None,
                    "invoice_status": inv.status if inv else None,
                    "status": s.status,
                }
            )

        pages = (total + size - 1) // size if size > 0 else 1

        return {"items": items, "total": total, "page": page, "pages": pages, "size": size}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@admission_entry_router.get(
    "/applied",
    tags=["Admission - Admission Students"],
    name="Get Applied Students"
)
async def get_applied_students(
    page: int = 1,
    size: int = 50,
    q: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Return students with status APPLIED.
    """
    try:
        filters = [
            AdmissionStudent.status == AdmissionStatusEnum.APPLIED.value,
        ]

        if q:
            qfilter = f"%{q}%"
            filters.append(
                (AdmissionStudent.name.ilike(qfilter)) | (AdmissionStudent.application_number.ilike(qfilter))
            )

        # Total count
        count_stmt = select(func.count(AdmissionStudent.id)).where(*filters)
        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        # Paging
        offset = (page - 1) * size

        stmt = select(AdmissionStudent).options(
            selectinload(AdmissionStudent.department),
            selectinload(AdmissionStudent.course),
        ).where(*filters).order_by(desc(AdmissionStudent.created_at)).offset(offset).limit(size)
        res = await db.execute(stmt)
        students = res.scalars().all()

        items = []
        for s in students:
            dept_name = None
            course_title = None
            if getattr(s, "department", None):
                dept_name = getattr(s.department, "name", None)
            if getattr(s, "course", None):
                course_title = getattr(s.course, "title", None)

            items.append(
                {
                    "id": str(s.id),
                    "application_number": s.application_number,
                    "name": s.name,
                    "department": dept_name,
                    "course": course_title,
                    "enrollment_date": s.created_at.isoformat() if getattr(s, "created_at", None) else None,
                    "status": s.status,
                }
            )

        pages = (total + size - 1) // size if size > 0 else 1

        return {"items": items, "total": total, "page": page, "pages": pages, "size": size}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@admission_entry_router.get(
    "/admission-students",
    tags=["Admission - Admission Students"],
    name="List Admission Students",
    description="Retrieve paginated admission students with filtering and searching (excludes JSON field searches to avoid PostgreSQL errors)"
)
async def list_admission_students(
    page: int = 1,
    size: int = 50,
    search: str | None = None,
    filters: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Retrieve paginated admission students with optional search and filtering.
    Search only applies to: name, enquiry_number, application_number, roll_number, student_mobile, parent_mobile
    Filtering uses JSON format: {"status": {"$in": ["APPLIED", "ENROLLED"]}}
    """
    try:
        import json
        import logging
        logger = logging.getLogger(__name__)
        
        # Build base query
        query_filters = [AdmissionStudent.deleted_at == None]
        
        # Apply search filter (only on important non-JSON fields)
        if search:
            search_pattern = f"%{search}%"
            query_filters.append(
                or_(
                    AdmissionStudent.name.ilike(search_pattern),
                    AdmissionStudent.enquiry_number.ilike(search_pattern),
                    AdmissionStudent.application_number.ilike(search_pattern),
                    AdmissionStudent.roll_number.ilike(search_pattern),
                    AdmissionStudent.student_mobile.ilike(search_pattern),
                    AdmissionStudent.parent_mobile.ilike(search_pattern),
                    AdmissionStudent.father_name.ilike(search_pattern),
                )
            )
        
        # Apply JSON filters
        if filters:
            try:
                filter_obj = json.loads(filters)

                def parse_uuid(value):
                    if not value:
                        return None
                    try:
                        return UUID(str(value))
                    except Exception:
                        return None

                def as_datetime_bounds(value, is_start=True):
                    if value is None:
                        return None
                    try:
                        parsed_date = datetime.fromisoformat(str(value)).date()
                        return datetime.combine(parsed_date, time.min if is_start else time.max)
                    except Exception:
                        return None

                def parse_condition(field_name, operator, raw_value):
                    string_columns = {
                        "name": AdmissionStudent.name,
                        "enquiry_number": AdmissionStudent.enquiry_number,
                        "application_number": AdmissionStudent.application_number,
                        "roll_number": AdmissionStudent.roll_number,
                        "student_mobile": AdmissionStudent.student_mobile,
                        "parent_mobile": AdmissionStudent.parent_mobile,
                        "father_name": AdmissionStudent.father_name,
                    }

                    uuid_columns = {
                        "institution_id": AdmissionStudent.institution_id,
                        "department_id": AdmissionStudent.department_id,
                        "course_id": AdmissionStudent.course_id,
                        "academic_year_id": AdmissionStudent.academic_year_id,
                    }

                    date_columns = {
                        "created_at": AdmissionStudent.created_at,
                        "updated_at": AdmissionStudent.updated_at,
                    }

                    if field_name == "status":
                        status_column = cast(AdmissionStudent.status, String)
                        if operator == "$in" and isinstance(raw_value, list):
                            return status_column.in_([str(v) for v in raw_value if v is not None])
                        if operator == "$eq":
                            return status_column == str(raw_value)
                        if operator == "$ne":
                            return status_column != str(raw_value)
                        if operator == "$contains":
                            return status_column.ilike(f"%{raw_value}%")
                        return None

                    if field_name in string_columns:
                        column = string_columns[field_name]
                        value = "" if raw_value is None else str(raw_value)
                        if operator == "$eq":
                            return column == value
                        if operator == "$ne":
                            return column != value
                        if operator == "$contains":
                            return column.ilike(f"%{value}%")
                        if operator == "$ncontains":
                            return ~column.ilike(f"%{value}%")
                        if operator == "$startswith":
                            return column.ilike(f"{value}%")
                        if operator == "$endswith":
                            return column.ilike(f"%{value}")
                        if operator == "$isempty":
                            return or_(column.is_(None), column == "")
                        if operator == "$isnotempty":
                            return and_(column.is_not(None), column != "")
                        if operator == "$isanyof":
                            items = [v.strip() for v in value.split(",") if v.strip()]
                            return column.in_(items) if items else None
                        if operator == "$in" and isinstance(raw_value, list):
                            return column.in_([str(v) for v in raw_value if v is not None])
                        return None

                    if field_name in uuid_columns:
                        column = uuid_columns[field_name]
                        if operator in {"$eq", "$ne"}:
                            uuid_value = parse_uuid(raw_value)
                            if not uuid_value:
                                return None
                            return column == uuid_value if operator == "$eq" else column != uuid_value
                        if operator == "$in":
                            if not isinstance(raw_value, list):
                                return None
                            uuid_values = [parse_uuid(v) for v in raw_value]
                            uuid_values = [value for value in uuid_values if value is not None]
                            return column.in_(uuid_values) if uuid_values else None
                        return None

                    if field_name in date_columns:
                        column = date_columns[field_name]
                        if operator in {"$eq", "$gte", "$gt", "$lte", "$lt", "$ne"}:
                            if operator in {"$gte", "$gt", "$eq"}:
                                dt_value = as_datetime_bounds(raw_value, is_start=True)
                            else:
                                dt_value = as_datetime_bounds(raw_value, is_start=False)
                            if not dt_value:
                                return None
                            if operator == "$eq":
                                return and_(column >= as_datetime_bounds(raw_value, True), column <= as_datetime_bounds(raw_value, False))
                            if operator == "$ne":
                                return ~and_(column >= as_datetime_bounds(raw_value, True), column <= as_datetime_bounds(raw_value, False))
                            if operator == "$gte":
                                return column >= dt_value
                            if operator == "$gt":
                                return column > dt_value
                            if operator == "$lte":
                                return column <= dt_value
                            if operator == "$lt":
                                return column < dt_value
                        return None

                    return None

                def parse_filter_tree(node):
                    if not isinstance(node, dict):
                        return None

                    if "$and" in node and isinstance(node["$and"], list):
                        expressions = [parse_filter_tree(item) for item in node["$and"]]
                        expressions = [expression for expression in expressions if expression is not None]
                        return and_(*expressions) if expressions else None

                    if "$or" in node and isinstance(node["$or"], list):
                        expressions = [parse_filter_tree(item) for item in node["$or"]]
                        expressions = [expression for expression in expressions if expression is not None]
                        return or_(*expressions) if expressions else None

                    expressions = []
                    for field_name, raw_condition in node.items():
                        if isinstance(raw_condition, dict):
                            for operator, raw_value in raw_condition.items():
                                parsed = parse_condition(field_name, operator, raw_value)
                                if parsed is not None:
                                    expressions.append(parsed)
                        else:
                            parsed = parse_condition(field_name, "$eq", raw_condition)
                            if parsed is not None:
                                expressions.append(parsed)

                    if not expressions:
                        return None
                    if len(expressions) == 1:
                        return expressions[0]
                    return and_(*expressions)

                parsed_tree = parse_filter_tree(filter_obj)
                if parsed_tree is not None:
                    query_filters.append(parsed_tree)

                # Backward compatibility for older keys
                created_at_from = filter_obj.get("created_at_from") or filter_obj.get("date_from")
                if created_at_from:
                    start_dt = as_datetime_bounds(created_at_from, True)
                    if start_dt:
                        query_filters.append(AdmissionStudent.created_at >= start_dt)

                created_at_to = filter_obj.get("created_at_to") or filter_obj.get("date_to")
                if created_at_to:
                    end_dt = as_datetime_bounds(created_at_to, False)
                    if end_dt:
                        query_filters.append(AdmissionStudent.created_at <= end_dt)
                        
                # Add more filter types as needed
            except json.JSONDecodeError:
                pass
        
        # Count total
        count_query = select(func.count(AdmissionStudent.id)).where(and_(*query_filters))
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0
        
        # Fetch paginated data
        offset = (page - 1) * size
        data_query = select(AdmissionStudent).options(
            selectinload(AdmissionStudent.department),
            selectinload(AdmissionStudent.course),
        ).where(and_(*query_filters)).order_by(desc(AdmissionStudent.created_at)).offset(offset).limit(size)
        
        result = await db.execute(data_query)
        students = result.scalars().all()
        
        department_ids = {student.department_id for student in students if student.department_id}
        course_ids = {student.course_id for student in students if student.course_id}
        academic_year_ids = {student.academic_year_id for student in students if student.academic_year_id}

        department_name_map = {}
        course_title_map = {}
        academic_year_name_map = {}

        if department_ids:
            department_result = await db.execute(
                select(Department.id, Department.name).where(Department.id.in_(department_ids))
            )
            department_name_map = {str(item[0]): item[1] for item in department_result.all()}

        if course_ids:
            course_result = await db.execute(
                select(Course.id, Course.title).where(Course.id.in_(course_ids))
            )
            course_title_map = {str(item[0]): item[1] for item in course_result.all()}

        if academic_year_ids:
            year_result = await db.execute(
                select(AcademicYear.id, AcademicYear.year_name).where(AcademicYear.id.in_(academic_year_ids))
            )
            academic_year_name_map = {str(item[0]): item[1] for item in year_result.all()}

        # Convert ORM objects to dictionaries for JSON serialization
        # Using sqlalchemy's introspection to handle all fields
        from sqlalchemy.inspection import inspect
        student_dicts = []
        for student in students:
            # Convert ORM object to dictionary, including relationships
            mapper = inspect(student.__class__)
            student_dict = {}
            for column in mapper.columns:
                value = getattr(student, column.name)
                # Convert datetime and UUID objects to strings for JSON serialization
                if hasattr(value, 'isoformat'):  # datetime
                    student_dict[column.name] = value.isoformat()
                elif hasattr(value, 'value'):  # Enum
                    student_dict[column.name] = value.value
                elif hasattr(value, 'hex'):  # UUID
                    student_dict[column.name] = str(value)
                else:
                    student_dict[column.name] = value

            student_dict["department_name"] = department_name_map.get(str(student.department_id))
            student_dict["course_title"] = course_title_map.get(str(student.course_id))
            student_dict["academic_year_name"] = academic_year_name_map.get(str(student.academic_year_id))

            student_dicts.append(student_dict)
        
        # Calculate pages (minimum 1 page even if no results)  
        pages = max(1, (total + size - 1) // size) if size > 0 else 1
        
        return {
            "items": student_dicts,
            "total": total,
            "page": page,
            "size": size,
            "pages": pages,
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in list_admission_students: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@admission_entry_router.post(
    "/admission-students/bulk-status",
    tags=["Admission - Admission Students"],
    name="Bulk Update Admission Student Status",
)
async def bulk_update_admission_student_status(
    payload: BulkAdmissionStatusUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    if not payload.student_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="student_ids cannot be empty",
        )

    if payload.new_status != AdmissionStatusEnum.PROVISIONALLY_ALLOTTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PROVISIONALLY_ALLOTTED bulk update is supported",
        )

    query = select(AdmissionStudent).where(
        AdmissionStudent.id.in_(payload.student_ids),
        AdmissionStudent.deleted_at.is_(None),
    )
    result = await db.execute(query)
    students = result.scalars().all()
    student_map = {student.id: student for student in students}

    updated_count = 0
    changes_made = 0
    results: List[BulkAdmissionStatusUpdateResult] = []

    for student_id in payload.student_ids:
        student = student_map.get(student_id)
        if not student:
            results.append(
                BulkAdmissionStatusUpdateResult(
                    student_id=student_id,
                    success=False,
                    message="Student not found",
                )
            )
            continue

        current_status = student.status.value if hasattr(student.status, "value") else str(student.status)

        if current_status == "PROVISIONALLY_ALLOTTED":
            if not getattr(student, "is_fee_structure_locked", False):
                try:
                    await billing_service.lock_student_fee_structure(db, student.id)
                    changes_made += 1
                    results.append(
                        BulkAdmissionStatusUpdateResult(
                            student_id=student_id,
                            success=True,
                            message="Already in PROVISIONALLY_ALLOTTED status; fee structure locked",
                        )
                    )
                except Exception as exc:
                    results.append(
                        BulkAdmissionStatusUpdateResult(
                            student_id=student_id,
                            success=False,
                            message=f"Already provisionally allotted but fee lock failed: {exc}",
                        )
                    )
                continue

            results.append(
                BulkAdmissionStatusUpdateResult(
                    student_id=student_id,
                    success=True,
                    message="Already in PROVISIONALLY_ALLOTTED status",
                )
            )
            continue

        if current_status != AdmissionStatusEnum.APPLIED.value:
            results.append(
                BulkAdmissionStatusUpdateResult(
                    student_id=student_id,
                    success=False,
                    message=f"Invalid transition from {current_status}",
                )
            )
            continue

        try:
            await billing_service.lock_student_fee_structure(db, student.id)
        except Exception as exc:
            results.append(
                BulkAdmissionStatusUpdateResult(
                    student_id=student_id,
                    success=False,
                    message=f"Fee structure lock failed: {exc}",
                )
            )
            continue

        student.status = AdmissionStatusEnum.PROVISIONALLY_ALLOTTED
        updated_count += 1
        changes_made += 1
        results.append(
            BulkAdmissionStatusUpdateResult(
                student_id=student_id,
                success=True,
                message="Status updated and fee structure locked",
            )
        )

    if changes_made > 0:
        await db.commit()

    failed_count = len([item for item in results if not item.success])

    return BulkAdmissionStatusUpdateResponse(
        total_requested=len(payload.student_ids),
        updated_count=updated_count,
        failed_count=failed_count,
        results=results,
    )


# Include only specific CRUD endpoints (excluding auto-generated GET list which causes JSON column search errors)
# Create a custom CRUD router that doesn't include the problematic list endpoint
admission_entry_crud_router_no_list = create_crud_routes(
    AdmissionStudent,
    AdmissionStudentCreate,
    AdmissionStudentUpdate,
    AdmissionStudentResponse,
    AdmissionStudentResponse
)

# Remove the GET "" endpoint from the router (the one that uses QueryBuilder)
admission_entry_crud_router_no_list.routes = [
    route for route in admission_entry_crud_router_no_list.routes
    if not (hasattr(route, 'path') and route.path == '' and 'GET' in route.methods)
]

admission_entry_router.include_router(
    admission_entry_crud_router_no_list, prefix="/admission-students", tags=["Admission - Admission Students"]
)

# Custom POST endpoint for granting admission
@admission_entry_router.post(
    "/admission-students",
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
    
    If visitor_id is provided (i.e. the student came from a gate enquiry):
    1. Finds the existing AdmissionStudent record (source=GATE_ENQUIRY)
    2. Updates it with the new payload data and promotes status to ENQUIRED
    
    If visitor_id is not provided (direct entry):
    1. Creates a new AdmissionStudent record (source=DIRECT_ENTRY)
    
    Args:
        payload: Admission student details (may include visitor_id)
        
    Returns:
        Created / updated admission student record
    """
    try:
        visitor_id = payload.visitor_id
        
        if visitor_id:
            # Promote existing gate-enquiry record
            result = await db.execute(
                select(AdmissionStudent).where(AdmissionStudent.id == visitor_id)
            )
            admission_student = result.scalar_one_or_none()
            
            if not admission_student:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Gate enquiry record with ID {visitor_id} not found"
                )
            
            # Generate enquiry number if not already set
            if not admission_student.enquiry_number:
                admission_student.enquiry_number = await generate_enquiry_number(
                    db, admission_student.institution_id
                )
            
            # Update fields from payload
            update_data = payload.dict(exclude_unset=True)
            update_data.pop("visitor_id", None)
            
            if "status" not in update_data or update_data["status"] is None:
                update_data["status"] = AdmissionStatusEnum.ENQUIRED.value
            
            # Handle nested relationships
            mapper = inspect(AdmissionStudent)
            for rel_name, rel in mapper.relationships.items():
                if rel_name in update_data and update_data[rel_name] is not None:
                    rel_data = update_data.pop(rel_name)
                    related_model = rel.mapper.class_
                    if not rel.uselist and isinstance(rel_data, dict):
                        setattr(admission_student, rel_name, related_model(**rel_data))
                    elif rel.uselist and isinstance(rel_data, list):
                        setattr(admission_student, rel_name, [
                            related_model(**item) if isinstance(item, dict) else item
                            for item in rel_data
                        ])
                elif rel_name in update_data:
                    update_data.pop(rel_name)
            
            for field, value in update_data.items():
                setattr(admission_student, field, value)
            
            await db.commit()
            await db.refresh(admission_student)
            
            # Return as dict to avoid circular reference encoding issues
            return {
                "id": str(admission_student.id),
                "name": admission_student.name,
                "email": admission_student.email,
                "student_mobile": admission_student.student_mobile,
                "enquiry_number": admission_student.enquiry_number,
                "application_number": admission_student.application_number,
                "status": admission_student.status,
                "source": admission_student.source,
                "department_id": str(admission_student.department_id) if admission_student.department_id else None,
                "course_id": str(admission_student.course_id) if admission_student.course_id else None,
                "institution_id": str(admission_student.institution_id) if admission_student.institution_id else None,
                "created_at": admission_student.created_at,
                "updated_at": admission_student.updated_at,
                "fee_structure_id": str(admission_student.fee_structure_id) if admission_student.fee_structure_id else None,
                "is_fee_structure_locked": admission_student.is_fee_structure_locked,
                "fee_structure_locked_at": admission_student.fee_structure_locked_at,
                "fee_structure_locked_by": str(admission_student.fee_structure_locked_by) if admission_student.fee_structure_locked_by else None
            }
        
        else:
            # Direct entry — create new record
            enquiry_number = await generate_enquiry_number(db)
            
            student_data = payload.dict(exclude_unset=True)
            student_data.pop("visitor_id", None)
            student_data["enquiry_number"] = enquiry_number
            student_data.setdefault("source", SourceEnum.DIRECT_ENTRY.value)
            
            if "status" not in student_data or student_data["status"] is None:
                student_data["status"] = AdmissionStatusEnum.ENQUIRED.value
            
            # Handle nested relationships
            mapper = inspect(AdmissionStudent)
            for rel_name, rel in mapper.relationships.items():
                if rel_name in student_data and student_data[rel_name] is not None:
                    rel_data = student_data[rel_name]
                    related_model = rel.mapper.class_
                    if not rel.uselist and isinstance(rel_data, dict):
                        student_data[rel_name] = related_model(**rel_data)
                    elif rel.uselist and isinstance(rel_data, list):
                        student_data[rel_name] = [
                            related_model(**item) if isinstance(item, dict) else item
                            for item in rel_data
                        ]
            
            admission_student = AdmissionStudent(**student_data)
            db.add(admission_student)
            await db.commit()
            await db.refresh(admission_student)
            
            # Return as dict to avoid circular reference encoding issues
            return {
                "id": str(admission_student.id),
                "name": admission_student.name,
                "email": admission_student.email,
                "student_mobile": admission_student.student_mobile,
                "enquiry_number": admission_student.enquiry_number,
                "application_number": admission_student.application_number,
                "status": admission_student.status,
                "source": admission_student.source,
                "department_id": str(admission_student.department_id) if admission_student.department_id else None,
                "course_id": str(admission_student.course_id) if admission_student.course_id else None,
                "institution_id": str(admission_student.institution_id) if admission_student.institution_id else None,
                "created_at": admission_student.created_at,
                "updated_at": admission_student.updated_at,
                "fee_structure_id": str(admission_student.fee_structure_id) if admission_student.fee_structure_id else None,
                "is_fee_structure_locked": admission_student.is_fee_structure_locked,
                "fee_structure_locked_at": admission_student.fee_structure_locked_at,
                "fee_structure_locked_by": str(admission_student.fee_structure_locked_by) if admission_student.fee_structure_locked_by else None
            }
        
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
    
    # Today's enquiries (all sources in one table now)
    stmt_today = select(func.count(AdmissionStudent.id)).where(
        func.date(AdmissionStudent.created_at) == today,
        AdmissionStudent.status == AdmissionStatusEnum.ENQUIRY
    )
    res_today = await db.execute(stmt_today)
    enquiries_today = res_today.scalar()
    
    # This week's enquiries
    stmt_week = select(func.count(AdmissionStudent.id)).where(
        func.date(AdmissionStudent.created_at) >= week_ago,
        AdmissionStudent.status.in_([AdmissionStatusEnum.ENQUIRY, AdmissionStatusEnum.APPLIED])
    )
    res_week = await db.execute(stmt_week)
    enquiries_week = res_week.scalar()
    
    # This month's enquiries
    stmt_month = select(func.count(AdmissionStudent.id)).where(
        func.date(AdmissionStudent.created_at) >= month_ago,
        AdmissionStudent.status.in_([AdmissionStatusEnum.ENQUIRY, AdmissionStatusEnum.APPLIED])
    )
    res_month = await db.execute(stmt_month)
    enquiries_month = res_month.scalar()
    
    # Status breakdown (only AdmissionStudent has detailed statuses)
    stmt_status = select(
        AdmissionStudent.status,
        func.count(AdmissionStudent.id)
    ).group_by(AdmissionStudent.status)
    
    res_status = await db.execute(stmt_status)
    status_breakdown = {str(status): count for status, count in res_status.all()}
    
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
    
    # Source breakdown (from AdmissionStudent reference_type)
    stmt_source = select(
        AdmissionStudent.reference_type,
        func.count(AdmissionStudent.id)
    ).where(
        AdmissionStudent.reference_type.isnot(None)
    ).group_by(AdmissionStudent.reference_type)
    
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
    
    if reference_type:
        query_students = query_students.where(AdmissionStudent.reference_type == reference_type)
    
    res_students = await db.execute(query_students)
    students = res_students.scalars().all()
    
    # Normalize data
    all_enquiries = [{
        "id": str(s.id),
        "enquiry_number": s.enquiry_number,
        "name": s.name,
        "mobile": s.student_mobile,
        "status": s.status,
        "source": s.source.value if s.source else None,
        "reference_type": s.reference_type,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    } for s in students]
    
    return {
        "total": len(all_enquiries),
        "data": all_enquiries
    }


@admission_entry_router.get("/reports/reference-summary", tags=["Admission - Reports"])
async def get_reference_summary(
    start_date: str = None,
    end_date: str = None,
    institution_id: str = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get admission counts grouped by consultancy and staff.
    Returns two lists: consultancy_summary and staff_summary.
    """
    from datetime import datetime as dt
    from common.models.gate.visitor_model import ConsultancyReference, StaffReference
    from common.models.admission.consultancy import Consultancy
    from common.models.master.institution import Staff, Department

    base_filters = [AdmissionStudent.deleted_at.is_(None)]

    if start_date:
        try:
            base_filters.append(AdmissionStudent.created_at >= dt.fromisoformat(start_date))
        except ValueError:
            pass
    if end_date:
        try:
            base_filters.append(AdmissionStudent.created_at <= dt.fromisoformat(end_date))
        except ValueError:
            pass
    if institution_id:
        base_filters.append(AdmissionStudent.institution_id == institution_id)

    # Consultancy summary
    consultancy_stmt = (
        select(
            Consultancy.id,
            Consultancy.name,
            func.count(AdmissionStudent.id).label("admission_count"),
        )
        .join(ConsultancyReference, ConsultancyReference.consultancy_id == Consultancy.id)
        .join(AdmissionStudent, AdmissionStudent.id == ConsultancyReference.student_id)
        .where(*base_filters)
        .group_by(Consultancy.id, Consultancy.name)
        .order_by(func.count(AdmissionStudent.id).desc())
    )
    consultancy_result = await db.execute(consultancy_stmt)
    consultancy_summary = [
        {"id": str(row.id), "name": row.name, "admission_count": row.admission_count}
        for row in consultancy_result.all()
    ]

    # Staff summary
    staff_stmt = (
        select(
            Staff.id,
            Staff.name,
            Staff.designation,
            Department.name.label("department_name"),
            func.count(AdmissionStudent.id).label("admission_count"),
        )
        .join(StaffReference, StaffReference.staff_id == Staff.id)
        .join(AdmissionStudent, AdmissionStudent.id == StaffReference.student_id)
        .outerjoin(Department, Department.id == Staff.department_id)
        .where(*base_filters)
        .group_by(Staff.id, Staff.name, Staff.designation, Department.name)
        .order_by(func.count(AdmissionStudent.id).desc())
    )
    staff_result = await db.execute(staff_stmt)
    staff_summary = [
        {
            "id": str(row.id),
            "name": row.name,
            "designation": row.designation,
            "department_name": row.department_name,
            "admission_count": row.admission_count,
        }
        for row in staff_result.all()
    ]

    # Totals
    total_consultancy = sum(c["admission_count"] for c in consultancy_summary)
    total_staff = sum(s["admission_count"] for s in staff_summary)

    # Overall total admissions
    total_stmt = select(func.count(AdmissionStudent.id)).where(*base_filters)
    total_result = await db.execute(total_stmt)
    total_admissions = total_result.scalar_one() or 0

    return {
        "total_admissions": total_admissions,
        "total_by_consultancy": total_consultancy,
        "total_by_staff": total_staff,
        "consultancy_summary": consultancy_summary,
        "staff_summary": staff_summary,
    }


@admission_entry_router.get("/reports/reference-details", tags=["Admission - Reports"])
async def get_reference_details(
    reference_type: str = None,
    reference_id: str = None,
    start_date: str = None,
    end_date: str = None,
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Get detailed admission list filtered by a specific consultancy or staff member.
    reference_type: 'consultancy' or 'staff'
    reference_id: UUID of the consultancy or staff member
    """
    from datetime import datetime as dt
    from common.models.gate.visitor_model import ConsultancyReference, StaffReference
    from common.models.admission.consultancy import Consultancy
    from common.models.master.institution import Staff

    filters = [AdmissionStudent.deleted_at.is_(None)]

    if start_date:
        try:
            filters.append(AdmissionStudent.created_at >= dt.fromisoformat(start_date))
        except ValueError:
            pass
    if end_date:
        try:
            filters.append(AdmissionStudent.created_at <= dt.fromisoformat(end_date))
        except ValueError:
            pass

    if reference_type == "consultancy" and reference_id:
        stmt = (
            select(AdmissionStudent)
            .join(ConsultancyReference, ConsultancyReference.student_id == AdmissionStudent.id)
            .where(ConsultancyReference.consultancy_id == reference_id, *filters)
        )
        count_stmt = (
            select(func.count(AdmissionStudent.id))
            .join(ConsultancyReference, ConsultancyReference.student_id == AdmissionStudent.id)
            .where(ConsultancyReference.consultancy_id == reference_id, *filters)
        )
    elif reference_type == "staff" and reference_id:
        stmt = (
            select(AdmissionStudent)
            .join(StaffReference, StaffReference.student_id == AdmissionStudent.id)
            .where(StaffReference.staff_id == reference_id, *filters)
        )
        count_stmt = (
            select(func.count(AdmissionStudent.id))
            .join(StaffReference, StaffReference.student_id == AdmissionStudent.id)
            .where(StaffReference.staff_id == reference_id, *filters)
        )
    else:
        return {"items": [], "total": 0, "page": page, "size": size, "pages": 0}

    # Total count
    total_res = await db.execute(count_stmt)
    total = total_res.scalar_one() or 0
    pages = (total + size - 1) // size if size > 0 else 0

    # Paginated data
    offset = (page - 1) * size
    stmt = stmt.order_by(desc(AdmissionStudent.created_at)).offset(offset).limit(size)
    result = await db.execute(stmt)
    students = result.scalars().all()

    items = [
        {
            "id": str(s.id),
            "enquiry_number": s.enquiry_number,
            "name": s.name,
            "mobile": s.student_mobile,
            "parent_name": s.father_name,
            "native_place": s.native_place,
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "reference_type": s.reference_type,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "institution_id": str(s.institution_id) if s.institution_id else None,
            "department_id": str(s.department_id) if s.department_id else None,
        }
        for s in students
    ]

    return {"items": items, "total": total, "page": page, "size": size, "pages": pages}


lead_followup_router = APIRouter()

lead_followup_crud_router = create_crud_routes(
    LeadFollowUp,
    LeadFollowUpCreate,
    LeadFollowUpUpdate,
    LeadFollowUpResponse,
)

@lead_followup_router.get(
    "/student/{student_id}",
    tags=["Admission - Lead Follow-up"]
)
async def get_student_followup_history(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Get follow-up history for a specific student."""
    query = select(LeadFollowUp).options(raiseload("*")).where(LeadFollowUp.student_id == student_id).order_by(desc(LeadFollowUp.created_at))
    result = await db.execute(query)
    followups = result.scalars().all()
    
    # Return as list of dicts to avoid circular reference encoding issues
    return [
        {
            "id": str(f.id),
            "student_id": str(f.student_id),
            "remark": f.remark,
            "status": f.status,
            "next_follow_up_date": f.next_follow_up_date,
            "created_at": f.created_at,
            "created_by": str(f.created_by) if f.created_by else None
        }
        for f in followups
    ]

lead_followup_router.include_router(
    lead_followup_crud_router, prefix="/records", tags=["Admission - Lead Follow-up"]
)


@lead_followup_router.get(
    "/leads",
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

    # Paginate and return — use DISTINCT ON primary key to avoid DISTINCT
    # across all selected columns (some may be JSON without equality ops).
    pk = getattr(AdmissionStudent, "id", None)
    if pk is not None:
        query = query.distinct(pk)
    else:
        query = query.distinct()

    return await paginate(db, query)


admission_router = APIRouter()

@admission_router.get("/applied", tags=["Admission - Admission Students"])
async def get_applied_admission_students(
    db: AsyncSession = Depends(get_db_session)
):
    """Get all admission students with status 'Applied'."""
    from sqlalchemy.orm import raiseload
    result = await db.execute(
        select(AdmissionStudent).where(AdmissionStudent.status == AdmissionStatusEnum.APPLIED.value).options(raiseload("*"))
    )
    students = result.scalars().all()
    # Return dict format to avoid circular reference encoding
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "enquiry_number": s.enquiry_number,
            "application_number": s.application_number,
            "status": s.status,
            "student_mobile": s.student_mobile,
            "department_id": str(s.department_id) if s.department_id else None,
            "course_id": str(s.course_id) if s.course_id else None,
            "institution_id": str(s.institution_id) if s.institution_id else None,
        }
        for s in students
    ]


# Import schemas
from common.schemas.admission.admission_entry import BookAdmissionRequest, BookAdmissionResponse, UpdateCourseRequest
from apps.billing.services import billing_service

@admission_router.post(
    "/admission-students/{student_id}/book-admission",
    tags=["Admission - Admission Students"],
    summary="Book Admission (Generate App No & Assign Fees)",
    response_model=BookAdmissionResponse
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
        student.status = AdmissionStatusEnum.BOOKED.value  # Changed to BOOKED status
        db.add(student)  # Ensure student record is tracked
        
        # 3. Assign Fees (Auto-resolve if not provided) - Non-critical, log but don't fail
        try:
            await billing_service.assign_course_fees(db, student_id, fee_structure_id=None)
        except Exception as fee_err:
            logger.warning(f"Failed to assign course fees for student {student_id}: {str(fee_err)}")
        
        # 4. Assign Application Fee (if configured) - Non-critical
        try:
            demand = await billing_service.assign_application_fee(db, student_id)
            if demand:
                # Auto-Invoice the application fee for Cash Counter availability
                await billing_service.create_invoice_from_demands(db, [demand])
        except Exception as app_fee_err:
            logger.warning(f"Failed to assign application fee for student {student_id}: {str(app_fee_err)}")
        
        await db.commit()
        await db.refresh(student)
        
        # Return response with only essential data to avoid circular references
        return BookAdmissionResponse(
            id=student.id,
            application_number=student.application_number,
            status=student.status,
            enquiry_number=student.enquiry_number,
            name=student.name
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Book admission failed for student {student_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to book admission: {str(e)}")


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

    if getattr(student, "is_fee_structure_locked", False):
        raise HTTPException(
            status_code=400,
            detail="Fee structure is locked for this student. Course/department change is not allowed.",
        )
        
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
    "/admission-students/{student_id}/set-fee-structure-lock",
    response_model=AdmissionStudentResponse,
    tags=["Admission - Admission Students"],
    summary="Set and lock final fee structure for student",
)
async def set_fee_structure_and_lock(
    student_id: UUID,
    payload: SetFeeStructureLockRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    current_status = student.status.value if hasattr(student.status, "value") else str(student.status)
    allowed_statuses = {
        AdmissionStatusEnum.APPLIED.value,
        AdmissionStatusEnum.PROVISIONALLY_ALLOTTED.value,
        AdmissionStatusEnum.ENROLLED.value,
    }
    if current_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Fee structure can be set and locked only for "
                "APPLIED, PROVISIONALLY_ALLOTTED, or ENROLLED students"
            ),
        )

    if student.is_fee_structure_locked and student.fee_structure_id:
        raise HTTPException(
            status_code=409,
            detail="Fee structure is already locked for this student",
        )

    try:
        user_id = await get_user_id(request)
    except Exception:
        user_id = None

    try:
        await billing_service.lock_student_fee_structure(
            db,
            student_id=student_id,
            fee_structure_id=payload.fee_structure_id,
            locked_by=user_id,
        )
        await db.commit()

        # Re-fetch with eager loads used by AdmissionStudentResponse
        # to avoid lazy-load failures during response validation.
        refreshed_query = (
            select(AdmissionStudent)
            .options(
                selectinload(AdmissionStudent.sslc_details),
                selectinload(AdmissionStudent.hsc_details),
                selectinload(AdmissionStudent.diploma_details),
                selectinload(AdmissionStudent.pg_details),
            )
            .where(AdmissionStudent.id == student_id)
        )
        refreshed_result = await db.execute(refreshed_query)
        refreshed_student = refreshed_result.scalar_one_or_none()

        if not refreshed_student:
            raise HTTPException(status_code=404, detail="Student not found after update")

        return refreshed_student
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@admission_router.post(
    "/admission-students/{student_id}/assign-roll",
    tags=["Admission - Admission Students"],
    summary="Assign Roll Number"
)
async def assign_roll_number(
    student_id: UUID,
    payload: AssignRollNumberRequest,
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    roll_number = payload.roll_number.strip()
    if not roll_number:
        raise HTTPException(status_code=400, detail="roll_number cannot be empty")

    duplicate_stmt = select(AdmissionStudent.id).where(
        AdmissionStudent.id != student_id,
        AdmissionStudent.institution_id == student.institution_id,
        AdmissionStudent.roll_number == roll_number,
    )
    duplicate_res = await db.execute(duplicate_stmt)
    if duplicate_res.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Roll number '{roll_number}' is already in use for this institution",
        )

    student.roll_number = roll_number
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@admission_router.post(
    "/admission-students/{student_id}/assign-section",
    tags=["Admission - Admission Students"],
    summary="Assign Section"
)
async def assign_section(
    student_id: UUID,
    payload: AssignSectionRequest,
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    section = payload.section.strip()
    if not section:
        raise HTTPException(status_code=400, detail="section cannot be empty")

    student.section = section
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


@admission_router.post(
    "/admission-students/{student_id}/activate-sem1",
    tags=["Admission - Admission Students"],
    summary="Activate Semester 1 and Enroll Student"
)
async def activate_sem1(
    student_id: UUID,
    payload: ActivateSem1Request,
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if student.status != AdmissionStatusEnum.PROVISIONALLY_ALLOTTED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Only PROVISIONALLY_ALLOTTED students can be activated to Sem1. Current status: {student.status}",
        )

    roll_number = (payload.roll_number or student.roll_number or "").strip()
    section = (payload.section or student.section or "").strip()

    if not roll_number or not section:
        raise HTTPException(
            status_code=400,
            detail="roll_number and section are required to activate Sem1",
        )

    duplicate_stmt = select(AdmissionStudent.id).where(
        AdmissionStudent.id != student_id,
        AdmissionStudent.institution_id == student.institution_id,
        AdmissionStudent.roll_number == roll_number,
    )
    duplicate_res = await db.execute(duplicate_stmt)
    if duplicate_res.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Roll number '{roll_number}' is already in use for this institution",
        )

    student.roll_number = roll_number
    student.section = section
    student.status = AdmissionStatusEnum.ENROLLED.value
    student.current_semester = 1
    student.is_sem1_active = True
    student.enrolled_at = datetime.utcnow()
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


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


@admission_router.post(
    "/admission-students/{student_id}/mark-applied",
    tags=["Admission - Admission Students"],
    summary="Mark Student as Applied after Document Submission"
)
async def mark_student_applied(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Mark student as APPLIED after all required documents are submitted.
    This endpoint should be called manually when all documents are collected.
    Status transition: BOOKED -> APPLIED
    """
    # 1. Fetch Student
    stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check if student is in BOOKED status
    if student.status != AdmissionStatusEnum.BOOKED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Only students with BOOKED status can be marked as APPLIED. Current status: {student.status}"
        )
    
    try:
        # Update status to APPLIED
        student.status = AdmissionStatusEnum.APPLIED.value
        db.add(student)
        await db.commit()
        await db.refresh(student)
        return student
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@admission_entry_router.patch(
    "/admission-students/{id}/status",
    tags=["Admission - Admission Students"],
    name="Update Admission Student Status"
)
async def update_admission_student_status(
    id: UUID,
    new_status: AdmissionStatusEnum,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Update the status of an admission student.
    """
    query = select(AdmissionStudent).where(AdmissionStudent.id == id)
    result = await db.execute(query)
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission student with ID {id} not found"
        )

    # Validate status transition
    if student.status != AdmissionStatusEnum.BOOKED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status can only be changed from BOOKED to APPLIED."
        )

    if new_status != AdmissionStatusEnum.APPLIED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status transition."
        )

    # Update status
    student.status = new_status
    db.add(student)
    await db.commit()

    return {"message": "Status updated successfully", "id": str(id), "new_status": new_status.value}


add_pagination(admission_router)
add_pagination(lead_followup_router)
add_pagination(admission_entry_router)
