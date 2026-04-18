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
from fastapi_pagination import add_pagination, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi_querybuilder.dependencies import QueryBuilder
from fastapi import Request

from common.models.admission.admission_entry import AdmissionGateEntry, AdmissionStudent, AdmissionStudentProgramDetails, AdmissionStatusEnum
from common.models.admission.lead_followup import LeadFollowUp
from common.schemas.admission.admission_entry import (
    AdmissionStudentCreate,
    AdmissionStudentResponse,
    AdmissionStudentUpdate,
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
from sqlalchemy import select, desc, and_, or_, cast, String
from sqlalchemy import func
from sqlalchemy.orm import selectinload, raiseload
from uuid import UUID
from typing import List
from datetime import datetime, time
from common.models.master.institution import Department, Course
from common.models.master.annual_task import AcademicYear

from common.models.billing.application_fees import Invoice, InvoiceLineItem
from components.generator.utils.get_user_from_request import get_user_id
import logging

logger = logging.getLogger(__name__)


def _serialize_admission_student(student: AdmissionStudent) -> dict:
    """
    Convert an AdmissionStudent ORM row to a JSON-safe dict using only table columns.
    Relationships are intentionally excluded to prevent recursive JSON encoding.
    """
    mapper = inspect(student.__class__)
    serialized = {}
    for column in mapper.columns:
        value = getattr(student, column.name, None)
        if isinstance(value, UUID):
            serialized[column.name] = str(value)
        elif hasattr(value, "isoformat"):
            serialized[column.name] = value.isoformat()
        elif hasattr(value, "value"):
            serialized[column.name] = value.value
        else:
            serialized[column.name] = value
    return serialized


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
        selectinload(AdmissionStudent.fee_structure),
        selectinload(AdmissionStudent.consultancy_reference),
        selectinload(AdmissionStudent.staff_reference),
        selectinload(AdmissionStudent.student_reference),
        selectinload(AdmissionStudent.other_reference),
        selectinload(AdmissionStudent.gate_entry),
        selectinload(AdmissionStudent.personal_details),
        selectinload(AdmissionStudent.program_details),
        selectinload(AdmissionStudent.previous_academic_details),
    ).where(AdmissionStudent.id == id)
    
    result = await db.execute(query)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission student with ID {id} not found"
        )
    
    # Return as dict to avoid circular reference encoding issues
    # Resolve readable department/course names from relationships (if loaded)
    from common.models.master.institution import Department, Course, Institution
    dept_name = None
    course_title = None
    institution_name = None
    if student.program_details:
        if student.program_details.department_id:
            dept = await db.scalar(select(Department.name).where(Department.id == student.program_details.department_id))
            dept_name = dept
        if student.program_details.course_id:
            course = await db.scalar(select(Course.title).where(Course.id == student.program_details.course_id))
            course_title = course
        if student.program_details.institution_id:
            inst = await db.scalar(select(Institution.name).where(Institution.id == student.program_details.institution_id))
            institution_name = inst

    admission_quota_name = None
    if student.program_details and getattr(student.program_details, 'admission_quota_id', None):
        from common.models.master.admission_masters import SeatQuota
        admission_quota_name = await db.scalar(select(SeatQuota.name).where(SeatQuota.id == student.program_details.admission_quota_id))

    admission_type_name = None
    if student.program_details and getattr(student.program_details, 'admission_type_id', None):
        from common.models.master.admission_masters import AdmissionType
        admission_type_name = await db.scalar(select(AdmissionType.name).where(AdmissionType.id == student.program_details.admission_type_id))

    academic_year_name = None
    ay_id_to_check = student.program_details.academic_year_id if student.program_details else None
    if ay_id_to_check:
        from common.models.master.annual_task import AcademicYear
        academic_year_name = await db.scalar(select(AcademicYear.year_name).where(AcademicYear.id == ay_id_to_check))

    staff_name = None
    if student.staff_reference and student.staff_reference.staff_id:
        from common.models.master.institution import Staff
        staff_name = await db.scalar(select(Staff.name).where(Staff.id == student.staff_reference.staff_id))

    # Helper function to convert nested objects to dict
    def obj_to_dict(obj):
        if obj is None:
            return None
        return {col.name: getattr(obj, col.name, None) for col in obj.__table__.columns}

    # Helper to safely get nested attribute
    def get_nested(obj, *attrs, default=None):
        for attr in attrs:
            if not obj:
                return default
            obj = getattr(obj, attr, None)
        return obj if obj is not None else default

    prog = student.program_details
    pers = student.personal_details
    prev = student.previous_academic_details
    gate = student.gate_entry

    religion_val = get_nested(pers, "religion")
    community_val = get_nested(pers, "community")
    caste_val = get_nested(pers, "caste")

    import uuid
    def is_valid_uuid(val):
        try:
            uuid.UUID(str(val))
            return True
        except (ValueError, TypeError):
            return False

    if is_valid_uuid(religion_val):
        from common.models.meta.models import Religion
        real_religion = await db.scalar(select(Religion.name).where(Religion.id == uuid.UUID(str(religion_val))))
        if real_religion: religion_val = real_religion

    if is_valid_uuid(community_val):
        from common.models.meta.models import Community
        real_community = await db.scalar(select(Community.name).where(Community.id == uuid.UUID(str(community_val))))
        if real_community: community_val = real_community

    if is_valid_uuid(caste_val):
        from common.models.meta.models import Caste
        real_caste = await db.scalar(select(Caste.name).where(Caste.id == uuid.UUID(str(caste_val))))
        if real_caste: caste_val = real_caste

    return {
        "id": str(student.id),
        "name": get_nested(pers, "name"),
        "email": get_nested(pers, "email"),
        "father_name": get_nested(pers, "father_name"),
        "gender": get_nested(pers, "gender"),
        "date_of_birth": get_nested(pers, "date_of_birth"),
        "student_mobile": get_nested(pers, "student_mobile"),
        "parent_mobile": get_nested(pers, "parent_mobile"),
        "aadhaar_number": get_nested(pers, "aadhaar_number"),
        "enquiry_number": student.enquiry_number,
        "application_number": student.application_number,
        "gate_pass_number": get_nested(gate, "gate_pass_number"),
        "reference_type": get_nested(gate, "reference_type"),
        "gate_entry_id": str(student.gate_entry_id) if student.gate_entry_id else None,
        "religion": religion_val,
        "community": community_val,
        "caste": caste_val,
        "parent_income": float(get_nested(pers, "parent_income")) if get_nested(pers, "parent_income") else None,
        "door_no": get_nested(pers, "door_no"),
        "street_name": get_nested(pers, "street_name"),
        "village_name": get_nested(pers, "village_name"),
        "taluk": get_nested(pers, "taluk"),
        "district": get_nested(pers, "district"),
        "state": get_nested(pers, "state"),
        "pincode": get_nested(pers, "pincode"),
        "parent_address": get_nested(pers, "parent_address"),
        "permanent_address": get_nested(pers, "permanent_address"),
        "campus": get_nested(prog, "campus"),
        "has_vehicle": get_nested(gate, "vehicle", default=False),
        "vehicle_number": get_nested(gate, "vehicle_number"),
        "status": student.status,
        "source": getattr(student, "source", None),
        "category": get_nested(prog, "category"),
        "quota_type": get_nested(prog, "quota_type"),
        "special_quota": get_nested(prog, "special_quota"),
        "scholarships": get_nested(prog, "scholarships"),
        "boarding_place": get_nested(prog, "boarding_place"),
        "previous_academic_level": get_nested(prog, "previous_academic_level"),
        "is_lateral_entry": get_nested(prog, "is_lateral_entry", default=False),
        "roll_number": student.roll_number,
        "section": student.section,
        "current_semester": student.current_semester,
        "enrolled_at": student.enrolled_at,
        "department_id": str(get_nested(prog, "department_id")) if get_nested(prog, "department_id") else None,
        "department": dept_name,
        "course_id": str(get_nested(prog, "course_id")) if get_nested(prog, "course_id") else None,
        "course": course_title,
        "institution_id": str(get_nested(prog, "institution_id")) if get_nested(prog, "institution_id") else None,
        "institution": institution_name,
        "admission_quota_id": str(get_nested(prog, "admission_quota_id")) if get_nested(prog, "admission_quota_id") else None,
        "admission_quota": admission_quota_name,
        "admission_type_id": str(get_nested(prog, "admission_type_id")) if get_nested(prog, "admission_type_id") else None,
        "admission_type": admission_type_name,
        "academic_year_id": str(ay_id_to_check) if ay_id_to_check else None,
        "academic_year": academic_year_name,
        "sslc_details": get_nested(prev, "sslc"),
        "hsc_details": get_nested(prev, "hsc"),
        "diploma_details": get_nested(prev, "diploma"),
        "pg_details": get_nested(prev, "degree"),
        "consultancy_reference": obj_to_dict(student.consultancy_reference),
        "staff_reference": {**obj_to_dict(student.staff_reference), "staff_name": staff_name} if student.staff_reference else None,
        "student_reference": obj_to_dict(student.student_reference),
        "other_reference": obj_to_dict(student.other_reference),
        "gate_entry": obj_to_dict(student.gate_entry),
        "personal_details": obj_to_dict(student.personal_details),
        "program_details": obj_to_dict(student.program_details),
        "previous_academic_details": obj_to_dict(student.previous_academic_details),
        "created_at": student.created_at,
        "updated_at": student.updated_at,
        "fee_structure_id": str(student.fee_structure_id) if student.fee_structure_id else None,
        "is_fee_structure_locked": student.is_fee_structure_locked,
        "fee_structure_locked_at": student.fee_structure_locked_at,
        "fee_structure_locked_by": str(student.fee_structure_locked_by) if student.fee_structure_locked_by else None
    }


