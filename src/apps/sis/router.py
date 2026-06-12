from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.sis import classes as cls_svc
from apps.sis import roll_number as rn
from apps.sis.schemas import (
    AssignClassRequest,
    ClassCreate,
    ClassUpdate,
    EnrollStudentRequest,
    LockFeeRequest,
    PerfectEntryUpdate,
    RollCommitRequest,
    RollPreviewRequest,
    RollTemplateUpsert,
    SISProfileResponse,
    SISProfileUpdate,
    SISStudentListItem,
    UnassignRequest,
)
from apps.sis.service import (
    compute_profile_completion,
    enroll_student,
    finalize_perfect_entry,
    get_or_create_sis_profile,
    unlock_perfect_entry,
)
from common.models.admission.admission_entry import (
    AdmissionStatusEnum,
    AdmissionStudent,
)
from common.models.sis.sis_student import SISStudentProfile
from components.db.db import get_db_session
from components.generator.utils.get_user_from_request import get_user_id
from components.middleware import is_superadmin

router = APIRouter(prefix="/sis", tags=["SIS"])


def _serialize_student(student: AdmissionStudent, sis_profile: SISStudentProfile | None) -> dict:
    pd = student.personal_details
    prog = student.program_details

    sis_profile_data = None
    if sis_profile:
        sis_profile_data = {
            "id": str(sis_profile.id),
            "admission_student_id": str(sis_profile.admission_student_id),
            "blood_group": sis_profile.blood_group.value if sis_profile.blood_group else None,
            "nationality": sis_profile.nationality,
            "mother_tongue": sis_profile.mother_tongue,
            "email": sis_profile.email,
            "whatsapp_number": sis_profile.whatsapp_number,
            "differently_abled": sis_profile.differently_abled,
            "differently_abled_type": sis_profile.differently_abled_type,
            "ex_serviceman_child": sis_profile.ex_serviceman_child,
            "first_generation_graduate": sis_profile.first_generation_graduate,
            "mother_name": sis_profile.mother_name,
            "mother_occupation": sis_profile.mother_occupation,
            "father_occupation": sis_profile.father_occupation,
            "guardian_name": sis_profile.guardian_name,
            "guardian_relation": sis_profile.guardian_relation,
            "guardian_mobile": sis_profile.guardian_mobile,
            "register_number": sis_profile.register_number,
            "hostel_status": sis_profile.hostel_status.value if sis_profile.hostel_status else None,
            "photo_url": sis_profile.photo_url,
            "profile_completed_at": sis_profile.profile_completed_at.isoformat() if sis_profile.profile_completed_at else None,
        }

    return {
        "id": str(student.id),
        "enquiry_number": student.enquiry_number,
        "application_number": student.application_number,
        "name": student.name,
        "roll_number": student.roll_number,
        "section": student.section,
        "current_semester": student.current_semester,
        "is_sem1_active": student.is_sem1_active,
        "enrolled_at": student.enrolled_at.isoformat() if student.enrolled_at else None,
        "status": student.status.value,
        "fee_structure_id": str(student.fee_structure_id) if student.fee_structure_id else None,
        "is_fee_structure_locked": student.is_fee_structure_locked,
        "fee_structure_name": student.fee_structure.name if student.fee_structure else None,
        "fee_structure_locked_at": student.fee_structure_locked_at.isoformat() if student.fee_structure_locked_at else None,
        "documents_submitted": student.documents_submitted,
        # Perfect Entry finalize / lock state
        "perfect_entry_finalized": student.perfect_entry_finalized,
        "perfect_entry_finalized_at": student.perfect_entry_finalized_at.isoformat() if student.perfect_entry_finalized_at else None,
        # Class / section assignment
        "class_id": str(student.class_id) if student.class_id else None,
        "class_code": student.assigned_class.code if student.assigned_class else None,
        "class_title": student.assigned_class.title if student.assigned_class else None,
        "class_section_name": student.assigned_class.section_name if student.assigned_class else None,
        # Personal details
        "student_mobile": pd.student_mobile if pd else None,
        "parent_mobile": pd.parent_mobile if pd else None,
        "gender": pd.gender.value if (pd and pd.gender) else None,
        "date_of_birth": pd.date_of_birth.isoformat() if (pd and pd.date_of_birth) else None,
        "father_name": pd.father_name if pd else None,
        "aadhaar_number": pd.aadhaar_number if pd else None,
        "religion": pd.religion if pd else None,
        "community": pd.community if pd else None,
        "caste": pd.caste if pd else None,
        "parent_income": str(pd.parent_income) if (pd and pd.parent_income) else None,
        "door_no": pd.door_no if pd else None,
        "street_name": pd.street_name if pd else None,
        "village_name": pd.village_name if pd else None,
        "taluk": pd.taluk if pd else None,
        "district": pd.district if pd else None,
        "state": pd.state if pd else None,
        "pincode": pd.pincode if pd else None,
        "parent_address": pd.parent_address if pd else None,
        "permanent_address": pd.permanent_address if pd else None,
        # Program details
        "department_id": str(prog.department_id) if (prog and prog.department_id) else None,
        "department_name": prog.department.name if (prog and prog.department) else None,
        "course_id": str(prog.course_id) if (prog and prog.course_id) else None,
        "course_title": prog.course.title if (prog and prog.course) else None,
        "academic_year_id": str(prog.academic_year_id) if (prog and prog.academic_year_id) else None,
        "institution_id": str(prog.institution_id) if (prog and prog.institution_id) else None,
        "category": prog.category.value if (prog and prog.category) else None,
        "is_lateral_entry": prog.is_lateral_entry if prog else False,
        "boarding_place": prog.boarding_place if prog else None,
        "scholarships": prog.scholarships if prog else None,
        # Previous academics
        "previous_academic_details": {
            "sslc": student.previous_academic_details.sslc if student.previous_academic_details else None,
            "hsc": student.previous_academic_details.hsc if student.previous_academic_details else None,
            "diploma": student.previous_academic_details.diploma if student.previous_academic_details else None,
            "degree": student.previous_academic_details.degree if student.previous_academic_details else None,
        } if student.previous_academic_details else None,
        # Form verification
        "form_verification_status": student.form_verification.status.value if (student.form_verification and student.form_verification.status) else None,
        # SIS profile
        "sis_profile": sis_profile_data,
        "profile_completion": compute_profile_completion(student, sis_profile),
    }


