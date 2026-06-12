from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.admission.admission_entry import AdmissionStatusEnum, AdmissionStudent
from common.models.sis.sis_student import SISStudentProfile


PROFILE_REQUIRED_FIELDS = [
    "blood_group",
    "mother_name",
    "hostel_status",
    "email",
    "nationality",
]


def compute_profile_completion(student: AdmissionStudent, sis_profile: SISStudentProfile | None) -> int:
    """Return profile completion percentage (0-100)."""
    checks = [
        # From admission personal details
        bool(student.personal_details and student.personal_details.name),
        bool(student.personal_details and student.personal_details.date_of_birth),
        bool(student.personal_details and student.personal_details.gender),
        bool(student.personal_details and student.personal_details.student_mobile),
        bool(student.personal_details and student.personal_details.aadhaar_number),
        bool(student.personal_details and student.personal_details.door_no),
        bool(student.personal_details and student.personal_details.father_name),
        # From SIS profile
        bool(sis_profile and sis_profile.blood_group),
        bool(sis_profile and sis_profile.mother_name),
        bool(sis_profile and sis_profile.hostel_status),
        bool(sis_profile and sis_profile.email),
        bool(sis_profile and sis_profile.nationality),
    ]
    completed = sum(checks)
    return round((completed / len(checks)) * 100)


async def get_or_create_sis_profile(
    session: AsyncSession,
    student_id: str,
) -> SISStudentProfile:
    result = await session.execute(
        select(SISStudentProfile).where(
            SISStudentProfile.admission_student_id == student_id
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = SISStudentProfile(admission_student_id=student_id)
        session.add(profile)
        await session.flush()
    return profile


async def enroll_student(
    session: AsyncSession,
    student_id: str,
    roll_number: str | None,
    section: str | None,
    enrolled_by: str,
) -> AdmissionStudent:
    student = await session.get(AdmissionStudent, student_id)
    if not student:
        raise ValueError("Student not found")

    allowed = {AdmissionStatusEnum.PROVISIONALLY_ALLOTTED, AdmissionStatusEnum.APPLIED}
    if student.status not in allowed:
        raise ValueError(
            f"Only PROVISIONALLY_ALLOTTED or APPLIED students can be enrolled. "
            f"Current status: {student.status.value}"
        )

    if roll_number:
        student.roll_number = roll_number
    if section:
        student.section = section

    student.status = AdmissionStatusEnum.ENROLLED
    student.enrolled_at = datetime.now(timezone.utc)

    await get_or_create_sis_profile(session, student_id)
    await session.commit()
    await session.refresh(student)
    return student


# ── Perfect Entry finalize / unlock ─────────────────────────────────────────

FINALIZE_MIN_COMPLETION = 80


async def finalize_perfect_entry(
    session: AsyncSession,
    student_id: str,
    finalized_by: str,
) -> AdmissionStudent:
    """Lock a Perfect Entry record read-only.

    Gates: student must be PROVISIONALLY_ALLOTTED, profile completion must meet
    the threshold, and the fee structure must already be locked. Idempotent.
    """
    student = await session.get(AdmissionStudent, student_id)
    if not student:
        raise ValueError("Student not found")

    if student.perfect_entry_finalized:
        return student  # idempotent — already finalized

    if student.status != AdmissionStatusEnum.PROVISIONALLY_ALLOTTED:
        raise ValueError(
            f"Only PROVISIONALLY_ALLOTTED students can be finalized. "
            f"Current status: {student.status.value}"
        )

    profile = await get_or_create_sis_profile(session, student_id)
    completion = compute_profile_completion(student, profile)
    if completion < FINALIZE_MIN_COMPLETION:
        raise ValueError(
            f"Profile is only {completion}% complete. "
            f"Fill the required fields (≥{FINALIZE_MIN_COMPLETION}%) before finalizing."
        )

    if not student.is_fee_structure_locked:
        raise ValueError("Lock the fee structure before finalizing the Perfect Entry.")

    student.perfect_entry_finalized = True
    # `perfect_entry_finalized_at` is TIMESTAMP WITHOUT TIME ZONE — store naive UTC
    # to match the column type and the existing billing convention.
    student.perfect_entry_finalized_at = datetime.utcnow()
    student.perfect_entry_finalized_by = finalized_by

    await session.commit()
    await session.refresh(student)
    return student


async def unlock_perfect_entry(
    session: AsyncSession,
    student_id: str,
) -> AdmissionStudent:
    """Re-open a finalized Perfect Entry (super-admin only).

    Disallowed once the student is ENROLLED, since a roll number / class would
    already be assigned and unlocking could invalidate them.
    """
    student = await session.get(AdmissionStudent, student_id)
    if not student:
        raise ValueError("Student not found")

    if student.status == AdmissionStatusEnum.ENROLLED:
        raise ValueError(
            "Cannot unlock: student is already ENROLLED (roll number/class assigned). "
            "Unlocking after enrollment is not allowed."
        )

    student.perfect_entry_finalized = False
    student.perfect_entry_finalized_at = None
    student.perfect_entry_finalized_by = None

    await session.commit()
    await session.refresh(student)
    return student