@admission_entry_router.get(
    "/admission-students/by-gate-pass/{gate_pass_no:path}",
    name="Get Admission Student By Gate Pass",
    tags=["Admission - Admission Students"],
)
async def get_admission_student_by_gate_pass(
    gate_pass_no: str,
    db: AsyncSession = Depends(get_db_session),
):
    normalized_gate_pass = (gate_pass_no or "").strip()
    if not normalized_gate_pass:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="gate_pass_no is required",
        )

    query = (
        select(AdmissionStudent.id)
        .where(
            AdmissionStudent.deleted_at.is_(None),
            AdmissionStudent.gate_entry.has(
                AdmissionGateEntry.gate_pass_number == normalized_gate_pass
            ),
        )
        .order_by(desc(AdmissionStudent.updated_at), desc(AdmissionStudent.created_at))
        .limit(1)
    )

    result = await db.execute(query)
    student_id = result.scalar_one_or_none()
    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admission student with gate pass {normalized_gate_pass} not found",
        )

    return await get_admission_student(student_id, db)


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
        from common.models.admission.admission_entry import AdmissionStudentPersonalDetails, AdmissionStudentProgramDetails
        # Base filters: student.status == BOOKED or APPLIED
        from sqlalchemy import or_
        filters = [
            or_(
                AdmissionStudent.status == AdmissionStatusEnum.BOOKED.value,
                AdmissionStudent.status == AdmissionStatusEnum.APPLIED.value,
                AdmissionStudent.status == "PROVISIONALLY_ALLOTTED",
            )
        ]

        if q:
            qfilter = f"%{q}%"
            filters.append(
                (AdmissionStudentPersonalDetails.name.ilike(qfilter)) | (AdmissionStudent.application_number.ilike(qfilter))
            )

        # Total count
        count_stmt = select(func.count(AdmissionStudent.id)).outerjoin(AdmissionStudentPersonalDetails).where(*filters)
        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        # Paging
        offset = (page - 1) * size

        stmt = select(AdmissionStudent).outerjoin(AdmissionStudentPersonalDetails).options(
            selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.department), selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.course), selectinload(AdmissionStudent.personal_details)
        ).where(*filters).order_by(desc(AdmissionStudent.created_at)).offset(offset).limit(size)
        res = await db.execute(stmt)
        students = res.scalars().all()

        items = []
        # Batch-load fee structure names for all students
        fee_structure_ids = {s.fee_structure_id for s in students if getattr(s, "fee_structure_id", None)}
        fee_structure_name_map = {}
        if fee_structure_ids:
            from common.models.billing.fee_structure import FeeStructure
            fs_stmt = select(FeeStructure.id, FeeStructure.name).where(FeeStructure.id.in_(fee_structure_ids))
            fs_res = await db.execute(fs_stmt)
            fee_structure_name_map = {str(row[0]): row[1] for row in fs_res.all()}

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
            pd = getattr(s, "program_details", None)
            if pd and getattr(pd, "department", None):
                dept_name = getattr(pd.department, "name", None)
            if pd and getattr(pd, "course", None):
                course_title = getattr(pd.course, "title", None)
                
            fs_id_str = str(s.fee_structure_id) if getattr(s, "fee_structure_id", None) else None
            
            s_name = getattr(s.personal_details, "name", None) if getattr(s, "personal_details", None) else getattr(s, "name", None)

            items.append(
                {
                    "id": str(s.id),
                    "application_number": s.application_number,
                    "name": s_name,
                    "department": dept_name,
                    "course": course_title,
                    "booking_date": s.created_at.isoformat() if getattr(s, "created_at", None) else None,
                    "amount_paid": float(inv.paid_amount) if inv and inv.paid_amount is not None else None,
                    "invoice_id": str(inv.id) if inv else None,
                    "invoice_status": inv.status if inv else None,
                    "status": s.status,
                    "fee_structure_id": fs_id_str,
                    "fee_structure_name": fee_structure_name_map.get(fs_id_str) if fs_id_str else None,
                    "is_fee_structure_locked": getattr(s, "is_fee_structure_locked", False),
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
        from common.models.admission.admission_entry import AdmissionStudentPersonalDetails, AdmissionStudentProgramDetails
        from sqlalchemy import or_
        filters = [
            or_(
                AdmissionStudent.status == AdmissionStatusEnum.BOOKED.value,
                AdmissionStudent.status == AdmissionStatusEnum.APPLIED.value,
                AdmissionStudent.status == "PROVISIONALLY_ALLOTTED",
            )
        ]

        if q:
            qfilter = f"%{q}%"
            filters.append(
                (AdmissionStudentPersonalDetails.name.ilike(qfilter)) | (AdmissionStudent.application_number.ilike(qfilter))
            )

        # Total count
        count_stmt = select(func.count(AdmissionStudent.id)).outerjoin(AdmissionStudentPersonalDetails).where(*filters)
        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        # Paging
        offset = (page - 1) * size

        stmt = select(AdmissionStudent).outerjoin(AdmissionStudentPersonalDetails).options(
            selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.department), selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.course), selectinload(AdmissionStudent.personal_details)
        ).where(*filters).order_by(desc(AdmissionStudent.created_at)).offset(offset).limit(size)
        res = await db.execute(stmt)
        students = res.scalars().all()

        items = []

        # Batch-load fee structure names for all students
        fee_structure_ids = {s.fee_structure_id for s in students if getattr(s, "fee_structure_id", None)}
        fee_structure_name_map = {}
        if fee_structure_ids:
            from common.models.billing.fee_structure import FeeStructure
            fs_stmt = select(FeeStructure.id, FeeStructure.name).where(FeeStructure.id.in_(fee_structure_ids))
            fs_res = await db.execute(fs_stmt)
            fee_structure_name_map = {str(row[0]): row[1] for row in fs_res.all()}

        for s in students:
            dept_name = None
            course_title = None
            pd = getattr(s, "program_details", None)
            if pd and getattr(pd, "department", None):
                dept_name = getattr(pd.department, "name", None)
            if pd and getattr(pd, "course", None):
                course_title = getattr(pd.course, "title", None)
                
            fs_id_str = str(s.fee_structure_id) if getattr(s, "fee_structure_id", None) else None
            
            s_name = getattr(s.personal_details, "name", None) if getattr(s, "personal_details", None) else getattr(s, "name", None)

            items.append(
                {
                    "id": str(s.id),
                    "application_number": s.application_number,
                    "name": s_name,
                    "department": dept_name,
                    "course": course_title,
                    "enrollment_date": s.created_at.isoformat() if getattr(s, "created_at", None) else None,
                    "status": s.status,
                    "fee_structure_id": fs_id_str,
                    "fee_structure_name": fee_structure_name_map.get(fs_id_str) if fs_id_str else None,
                    "is_fee_structure_locked": getattr(s, "is_fee_structure_locked", False),
                }
            )

        pages = (total + size - 1) // size if size > 0 else 1

        return {"items": items, "total": total, "page": page, "pages": pages, "size": size}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@admission_entry_router.post(
    "/admission-students/{student_id}/set-fee-structure",
    tags=["Admission - Admission Students"],
    name="Set Temporary Fee Structure",
    summary="Set temporary fee structure for booked/applied student",
)
async def set_temporary_fee_structure(
    student_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Set temporary fee structure for BOOKED/APPLIED students (without locking).
    Can be changed later until fee structure is locked.
    """
    try:
        from uuid import UUID
        from sqlalchemy import update
        
        # Convert student_id to UUID
        student_uuid = UUID(student_id)
        
        # Get the student
        stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_uuid)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()

        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Check if student is in allowed status
        current_status = student.status
        allowed_statuses = {"BOOKED", "APPLIED", "PROVISIONALLY_ALLOTTED", "ENROLLED"}
        if current_status not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Fee structure can be set for BOOKED, APPLIED, PROVISIONALLY_ALLOTTED, or ENROLLED students, current status: {current_status}",
            )

        # Check if already locked
        if getattr(student, "is_fee_structure_locked", False):
            raise HTTPException(
                status_code=409,
                detail="Fee structure is locked for this student. Cannot modify.",
            )

        # Update fee structure
        fee_structure_id = payload.get("fee_structure_id")
        update_stmt = (
            update(AdmissionStudent)
            .where(AdmissionStudent.id == student_uuid)
            .values(fee_structure_id=fee_structure_id)
        )
        await db.execute(update_stmt)
        await db.commit()

        # Fetch and return updated student
        refreshed_stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_uuid)
        refreshed_res = await db.execute(refreshed_stmt)
        updated_student = refreshed_res.scalar_one_or_none()

        return {
            "id": str(updated_student.id),
            "application_number": updated_student.application_number,
            "name": getattr(student.personal_details, "name", None) if getattr(student, "personal_details", None) else getattr(student, "name", None),
            "fee_structure_id": str(updated_student.fee_structure_id) if updated_student.fee_structure_id else None,
            "is_fee_structure_locked": getattr(updated_student, "is_fee_structure_locked", False),
            "status": updated_student.status,
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@admission_entry_router.post(
    "/admission-students/{student_id}/provisionally-allot",
    tags=["Admission - Admission Students"],
    name="Provisionally Allot Student",
    summary="Change student status to PROVISIONALLY_ALLOTTED",
)
async def provisionally_allot_student(
    student_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Change student status from APPLIED to PROVISIONALLY_ALLOTTED.
    Does NOT require fee structure to be set.
    Fee structure can be set/locked later.
    """
    try:
        from uuid import UUID
        from sqlalchemy import update
        
        # Convert student_id to UUID
        student_uuid = UUID(student_id)
        
        # Get the student
        stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_uuid)
        res = await db.execute(stmt)
        student = res.scalar_one_or_none()

        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Check current status
        current_status = student.status
        if current_status != "APPLIED":
            raise HTTPException(
                status_code=400,
                detail=f"Student must be in APPLIED status to provisionally allot, current status: {current_status}",
            )

        # Update status to PROVISIONALLY_ALLOTTED
        update_stmt = (
            update(AdmissionStudent)
            .where(AdmissionStudent.id == student_uuid)
            .values(status="PROVISIONALLY_ALLOTTED")
        )
        await db.execute(update_stmt)
        await db.commit()

        # Fetch and return updated student
        refreshed_stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_uuid)
        refreshed_res = await db.execute(refreshed_stmt)
        updated_student = refreshed_res.scalar_one_or_none()

        return {
            "id": str(updated_student.id),
            "application_number": updated_student.application_number,
            "name": getattr(student.personal_details, "name", None) if getattr(student, "personal_details", None) else getattr(student, "name", None),
            "status": updated_student.status,
            "fee_structure_id": str(updated_student.fee_structure_id) if updated_student.fee_structure_id else None,
            "is_fee_structure_locked": getattr(updated_student, "is_fee_structure_locked", False),
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
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
        from common.models.admission.admission_entry import AdmissionStudentPersonalDetails, AdmissionGateEntry, AdmissionStudentProgramDetails
        logger = logging.getLogger(__name__)
        
        # Build base query
        query_filters = [AdmissionStudent.deleted_at == None]
        
        # Apply search filter (only on important non-JSON fields)
        if search:
            search_pattern = f"%{search}%"
            query_filters.append(
                or_(
                    AdmissionStudentPersonalDetails.name.ilike(search_pattern),
                    AdmissionGateEntry.gate_pass_number.ilike(search_pattern),
                    AdmissionStudent.enquiry_number.ilike(search_pattern),
                    AdmissionStudent.application_number.ilike(search_pattern),
                    AdmissionStudent.roll_number.ilike(search_pattern),
                    AdmissionStudentPersonalDetails.student_mobile.ilike(search_pattern),
                    AdmissionStudentPersonalDetails.parent_mobile.ilike(search_pattern),
                    AdmissionStudentPersonalDetails.father_name.ilike(search_pattern),
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
                        "name": AdmissionStudentPersonalDetails.name,
                        "enquiry_number": AdmissionStudent.enquiry_number,
                        "application_number": AdmissionStudent.application_number,
                        "roll_number": AdmissionStudent.roll_number,
                        "student_mobile": AdmissionStudentPersonalDetails.student_mobile,
                        "parent_mobile": AdmissionStudentPersonalDetails.parent_mobile,
                        "father_name": AdmissionStudentPersonalDetails.father_name,
                        "gate_pass_number": AdmissionGateEntry.gate_pass_number,
                    }

                    uuid_columns = {
                        "institution_id": AdmissionStudentProgramDetails.institution_id,
                        "department_id": AdmissionStudentProgramDetails.department_id,
                        "course_id": AdmissionStudentProgramDetails.course_id,
                        "academic_year_id": AdmissionStudentProgramDetails.academic_year_id,
                    }

                    date_columns = {
                        "created_at": AdmissionStudent.created_at,
                        "updated_at": AdmissionStudent.updated_at,
                    }

                    boolean_columns = {
                        "is_fee_structure_locked": AdmissionStudent.is_fee_structure_locked,
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
                        
                    if field_name in boolean_columns:
                        column = boolean_columns[field_name]
                        # Handle strings from JSON like "true", "false", or boolean true/false
                        bool_value = str(raw_value).strip().lower() in {'true', '1', 'yes', 'y'}
                        if operator == "$eq":
                            return column == bool_value
                        elif operator == "$ne":
                            return column != bool_value
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
        count_query = select(func.count(AdmissionStudent.id)).outerjoin(AdmissionStudentPersonalDetails).outerjoin(AdmissionStudentProgramDetails).outerjoin(AdmissionGateEntry).where(and_(*query_filters))
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0
        
        # Fetch paginated data
        offset = (page - 1) * size
        data_query = select(AdmissionStudent).outerjoin(AdmissionStudentPersonalDetails).outerjoin(AdmissionStudentProgramDetails).outerjoin(AdmissionGateEntry).options(
            selectinload(AdmissionStudent.program_details), 
            selectinload(AdmissionStudent.personal_details),
            selectinload(AdmissionStudent.previous_academic_details),
            selectinload(AdmissionStudent.gate_entry)
        ).where(and_(*query_filters)).order_by(desc(AdmissionStudent.created_at)).offset(offset).limit(size)
        
        result = await db.execute(data_query)
        students = result.scalars().all()
        
        department_ids = {student.program_details.department_id for student in students if student.program_details and student.program_details.department_id}
        course_ids = {student.program_details.course_id for student in students if student.program_details and student.program_details.course_id}
        academic_year_ids = {
            student.program_details.academic_year_id
            for student in students
            if student.program_details and student.program_details.academic_year_id
        }

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

            # Serialize relationships
            def serialize_model(model_obj):
                if not model_obj:
                    return None
                model_dict = {}
                m_mapper = inspect(model_obj.__class__)
                for col in m_mapper.columns:
                    val = getattr(model_obj, col.name)
                    if hasattr(val, 'isoformat'):
                        model_dict[col.name] = val.isoformat()
                    elif hasattr(val, 'value'):
                        model_dict[col.name] = val.value
                    elif hasattr(val, 'hex'):
                        model_dict[col.name] = str(val)
                    else:
                        model_dict[col.name] = val
                return model_dict

            student_dict["personal_details"] = serialize_model(student.personal_details)
            student_dict["program_details"] = serialize_model(student.program_details)
            student_dict["previous_academic_details"] = serialize_model(student.previous_academic_details)
            student_dict["gate_entry"] = serialize_model(student.gate_entry)
            student_dict["gate_pass_number"] = getattr(student.gate_entry, "gate_pass_number", None) if getattr(student, "gate_entry", None) else None

            student_dict["department_name"] = department_name_map.get(str(student.program_details.department_id)) if student.program_details and getattr(student.program_details, 'department_id', None) else None
            student_dict["course_title"] = course_title_map.get(str(student.program_details.course_id)) if student.program_details and getattr(student.program_details, 'course_id', None) else None
            student_dict["academic_year_name"] = academic_year_name_map.get(
                str(student.program_details.academic_year_id)
            ) if student.program_details and getattr(student.program_details, "academic_year_id", None) else None

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
            detail="Only PROVISIONALLY_ALLOTTED bulk update is supported via this endpoint. Use /bulk-waitlist or /bulk-cancel for other statuses.",
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

    # Allow both APPLIED and WAITLISTED → PROVISIONALLY_ALLOTTED
    valid_source_statuses = {AdmissionStatusEnum.APPLIED.value, AdmissionStatusEnum.WAITLISTED.value}

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
            results.append(
                BulkAdmissionStatusUpdateResult(
                    student_id=student_id,
                    success=True,
                    message="Already in PROVISIONALLY_ALLOTTED status",
                )
            )
            continue

        if current_status != AdmissionStatusEnum.APPLIED.value and current_status not in valid_source_statuses:
            results.append(
                BulkAdmissionStatusUpdateResult(
                    student_id=student_id,
                    success=False,
                    message=f"Invalid transition from {current_status}",
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
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed during bulk admission status update: {str(e)}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Bulk update failed: {str(e)}")

    failed_count = len([item for item in results if not item.success])

    return BulkAdmissionStatusUpdateResponse(
        total_requested=len(payload.student_ids),
        updated_count=updated_count,
        failed_count=failed_count,
        results=results,
    )


# ── Bulk Waitlist ─────────────────────────────────────
@admission_entry_router.post(
    "/admission-students/bulk-waitlist",
    tags=["Admission - Admission Students"],
    name="Bulk Waitlist Students",
)
async def bulk_waitlist_students(
    payload: BulkAdmissionStatusUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Bulk transition APPLIED students → WAITLISTED."""
    if not payload.student_ids:
        raise HTTPException(status_code=400, detail="student_ids cannot be empty")

    query = select(AdmissionStudent).where(
        AdmissionStudent.id.in_(payload.student_ids),
        AdmissionStudent.deleted_at.is_(None),
    )
    result = await db.execute(query)
    student_map = {s.id: s for s in result.scalars().all()}

    updated, results = 0, []
    valid_from = {AdmissionStatusEnum.APPLIED.value, "APPLIED"}

    for sid in payload.student_ids:
        student = student_map.get(sid)
        if not student:
            results.append(BulkAdmissionStatusUpdateResult(student_id=sid, success=False, message="Student not found"))
            continue
        cur = student.status.value if hasattr(student.status, "value") else str(student.status)
        if cur not in valid_from:
            results.append(BulkAdmissionStatusUpdateResult(student_id=sid, success=False, message=f"Cannot waitlist from {cur}"))
            continue
        student.status = AdmissionStatusEnum.WAITLISTED
        updated += 1
        results.append(BulkAdmissionStatusUpdateResult(student_id=sid, success=True, message="Moved to WAITLISTED"))

    if updated:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    return BulkAdmissionStatusUpdateResponse(
        total_requested=len(payload.student_ids),
        updated_count=updated,
        failed_count=len([r for r in results if not r.success]),
        results=results,
    )


# ── Bulk Cancel (Withdraw) ───────────────────────────
@admission_entry_router.post(
    "/admission-students/bulk-cancel",
    tags=["Admission - Admission Students"],
    name="Bulk Cancel Admission Students",
)
async def bulk_cancel_students(
    payload: BulkAdmissionStatusUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Bulk transition students → WITHDRAWN (cancel admission)."""
    if not payload.student_ids:
        raise HTTPException(status_code=400, detail="student_ids cannot be empty")

    query = select(AdmissionStudent).where(
        AdmissionStudent.id.in_(payload.student_ids),
        AdmissionStudent.deleted_at.is_(None),
    )
    result = await db.execute(query)
    student_map = {s.id: s for s in result.scalars().all()}

    valid_from = {
        AdmissionStatusEnum.APPLIED.value,
        AdmissionStatusEnum.PROVISIONALLY_ALLOTTED.value,
        AdmissionStatusEnum.WAITLISTED.value,
        "APPLIED", "PROVISIONALLY_ALLOTTED", "WAITLISTED",
    }

    updated, results = 0, []
    for sid in payload.student_ids:
        student = student_map.get(sid)
        if not student:
            results.append(BulkAdmissionStatusUpdateResult(student_id=sid, success=False, message="Student not found"))
            continue
        cur = student.status.value if hasattr(student.status, "value") else str(student.status)
        if cur not in valid_from:
            results.append(BulkAdmissionStatusUpdateResult(student_id=sid, success=False, message=f"Cannot cancel from {cur}"))
            continue
        student.status = AdmissionStatusEnum.WITHDRAWN
        updated += 1
        results.append(BulkAdmissionStatusUpdateResult(student_id=sid, success=True, message="Cancelled (WITHDRAWN)"))

    if updated:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    return BulkAdmissionStatusUpdateResponse(
        total_requested=len(payload.student_ids),
        updated_count=updated,
        failed_count=len([r for r in results if not r.success]),
        results=results,
    )


# ── Reinstate Waitlisted → Provisionally Allotted ────
@admission_entry_router.post(
    "/admission-students/{student_id}/reinstate",
    tags=["Admission - Admission Students"],
    name="Reinstate Waitlisted Student",
)
async def reinstate_student(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """Move a WAITLISTED student back to PROVISIONALLY_ALLOTTED with fee lock."""
    from apps.billing.services import billing_service

    student = (await db.execute(
        select(AdmissionStudent).where(AdmissionStudent.id == student_id, AdmissionStudent.deleted_at.is_(None))
    )).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    cur = student.status.value if hasattr(student.status, "value") else str(student.status)
    if cur != AdmissionStatusEnum.WAITLISTED.value:
        raise HTTPException(status_code=400, detail=f"Cannot reinstate from {cur}; must be WAITLISTED")

    student.status = AdmissionStatusEnum.PROVISIONALLY_ALLOTTED
    await db.commit()
    return {"message": "Student reinstated to PROVISIONALLY_ALLOTTED", "student_id": str(student_id)}


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
    
    # Source breakdown (from AdmissionGateEntry reference_type)
    from common.models.admission.admission_entry import AdmissionGateEntry
    stmt_source = select(
        AdmissionGateEntry.reference_type,
        func.count(AdmissionStudent.id)
    ).join(AdmissionStudent, AdmissionStudent.gate_entry_id == AdmissionGateEntry.id).where(
        AdmissionGateEntry.reference_type.isnot(None)
    ).group_by(AdmissionGateEntry.reference_type)
    
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
    from common.models.admission.admission_entry import AdmissionGateEntry, AdmissionStudentPersonalDetails
    query_students = select(AdmissionStudent).outerjoin(AdmissionGateEntry).outerjoin(AdmissionStudentPersonalDetails).options(
        selectinload(AdmissionStudent.personal_details),
        selectinload(AdmissionStudent.gate_entry)
    )
    if source:
        # source doesn't exist, ignore or filter on reference_type
        pass
    if reference_type:
        query_students = query_students.where(AdmissionGateEntry.reference_type == reference_type)
    
    res_students = await db.execute(query_students)
    students = res_students.scalars().all()
    
    # Normalize data
    all_enquiries = [{
        "id": str(s.id),
        "enquiry_number": s.enquiry_number,
        "name": s.personal_details.name if getattr(s, "personal_details", None) else None,
        "mobile": s.personal_details.student_mobile if getattr(s, "personal_details", None) else None,
        "status": s.status,
        "source": getattr(s, "source", None).value if getattr(s, "source", None) else None,
        "reference_type": getattr(s.gate_entry, "reference_type", None) if getattr(s, "gate_entry", None) else None,
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
    from common.models.admission.admission_entry import AdmissionStudentProgramDetails

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
        base_filters.append(AdmissionStudentProgramDetails.institution_id == institution_id)

    # Consultancy summary
    consultancy_stmt = (
        select(
            Consultancy.id,
            Consultancy.name,
            func.count(AdmissionStudent.id).label("admission_count"),
        )
        .join(ConsultancyReference, ConsultancyReference.consultancy_id == Consultancy.id)
        .join(AdmissionStudent, AdmissionStudent.id == ConsultancyReference.student_id)
        .outerjoin(AdmissionStudentProgramDetails, AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id)
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
        .outerjoin(AdmissionStudentProgramDetails, AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id)
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
    stmt = stmt.options(selectinload(AdmissionStudent.personal_details), selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.department), selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.course), selectinload(AdmissionStudent.personal_details), selectinload(AdmissionStudent.gate_entry)).order_by(desc(AdmissionStudent.created_at)).offset(offset).limit(size)
    result = await db.execute(stmt)
    students = result.scalars().all()

    items = [
        {
            "id": str(s.id),
            "enquiry_number": s.enquiry_number,
            "name": s.personal_details.name if s.personal_details else None,
            "mobile": s.personal_details.student_mobile if s.personal_details else None,
            "parent_name": s.personal_details.father_name if s.personal_details else None,
            "native_place": getattr(s.gate_entry, "native_place", None) if s.gate_entry else None,
            "status": s.status.value if hasattr(s.status, "value") else s.status,
            "reference_type": getattr(s.gate_entry, "reference_type", None) if s.gate_entry else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "institution_id": str(s.program_details.institution_id) if s.program_details and s.program_details.institution_id else None,
            "department_id": str(s.program_details.department_id) if s.program_details and s.program_details.department_id else None,
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
    query=QueryBuilder(AdmissionStudent),
    params: Params = Depends()
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

    return await paginate(db, query, params)


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
            "name": s.personal_details.name if s.personal_details else None,
            "enquiry_number": s.enquiry_number,
            "application_number": s.application_number,
            "status": s.status,
            "student_mobile": s.personal_details.student_mobile if s.personal_details else None,
            "department_id": str(s.program_details.department_id) if s.program_details and s.program_details.department_id else None,
            "course_id": str(s.program_details.course_id) if s.program_details and s.program_details.course_id else None,
            "institution_id": str(s.program_details.institution_id) if s.program_details and s.program_details.institution_id else None,
        }
        for s in students
    ]


# Import schemas
from common.schemas.admission.admission_entry import BookAdmissionResponse, UpdateCourseRequest
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
    stmt = select(AdmissionStudent).options(selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.department), selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.course), selectinload(AdmissionStudent.personal_details)).where(AdmissionStudent.id == student_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    def _build_response(s):
        return {
            "id": s.id,
            "application_number": s.application_number,
            "status": s.status,
            "enquiry_number": s.enquiry_number,
            "name": s.personal_details.name if s.personal_details else ""
        }

    if getattr(student, "application_number", None):
        return _build_response(student)

    try:
        if not student.program_details or not student.program_details.institution_id:
            raise ValueError("Student missing program details or institution_id")

        # 2. Generate Application Number
        app_no = await billing_service.generate_application_number(db, student.program_details.institution_id)
        student.application_number = app_no

        # 3. Mark Status as BOOKED
        if student.status in [AdmissionStatusEnum.ENQUIRY.value, AdmissionStatusEnum.ENQUIRED.value]:
            student.status = AdmissionStatusEnum.BOOKED.value
            
        # 4. Handle Fee Logic
        demand_item = await billing_service.assign_application_fee(db, student.id)
        if demand_item:
            await db.flush()
            await billing_service.create_invoice_from_demands(db, [demand_item])
        
        await db.commit()
        await db.refresh(student)
        return _build_response(student)
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

        # Re-fetch updated row and serialize only columns to avoid recursion.
        refreshed_query = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
        refreshed_result = await db.execute(refreshed_query)
        refreshed_student = refreshed_result.scalar_one_or_none()

        if not refreshed_student:
            raise HTTPException(status_code=404, detail="Student not found after update")

        return _serialize_admission_student(refreshed_student)
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
    stmt = select(AdmissionStudent).options(selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.department), selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.course), selectinload(AdmissionStudent.personal_details)).where(AdmissionStudent.id == student_id)
    res = await db.execute(stmt)
    student = res.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    roll_number = payload.roll_number.strip()
    if not roll_number:
        raise HTTPException(status_code=400, detail="roll_number cannot be empty")

    inst_id = student.program_details.institution_id if student.program_details else None

    duplicate_stmt = (
        select(AdmissionStudent.id)
        .join(AdmissionStudentProgramDetails, AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id)
        .where(
            AdmissionStudent.id != student_id,
            AdmissionStudentProgramDetails.institution_id == inst_id,
            AdmissionStudent.roll_number == roll_number,
        )
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
    return _serialize_admission_student(student)


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
    return _serialize_admission_student(student)


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
    stmt = select(AdmissionStudent).options(selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.department), selectinload(AdmissionStudent.program_details).selectinload(AdmissionStudentProgramDetails.course), selectinload(AdmissionStudent.personal_details)).where(AdmissionStudent.id == student_id)
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

    inst_id = student.program_details.institution_id if student.program_details else None

    duplicate_stmt = (
        select(AdmissionStudent.id)
        .join(AdmissionStudentProgramDetails, AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id)
        .where(
            AdmissionStudent.id != student_id,
            AdmissionStudentProgramDetails.institution_id == inst_id,
            AdmissionStudent.roll_number == roll_number,
        )
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
    return _serialize_admission_student(student)


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
        return _serialize_admission_student(student)
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
        return _serialize_admission_student(student)
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


# ── Student Deposit Management ─────────────────────────
@admission_entry_router.post(
    "/admission-students/{student_id}/record-deposit",
    tags=["Admission - Student Deposits"],
    name="Record Student Deposit",
    summary="Record advance/deposit payment for student before admission"
)
async def record_deposit(
    student_id: UUID,
    payload: dict,
    db: AsyncSession = Depends(get_db_session),
    user_id: UUID = Depends(get_user_id),
):
    """
    Record a deposit/advance payment from a student.
    Creates or updates StudentDeposit record.
    """
    try:
        from common.models.billing.student_deposit import StudentDeposit
        from datetime import datetime
        
        # Get the student
        student_stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
        student_res = await db.execute(student_stmt)
        student = student_res.scalar_one_or_none()

        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Check if deposit record exists
        deposit_stmt = select(StudentDeposit).where(StudentDeposit.student_id == student_id)
        deposit_res = await db.execute(deposit_stmt)
        deposit = deposit_res.scalar_one_or_none()

        # Extract payload
        amount = payload.get("amount")
        payment_method = payload.get("payment_method")
        transaction_id = payload.get("transaction_id")
        notes = payload.get("notes")

        if not amount or amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than 0")

        if not payment_method:
            raise HTTPException(status_code=400, detail="Payment method is required")

        # Create deposit record if doesn't exist
        if not deposit:
            deposit = StudentDeposit(
                student_id=student_id,
                institution_id=student.institution_id,
                application_number=student.application_number,
                total_deposited=0,
                used_amount=0,
                refunds_issued=0,
                created_by=user_id,
                last_modified_by=user_id,
            )
            db.add(deposit)

        # Update deposit amounts and history
        from decimal import Decimal
        amount_decimal = Decimal(str(amount))
        deposit.total_deposited += amount_decimal
        deposit.last_modified_by = user_id

        # Add to receipt history
        receipt_entry = {
            "date": datetime.utcnow().isoformat(),
            "amount": float(amount),
            "payment_method": payment_method,
            "receipt_number": transaction_id,
            "notes": notes,
        }
        
        # Get existing receipts or create new list
        receipts = list(deposit.deposit_receipts) if deposit.deposit_receipts else []
        receipts.append(receipt_entry)
        # Explicitly assign to trigger SQLAlchemy change detection for JSON field
        deposit.deposit_receipts = receipts

        await db.commit()
        await db.refresh(deposit)

        return {
            "id": str(deposit.id),
            "student_id": str(deposit.student_id),
            "application_number": deposit.application_number,
            "total_deposited": float(deposit.total_deposited),
            "used_amount": float(deposit.used_amount),
            "available_balance": float(deposit.available_balance),
            "status": deposit.status,
            "created_at": deposit.created_at.isoformat(),
        }
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error recording deposit: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@admission_entry_router.get(
    "/admission-students/{student_id}/deposit",
    tags=["Admission - Student Deposits"],
    name="Get Student Deposit",
    summary="View student deposit details and transaction history"
)
async def get_student_deposit(
    student_id: UUID,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Retrieve complete deposit details for a student including balance and history.
    """
    try:
        from common.models.billing.student_deposit import StudentDeposit
        
        # Check if student exists
        student_stmt = select(AdmissionStudent).where(AdmissionStudent.id == student_id)
        student_res = await db.execute(student_stmt)
        student = student_res.scalar_one_or_none()

        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

        # Get deposit if exists
        deposit_stmt = select(StudentDeposit).where(StudentDeposit.student_id == student_id)
        deposit_res = await db.execute(deposit_stmt)
        deposit = deposit_res.scalar_one_or_none()

        if not deposit:
            return {
                "student_id": str(student_id),
                "application_number": student.application_number,
                "total_deposited": 0,
                "used_amount": 0,
                "available_balance": 0,
                "status": "ACTIVE",
                "message": "No deposits recorded for this student",
            }

        return {
            "id": str(deposit.id),
            "student_id": str(deposit.student_id),
            "application_number": deposit.application_number,
            "total_deposited": float(deposit.total_deposited),
            "used_amount": float(deposit.used_amount),
            "refunds_issued": float(deposit.refunds_issued),
            "available_balance": float(deposit.available_balance),
            "status": deposit.status,
            "notes": deposit.notes,
            "deposit_receipts": deposit.deposit_receipts or [],
            "adjustment_history": deposit.adjustment_history or [],
            "created_at": deposit.created_at.isoformat(),
            "updated_at": deposit.updated_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting deposit: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@admission_entry_router.get(
    "/deposits/by-application",
    tags=["Admission - Student Deposits"],
    name="Get Deposit by Application Number",
    summary="Quick lookup of deposit by application number"
)
async def get_deposit_by_application(
    application_number: str,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Retrieve deposit details by application number for quick lookup by Finance staff.
    """
    try:
        from common.models.billing.student_deposit import StudentDeposit
        
        # Get deposit by application number
        deposit_stmt = select(StudentDeposit).where(
            StudentDeposit.application_number == application_number
        )
        deposit_res = await db.execute(deposit_stmt)
        deposit = deposit_res.scalar_one_or_none()

        if not deposit:
            raise HTTPException(
                status_code=404, 
                detail=f"No deposit found for application number {application_number}"
            )

        return {
            "id": str(deposit.id),
            "student_id": str(deposit.student_id),
            "application_number": deposit.application_number,
            "total_deposited": float(deposit.total_deposited),
            "used_amount": float(deposit.used_amount),
            "refunds_issued": float(deposit.refunds_issued),
            "available_balance": float(deposit.available_balance),
            "status": deposit.status,
            "notes": deposit.notes,
            "deposit_receipts": deposit.deposit_receipts or [],
            "adjustment_history": deposit.adjustment_history or [],
            "created_at": deposit.created_at.isoformat(),
            "updated_at": deposit.updated_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting deposit by application: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


add_pagination(admission_router)
add_pagination(lead_followup_router)
add_pagination(admission_entry_router)
