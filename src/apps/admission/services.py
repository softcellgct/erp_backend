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

    # Get the maximum enquiry number from both tables to find the highest sequence
    student_max_stmt = select(func.max(AdmissionStudent.enquiry_number)).where(
        AdmissionStudent.enquiry_number.ilike(like_pattern)
    )
    gate_max_stmt = select(func.max(AdmissionGateEntry.enquiry_number)).where(
        AdmissionGateEntry.enquiry_number.ilike(like_pattern)
    )

    student_max_res = await db.execute(student_max_stmt)
    gate_max_res = await db.execute(gate_max_stmt)

    s_max_val = student_max_res.scalar()
    g_max_val = gate_max_res.scalar()

    max_sequence = 0
    for val in [s_max_val, g_max_val]:
        if val and "-" in val:
            try:
                # Extract the last numeric part after the last hyphen
                parts = val.split("-")
                if parts:
                    seq_num = int(parts[-1])
                    if seq_num > max_sequence:
                        max_sequence = seq_num
            except (ValueError, IndexError):
                continue

    next_sequence = str(max_sequence + 1).zfill(4)
    return f"{prefix}{next_sequence}"
