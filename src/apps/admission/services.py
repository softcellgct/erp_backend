"""
Admission Services
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.admission.admission_entry import AdmissionGateEntry, AdmissionStudent


async def generate_enquiry_number(db: AsyncSession, institution_id: str = None) -> str:
    """
    Generate a unique enquiry number in the format: ENQ-{TIMESTAMP}-{SEQUENCE}
    Example: ENQ-20260122-0001

    Sequence is computed across both admission students and gate entries,
    so enquiry numbers stay globally unique after table split.
    """
    date_str = datetime.utcnow().strftime("%Y%m%d")

    student_result = await db.execute(
        select(func.count(AdmissionStudent.id)).where(
            AdmissionStudent.enquiry_number.ilike(f"ENQ-{date_str}%")
        )
    )
    student_count = student_result.scalar() or 0

    gate_result = await db.execute(
        select(func.count(AdmissionGateEntry.id)).where(
            AdmissionGateEntry.enquiry_number.ilike(f"ENQ-{date_str}%")
        )
    )
    gate_count = gate_result.scalar() or 0

    sequence = str(student_count + gate_count + 1).zfill(4)
    enquiry_number = f"ENQ-{date_str}-{sequence}"

    return enquiry_number
