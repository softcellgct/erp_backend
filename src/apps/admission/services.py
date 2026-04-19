"""
Admission Services
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.admission.admission_entry import AdmissionGateEntry, AdmissionStudent
from common.models.master.institution import Institution


async def generate_enquiry_number(db: AsyncSession, institution_id=None) -> str:
    """
    Generate a unique enquiry number.

    Format when institution is known: ENQ-{INST_CODE}-{YYYYMMDD}-{SEQUENCE}
    Fallback (no institution passed): ENQ-{YYYYMMDD}-{SEQUENCE}

    Sequence is computed across both admission students and gate entries
    that share the same prefix, so enquiry numbers stay unique.
    """
    date_str = datetime.utcnow().strftime("%Y%m%d")

    inst_code = None
    if institution_id:
        inst_uuid = institution_id if isinstance(institution_id, UUID) else UUID(str(institution_id))
        institution = await db.get(Institution, inst_uuid)
        if institution and institution.code:
            inst_code = institution.code.upper()

    prefix = f"ENQ-{inst_code}-{date_str}-" if inst_code else f"ENQ-{date_str}-"
    like_pattern = f"{prefix}%"

    student_result = await db.execute(
        select(func.count(AdmissionStudent.id)).where(
            AdmissionStudent.enquiry_number.ilike(like_pattern)
        )
    )
    student_count = student_result.scalar() or 0

    gate_result = await db.execute(
        select(func.count(AdmissionGateEntry.id)).where(
            AdmissionGateEntry.enquiry_number.ilike(like_pattern)
        )
    )
    gate_count = gate_result.scalar() or 0

    sequence = str(student_count + gate_count + 1).zfill(4)
    return f"{prefix}{sequence}"