@router.post("/students/{student_id}/enroll")
async def enroll_student_to_sis(
    student_id: UUID,
    payload: EnrollStudentRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Enroll a PROVISIONALLY_ALLOTTED student into SIS."""
    try:
        user_id = await get_user_id(request)
        student = await enroll_student(
            session=session,
            student_id=str(student_id),
            roll_number=payload.roll_number,
            section=payload.section,
            enrolled_by=str(user_id),
        )
        sis_result = await session.execute(
            select(SISStudentProfile).where(
                SISStudentProfile.admission_student_id == student.id
            )
        )
        sis_profile = sis_result.scalar_one_or_none()
        return _serialize_student(student, sis_profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/students")
async def list_sis_students(
    page: int = 1,
    size: int = 20,
    search: str = "",
    department_id: str = "",
    course_id: str = "",
    academic_year_id: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    """List all enrolled SIS students with pagination."""
    from sqlalchemy import func, or_, cast, String
    from common.models.admission.admission_entry import AdmissionStudentPersonalDetails, AdmissionStudentProgramDetails
    from common.models.master.institution import Department, Course
    from common.models.master.annual_task import AcademicYear

    stmt = (
        select(AdmissionStudent)
        .where(
            AdmissionStudent.deleted_at.is_(None),
            AdmissionStudent.status == AdmissionStatusEnum.ENROLLED,
        )
        .order_by(AdmissionStudent.enrolled_at.desc().nullslast())
    )

    if search:
        pattern = f"%{search}%"
        stmt = stmt.join(
            AdmissionStudentPersonalDetails,
            AdmissionStudentPersonalDetails.admission_student_id == AdmissionStudent.id,
            isouter=True,
        ).where(
            or_(
                AdmissionStudent.name.ilike(pattern),
                AdmissionStudent.roll_number.ilike(pattern),
                AdmissionStudent.application_number.ilike(pattern),
                AdmissionStudentPersonalDetails.student_mobile.ilike(pattern),
                AdmissionStudentPersonalDetails.aadhaar_number.ilike(pattern),
            )
        )

    if department_id:
        stmt = stmt.join(
            AdmissionStudentProgramDetails,
            AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id,
            isouter=True,
        ).where(
            cast(AdmissionStudentProgramDetails.department_id, String) == department_id
        )

    if course_id:
        if not department_id:
            stmt = stmt.join(
                AdmissionStudentProgramDetails,
                AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id,
                isouter=True,
            )
        stmt = stmt.where(
            cast(AdmissionStudentProgramDetails.course_id, String) == course_id
        )

    # Total count
    count_result = await session.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)
    result = await session.execute(stmt)
    students = result.scalars().all()

    # Bulk-load SIS profiles
    student_ids = [s.id for s in students]
    sis_result = await session.execute(
        select(SISStudentProfile).where(
            SISStudentProfile.admission_student_id.in_(student_ids)
        )
    )
    sis_map = {str(p.admission_student_id): p for p in sis_result.scalars().all()}

    items = [_serialize_student(s, sis_map.get(str(s.id))) for s in students]

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, -(-total // size)),
    }


@router.get("/students/{student_id}")
async def get_sis_student(
    student_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    """Get full SIS student profile."""
    result = await session.execute(
        select(AdmissionStudent).where(
            AdmissionStudent.id == student_id,
            AdmissionStudent.deleted_at.is_(None),
        )
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    sis_result = await session.execute(
        select(SISStudentProfile).where(
            SISStudentProfile.admission_student_id == student_id
        )
    )
    sis_profile = sis_result.scalar_one_or_none()

    return await _resolve_person_meta(session, _serialize_student(student, sis_profile))


@router.put("/students/{student_id}/profile")
async def update_sis_profile(
    student_id: UUID,
    payload: SISProfileUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Create or update SIS-specific profile fields."""
    student = await session.get(AdmissionStudent, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    profile = await get_or_create_sis_profile(session, str(student_id))

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await session.commit()
    await session.refresh(profile)

    return _serialize_student(student, profile)


@router.post("/students/{student_id}/profile/complete")
async def mark_profile_complete(
    student_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Mark the SIS profile as complete."""
    student = await session.get(AdmissionStudent, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    profile = await get_or_create_sis_profile(session, str(student_id))
    completion = compute_profile_completion(student, profile)
    if completion < 80:
        raise HTTPException(
            status_code=400,
            detail=f"Profile is only {completion}% complete. Fill required fields before marking as complete.",
        )

    user_id = await get_user_id(request)
    profile.profile_completed_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    profile.profile_completed_by = user_id
    await session.commit()

    return {"profile_completion": completion, "profile_completed_at": profile.profile_completed_at.isoformat()}


# ── Perfect Entry endpoints ────────────────────────────────────────────────────

def _serialize_perfect_entry_list_item(student: AdmissionStudent, sis_profile: SISStudentProfile | None) -> dict:
    """Lightweight serializer for the Perfect Entry list page — only list-needed fields."""
    pd = student.personal_details
    prog = student.program_details

    if sis_profile and sis_profile.profile_completed_at:
        pe_status = "completed"
    elif sis_profile:
        pe_status = "in_progress"
    else:
        pe_status = "pending"

    return {
        "id": str(student.id),
        "application_number": student.application_number,
        "enquiry_number": student.enquiry_number,
        "name": student.name,
        "status": student.status.value,
        "gender": pd.gender.value if (pd and pd.gender) else None,
        "student_mobile": pd.student_mobile if pd else None,
        "department_name": prog.department.name if (prog and prog.department) else None,
        "course_title": prog.course.title if (prog and prog.course) else None,
        "institution_name": prog.institution.name if (prog and prog.institution) else None,
        "institution_id": str(prog.institution_id) if (prog and prog.institution_id) else None,
        "department_id": str(prog.department_id) if (prog and prog.department_id) else None,
        "quota_type": prog.quota_type if prog else None,
        "category": prog.category.value if (prog and prog.category) else None,
        "perfect_entry_status": pe_status,
        "perfect_entry_finalized": student.perfect_entry_finalized,
        "is_fee_structure_locked": student.is_fee_structure_locked,
    }


def _serialize_perfect_entry_student(student: AdmissionStudent, sis_profile: SISStudentProfile | None) -> dict:
    """Full serializer for Perfect Entry — includes all fields needed across all 9 tabs."""
    base = _serialize_student(student, sis_profile)
    pd = student.personal_details
    prog = student.program_details

    # Extend with fields not in base serializer
    base.update({
        # Basic Info extras
        "name": student.name,
        "date_of_birth": pd.date_of_birth.isoformat() if (pd and pd.date_of_birth) else None,
        "gender": pd.gender.value if (pd and pd.gender) else None,
        "aadhaar_number": pd.aadhaar_number if pd else None,  # shown masked in UI
        # Statutory Info
        "religion": pd.religion if pd else None,
        "community": pd.community if pd else None,
        "caste": pd.caste if pd else None,
        "category": prog.category.value if (prog and prog.category) else None,
        "quota_type": prog.quota_type if prog else None,
        "special_quota": prog.special_quota if prog else None,
        "scholarships": prog.scholarships if prog else None,
        "admission_quota_name": prog.admission_quota.name if (prog and prog.admission_quota) else None,
        "admission_quota_id": str(prog.admission_quota_id) if (prog and prog.admission_quota_id) else None,
        # Communication
        "student_mobile": pd.student_mobile if pd else None,
        "parent_mobile": pd.parent_mobile if pd else None,
        "door_no": pd.door_no if pd else None,
        "street_name": pd.street_name if pd else None,
        "village_name": pd.village_name if pd else None,
        "taluk": pd.taluk if pd else None,
        "district": pd.district if pd else None,
        "state": pd.state if pd else None,
        "pincode": pd.pincode if pd else None,
        "parent_address": pd.parent_address if pd else None,
        "permanent_address": pd.permanent_address if pd else None,
        # Parental Info
        "father_name": pd.father_name if pd else None,
        "parent_income": str(pd.parent_income) if (pd and pd.parent_income) else None,
        # Boarding / Counselling (program)
        "boarding_place": prog.boarding_place if prog else None,
        # Academic context (for Tab 3 display)
        "institution_name": prog.institution.name if (prog and prog.institution) else None,
        "academic_year_name": prog.academic_year.year_name if (prog and prog.academic_year) else None,
        # SIS profile extras
        "email": sis_profile.email if sis_profile else None,
        "whatsapp_number": sis_profile.whatsapp_number if sis_profile else None,
        "blood_group": sis_profile.blood_group.value if (sis_profile and sis_profile.blood_group) else None,
        "nationality": sis_profile.nationality if sis_profile else "Indian",
        "mother_tongue": sis_profile.mother_tongue if sis_profile else None,
        "hostel_status": sis_profile.hostel_status.value if (sis_profile and sis_profile.hostel_status) else None,
        "register_number": sis_profile.register_number if sis_profile else None,
        "differently_abled": sis_profile.differently_abled if sis_profile else False,
        "differently_abled_type": sis_profile.differently_abled_type if sis_profile else None,
        "ex_serviceman_child": sis_profile.ex_serviceman_child if sis_profile else False,
        "first_generation_graduate": sis_profile.first_generation_graduate if sis_profile else False,
        "mother_name": sis_profile.mother_name if sis_profile else None,
        "mother_occupation": sis_profile.mother_occupation if sis_profile else None,
        "father_occupation": sis_profile.father_occupation if sis_profile else None,
        "guardian_name": sis_profile.guardian_name if sis_profile else None,
        "guardian_relation": sis_profile.guardian_relation if sis_profile else None,
        "guardian_mobile": sis_profile.guardian_mobile if sis_profile else None,
        # Bank details
        "bank_name": sis_profile.bank_name if sis_profile else None,
        "bank_account_number": sis_profile.bank_account_number if sis_profile else None,
        "bank_ifsc_code": sis_profile.bank_ifsc_code if sis_profile else None,
        "bank_branch_name": sis_profile.bank_branch_name if sis_profile else None,
        "bank_account_holder_name": sis_profile.bank_account_holder_name if sis_profile else None,
        # TC details
        "tc_number": sis_profile.tc_number if sis_profile else None,
        "tc_date": sis_profile.tc_date.isoformat() if (sis_profile and sis_profile.tc_date) else None,
        "tc_from_school": sis_profile.tc_from_school if sis_profile else None,
        "tc_issued_by": sis_profile.tc_issued_by if sis_profile else None,
        # Emergency contact
        "emergency_contact_name": sis_profile.emergency_contact_name if sis_profile else None,
        "emergency_contact_relation": sis_profile.emergency_contact_relation if sis_profile else None,
        "emergency_contact_mobile": sis_profile.emergency_contact_mobile if sis_profile else None,
        # Counselling
        "counselling_date": sis_profile.counselling_date.isoformat() if (sis_profile and sis_profile.counselling_date) else None,
        "counselling_number": sis_profile.counselling_number if sis_profile else None,
        "allotment_order_number": sis_profile.allotment_order_number if sis_profile else None,
        "counselling_type": sis_profile.counselling_type if sis_profile else None,
        # Government / institutional IDs
        "emis_number": sis_profile.emis_number if sis_profile else None,
        "umis_number": sis_profile.umis_number if sis_profile else None,
        "abc_id": sis_profile.abc_id if sis_profile else None,
        # Quota / social extras
        "minority_status": sis_profile.minority_status if sis_profile else None,
        # Contact extras
        "alternate_mobile": sis_profile.alternate_mobile if sis_profile else None,
        # Extended communication address
        "comm_address_line2": sis_profile.comm_address_line2 if sis_profile else None,
        "comm_country": sis_profile.comm_country if sis_profile else "India",
        # Structured permanent address
        "perm_address_line1": sis_profile.perm_address_line1 if sis_profile else None,
        "perm_address_line2": sis_profile.perm_address_line2 if sis_profile else None,
        "perm_area_street": sis_profile.perm_area_street if sis_profile else None,
        "perm_city": sis_profile.perm_city if sis_profile else None,
        "perm_district": sis_profile.perm_district if sis_profile else None,
        "perm_state": sis_profile.perm_state if sis_profile else None,
        "perm_country": sis_profile.perm_country if sis_profile else "India",
        "perm_pincode": sis_profile.perm_pincode if sis_profile else None,
    })
    return base


def _serialize_student_360(student: AdmissionStudent, sis_profile: SISStudentProfile | None) -> dict:
    """Aggregate read for the Student 360 profile — everything about a student
    plus a derived status timeline."""
    base = _serialize_perfect_entry_student(student, sis_profile)
    status = student.status

    is_pa_or_enrolled = status in (
        AdmissionStatusEnum.PROVISIONALLY_ALLOTTED,
        AdmissionStatusEnum.ENROLLED,
    )
    timeline = [
        {"key": "created", "label": "Application Created",
         "date": student.created_at.isoformat() if student.created_at else None, "done": True},
        {"key": "provisionally_allotted", "label": "Provisionally Allotted",
         "date": None, "done": is_pa_or_enrolled},
        {"key": "fee_locked", "label": "Fee Structure Locked",
         "date": student.fee_structure_locked_at.isoformat() if student.fee_structure_locked_at else None,
         "done": student.is_fee_structure_locked},
        {"key": "finalized", "label": "Perfect Entry Finalized",
         "date": student.perfect_entry_finalized_at.isoformat() if student.perfect_entry_finalized_at else None,
         "done": student.perfect_entry_finalized},
        {"key": "enrolled", "label": "Enrolled (Roll Number Assigned)",
         "date": student.enrolled_at.isoformat() if student.enrolled_at else None,
         "done": status == AdmissionStatusEnum.ENROLLED},
        {"key": "class_assigned", "label": "Class Assigned",
         "date": None, "done": student.class_id is not None},
    ]
    base["status_timeline"] = timeline
    return base


@router.get("/students/{student_id}/360")
async def get_student_360(
    student_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    """Full aggregate profile for the Student 360 page."""
    result = await session.execute(
        select(AdmissionStudent).where(
            AdmissionStudent.id == student_id,
            AdmissionStudent.deleted_at.is_(None),
        )
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    sis_result = await session.execute(
        select(SISStudentProfile).where(
            SISStudentProfile.admission_student_id == student_id
        )
    )
    sis_profile = sis_result.scalar_one_or_none()
    return await _resolve_person_meta(session, _serialize_student_360(student, sis_profile))


@router.get("/perfect-entry/students")
async def list_perfect_entry_students(
    page: int = 1,
    size: int = 20,
    search: str = "",
    department_id: str = "",
    institution_id: str = "",
    academic_year_id: str = "",
    quota: str = "",
    finalized: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    """List PROVISIONALLY_ALLOTTED students for the Perfect Entry workflow.

    Supports server-side search (name, application no., mobile, aadhaar) and
    filtering by institution, department, academic year, quota type, and
    finalize state (``finalized`` = "true" | "false").
    """
    from sqlalchemy import func, or_, cast, String
    from common.models.admission.admission_entry import (
        AdmissionStudentPersonalDetails,
        AdmissionStudentProgramDetails,
    )

    stmt = (
        select(AdmissionStudent)
        .where(
            AdmissionStudent.deleted_at.is_(None),
            AdmissionStudent.status == AdmissionStatusEnum.PROVISIONALLY_ALLOTTED,
        )
        .order_by(AdmissionStudent.created_at.desc().nullslast())
    )

    if finalized == "true":
        stmt = stmt.where(AdmissionStudent.perfect_entry_finalized.is_(True))
    elif finalized == "false":
        stmt = stmt.where(AdmissionStudent.perfect_entry_finalized.is_(False))

    if search:
        pattern = f"%{search}%"
        stmt = stmt.join(
            AdmissionStudentPersonalDetails,
            AdmissionStudentPersonalDetails.admission_student_id == AdmissionStudent.id,
            isouter=True,
        ).where(
            or_(
                AdmissionStudent.name.ilike(pattern),
                AdmissionStudent.application_number.ilike(pattern),
                AdmissionStudent.enquiry_number.ilike(pattern),
                AdmissionStudentPersonalDetails.student_mobile.ilike(pattern),
                AdmissionStudentPersonalDetails.aadhaar_number.ilike(pattern),
            )
        )

    # All program-level filters share a single join to avoid duplicate rows
    if any([department_id, institution_id, academic_year_id, quota]):
        stmt = stmt.join(
            AdmissionStudentProgramDetails,
            AdmissionStudentProgramDetails.admission_student_id == AdmissionStudent.id,
            isouter=True,
        )

        if department_id:
            stmt = stmt.where(
                cast(AdmissionStudentProgramDetails.department_id, String) == department_id
            )
        if institution_id:
            stmt = stmt.where(
                cast(AdmissionStudentProgramDetails.institution_id, String) == institution_id
            )
        if academic_year_id:
            stmt = stmt.where(
                cast(AdmissionStudentProgramDetails.academic_year_id, String) == academic_year_id
            )
        if quota:
            stmt = stmt.where(
                AdmissionStudentProgramDetails.quota_type.ilike(f"%{quota}%")
            )

    # No .distinct() needed — both joined tables are one-to-one with admission_students
    # (unique constraint on admission_student_id in each detail table).
    # Using DISTINCT on JSON columns would raise an UndefinedFunctionError in PostgreSQL.

    count_result = await session.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar() or 0

    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)
    result = await session.execute(stmt)
    students = result.scalars().all()

    # Batch-load SIS profiles to avoid N+1
    student_ids = [s.id for s in students]
    sis_result = await session.execute(
        select(SISStudentProfile).where(
            SISStudentProfile.admission_student_id.in_(student_ids)
        )
    )
    sis_map = {str(p.admission_student_id): p for p in sis_result.scalars().all()}

    items = [_serialize_perfect_entry_list_item(s, sis_map.get(str(s.id))) for s in students]

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": max(1, -(-total // size)),
    }


@router.get("/perfect-entry/students/{student_id}")
async def get_perfect_entry_student(
    student_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    """Get full student data for the Perfect Entry form."""
    return await _load_perfect_entry(session, student_id)


@router.put("/perfect-entry/students/{student_id}")
async def update_perfect_entry(
    student_id: UUID,
    payload: PerfectEntryUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Comprehensive update for Perfect Entry — updates personal details, program details, and SIS profile.
    Aadhaar number is locked and cannot be updated via this endpoint."""
    student = await session.get(AdmissionStudent, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    if student.perfect_entry_finalized:
        raise HTTPException(
            status_code=423,
            detail="Perfect Entry is finalized and read-only. Ask a super-admin to unlock to make changes.",
        )

    data = payload.model_dump(exclude_unset=True)

    # ── Update AdmissionStudentPersonalDetails (all except aadhaar_number) ──
    personal_fields = {
        "name", "date_of_birth", "gender", "student_mobile", "parent_mobile",
        "father_name", "parent_income", "religion", "community", "caste",
        "door_no", "street_name", "village_name", "taluk", "district",
        "state", "pincode", "parent_address", "permanent_address",
    }
    personal_update = {k: v for k, v in data.items() if k in personal_fields}
    if personal_update:
        pd = student.personal_details
        if pd:
            for field, value in personal_update.items():
                setattr(pd, field, value)
            if "name" in personal_update:
                student.name = personal_update["name"]
        await session.flush()

    # ── Update AdmissionStudentProgramDetails ──
    program_fields = {
        "category", "quota_type", "special_quota", "scholarships", "boarding_place",
        # Program structure (FK columns) — editable in Perfect Entry
        "institution_id", "department_id", "course_id", "academic_year_id",
        "admission_quota_id", "is_lateral_entry",
    }
    program_update = {k: v for k, v in data.items() if k in program_fields}
    if program_update:
        prog = student.program_details

        # If department/course actually changes while a fee structure is locked,
        # auto-clear the lock — the locked structure no longer matches the program,
        # so the user must re-select & re-lock (and re-lock is required to finalize).
        if prog and student.is_fee_structure_locked:
            def _norm(v):
                return str(v) if v is not None else None

            dept_changed = (
                "department_id" in program_update
                and _norm(program_update["department_id"]) != _norm(prog.department_id)
            )
            course_changed = (
                "course_id" in program_update
                and _norm(program_update["course_id"]) != _norm(prog.course_id)
            )
            if dept_changed or course_changed:
                student.fee_structure_id = None
                student.is_fee_structure_locked = False
                student.fee_structure_locked_at = None
                student.fee_structure_locked_by = None

        if prog:
            for field, value in program_update.items():
                setattr(prog, field, value)
        # `is_lateral_entry` is denormalized onto the student too — keep in sync.
        if "is_lateral_entry" in program_update:
            student.is_lateral_entry = bool(program_update["is_lateral_entry"])
        await session.flush()

    # ── Create/update AdmissionStudentPreviousAcademicDetails (JSON per level) ──
    prev_acad_fields = {"sslc", "hsc", "diploma", "degree"}
    prev_acad_update = {k: v for k, v in data.items() if k in prev_acad_fields}
    if prev_acad_update:
        from common.models.admission.admission_entry import (
            AdmissionStudentPreviousAcademicDetails,
        )

        prev = student.previous_academic_details
        if not prev:
            prev = AdmissionStudentPreviousAcademicDetails(
                admission_student_id=student_id
            )
            session.add(prev)
        for field, value in prev_acad_update.items():
            # Assigning a fresh dict (not mutating in place) so SQLAlchemy detects
            # the change on the JSON column without a MutableDict wrapper.
            setattr(prev, field, value)
        await session.flush()

    # ── Create/update SISStudentProfile ──
    sis_fields = {
        "blood_group", "nationality", "mother_tongue", "email", "whatsapp_number",
        "differently_abled", "differently_abled_type", "ex_serviceman_child",
        "first_generation_graduate", "mother_name", "mother_occupation",
        "father_occupation", "guardian_name", "guardian_relation", "guardian_mobile",
        "register_number", "hostel_status",
        "bank_name", "bank_account_number", "bank_ifsc_code", "bank_branch_name", "bank_account_holder_name",
        "tc_number", "tc_date", "tc_from_school", "tc_issued_by",
        "emergency_contact_name", "emergency_contact_relation", "emergency_contact_mobile",
        "counselling_date", "counselling_number", "allotment_order_number", "counselling_type",
        # New fields
        "emis_number", "umis_number", "abc_id",
        "minority_status",
        "alternate_mobile",
        "comm_address_line2", "comm_country",
        "perm_address_line1", "perm_address_line2", "perm_area_street",
        "perm_city", "perm_district", "perm_state", "perm_country", "perm_pincode",
    }
    sis_update = {k: v for k, v in data.items() if k in sis_fields}
    if sis_update:
        profile = await get_or_create_sis_profile(session, str(student_id))
        for field, value in sis_update.items():
            setattr(profile, field, value)
        await session.flush()

    await session.commit()
    # Expire the identity map so program-detail FK relationships (department,
    # course, institution, academic_year, admission_quota) re-load fresh names —
    # the session uses expire_on_commit=False, so stale relationship objects
    # would otherwise survive the re-read in _load_perfect_entry.
    session.expire_all()

    return await _load_perfect_entry(session, student_id)


async def _resolve_person_meta(session: AsyncSession, data: dict) -> dict:
    """Replace religion/community/caste UUIDs with their human-readable names.

    These columns are free-text String(50) but often store FK references into the
    meta master tables; resolve them so the UI never shows raw UUIDs.
    """
    import uuid as _uuid
    from common.models.meta.models import Caste, Community, Religion

    def _is_uuid(val):
        try:
            _uuid.UUID(str(val))
            return True
        except (ValueError, TypeError):
            return False

    for field, model in (("religion", Religion), ("community", Community), ("caste", Caste)):
        val = data.get(field)
        if val and _is_uuid(val):
            name = await session.scalar(select(model.name).where(model.id == _uuid.UUID(str(val))))
            if name:
                data[field] = name
    return data


async def _load_perfect_entry(session: AsyncSession, student_id: UUID) -> dict:
    """Re-read and serialize a student for Perfect Entry responses."""
    result = await session.execute(
        select(AdmissionStudent).where(
            AdmissionStudent.id == student_id,
            AdmissionStudent.deleted_at.is_(None),
        )
    )
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    sis_result = await session.execute(
        select(SISStudentProfile).where(
            SISStudentProfile.admission_student_id == student_id
        )
    )
    sis_profile = sis_result.scalar_one_or_none()
    return await _resolve_person_meta(session, _serialize_perfect_entry_student(student, sis_profile))


@router.post("/perfect-entry/students/{student_id}/lock-fee")
async def lock_perfect_entry_fee(
    student_id: UUID,
    payload: LockFeeRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Assign & lock a fee structure for a Perfect Entry student.

    Reuses the billing service so SIS and admission share one fee-lock path.
    """
    student = await session.get(AdmissionStudent, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if student.perfect_entry_finalized:
        raise HTTPException(
            status_code=423,
            detail="Perfect Entry is finalized and read-only. Ask a super-admin to unlock.",
        )

    user_id = await get_user_id(request)
    from apps.billing.services import billing_service

    try:
        await billing_service.lock_student_fee_structure(
            session,
            student_id,
            payload.fee_structure_id,
            locked_by=user_id,
        )
        await session.commit()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

    return await _load_perfect_entry(session, student_id)


@router.post("/perfect-entry/students/{student_id}/finalize")
async def finalize_perfect_entry_student(
    student_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Finalize (lock read-only) a Perfect Entry record."""
    try:
        user_id = await get_user_id(request)
        await finalize_perfect_entry(session, str(student_id), str(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return await _load_perfect_entry(session, student_id)


@router.post("/perfect-entry/students/{student_id}/unlock")
@is_superadmin
async def unlock_perfect_entry_student(
    student_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Re-open a finalized Perfect Entry record (super-admin only)."""
    try:
        await unlock_perfect_entry(session, str(student_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return await _load_perfect_entry(session, student_id)


# ── Roll number generation ──────────────────────────────────────────────────

def _tokens_to_dicts(tokens) -> list:
    return [t.model_dump(exclude_none=True) for t in tokens]


@router.get("/roll-templates")
async def get_roll_template_endpoint(
    department_id: str = "",
    academic_year_id: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    """Return the saved roll-number template for a department + academic year (or null)."""
    tpl = await rn.get_roll_template(session, department_id, academic_year_id)
    if not tpl:
        return None
    return {
        "id": str(tpl.id),
        "institution_id": str(tpl.institution_id) if tpl.institution_id else None,
        "department_id": str(tpl.department_id) if tpl.department_id else None,
        "course_id": str(tpl.course_id) if tpl.course_id else None,
        "academic_year_id": str(tpl.academic_year_id) if tpl.academic_year_id else None,
        "name": tpl.name,
        "tokens": tpl.tokens,
        "separator": tpl.separator,
    }


@router.put("/roll-templates")
async def upsert_roll_template_endpoint(
    payload: RollTemplateUpsert,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Create or update the roll-number template for (department, academic year)."""
    user_id = await get_user_id(request)
    data = {
        "institution_id": payload.institution_id,
        "department_id": payload.department_id,
        "course_id": payload.course_id,
        "academic_year_id": payload.academic_year_id,
        "name": payload.name,
        "tokens": _tokens_to_dicts(payload.tokens),
        "separator": payload.separator or "",
    }
    tpl = await rn.upsert_roll_template(session, data, user_id)
    return {
        "id": str(tpl.id),
        "department_id": str(tpl.department_id) if tpl.department_id else None,
        "academic_year_id": str(tpl.academic_year_id) if tpl.academic_year_id else None,
    }


@router.post("/roll-numbers/preview")
async def preview_roll_numbers_endpoint(
    payload: RollPreviewRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Read-only preview of batch roll-number generation (with conflict flags)."""
    p = {
        "filters": payload.filters.model_dump(exclude_none=True),
        "tokens": _tokens_to_dicts(payload.tokens),
        "separator": payload.separator or "",
        "only_unassigned": payload.only_unassigned,
    }
    return await rn.preview_batch_roll_numbers(session, p)


@router.post("/roll-numbers/commit")
async def commit_roll_numbers_endpoint(
    payload: RollCommitRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Atomically assign roll numbers + enroll the matched finalized students."""
    user_id = await get_user_id(request)
    p = {
        "filters": payload.filters.model_dump(exclude_none=True),
        "tokens": _tokens_to_dicts(payload.tokens),
        "separator": payload.separator or "",
        "only_unassigned": payload.only_unassigned,
        "save_template": payload.save_template,
        "template_name": payload.template_name,
    }
    try:
        return await rn.commit_batch_roll_numbers(session, p, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ── Class management + assignment ────────────────────────────────────────────

@router.get("/classes")
async def list_classes_endpoint(
    institution_id: str = "",
    course_id: str = "",
    academic_year_id: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    """List classes (with live enrolled_count / capacity) matching the filters."""
    return await cls_svc.list_classes(
        session,
        {"institution_id": institution_id, "course_id": course_id, "academic_year_id": academic_year_id},
    )


@router.post("/classes")
async def create_class_endpoint(
    payload: ClassCreate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Create a class for a (course + academic year + section)."""
    user_id = await get_user_id(request)
    try:
        return await cls_svc.create_class(
            session,
            {
                "course_id": payload.course_id,
                "academic_year_id": payload.academic_year_id,
                "section_name": payload.section_name,
                "capacity": payload.capacity,
                "institution_id": payload.institution_id,
            },
            user_id,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.put("/classes/{class_id}")
async def update_class_endpoint(
    class_id: UUID,
    payload: ClassUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    user_id = await get_user_id(request)
    try:
        return await cls_svc.update_class(session, class_id, payload.model_dump(exclude_unset=True), user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/classes/{class_id}")
async def delete_class_endpoint(
    class_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    user_id = await get_user_id(request)
    try:
        return await cls_svc.delete_class(session, class_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/class-assignment/students")
async def list_assignable_students_endpoint(
    institution_id: str = "",
    department_id: str = "",
    course_id: str = "",
    academic_year_id: str = "",
    assigned: str = "",
    session: AsyncSession = Depends(get_db_session),
):
    """ENROLLED students eligible for class assignment (assigned = '' | 'true' | 'false')."""
    return await cls_svc.list_assignable_students(
        session,
        {
            "institution_id": institution_id,
            "department_id": department_id,
            "course_id": course_id,
            "academic_year_id": academic_year_id,
            "assigned": assigned,
        },
    )


@router.post("/class-assignment/assign")
async def assign_students_endpoint(
    payload: AssignClassRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Assign students to a class (capacity-checked)."""
    try:
        return await cls_svc.assign_students_to_class(
            session, payload.class_id, [str(s) for s in payload.student_ids]
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/class-assignment/unassign")
async def unassign_students_endpoint(
    payload: UnassignRequest,
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await cls_svc.unassign_students(session, [str(s) for s in payload.student_ids])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
