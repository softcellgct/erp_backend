"""
Admission Services
"""
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from common.models.admission.admission_entry import AdmissionStudent


async def generate_enquiry_number(db: AsyncSession, institution_id: str = None) -> str:
    """
    Generate a unique enquiry number in the format: ENQ-{TIMESTAMP}-{SEQUENCE}
    Example: ENQ-20260122-0001
    
    Args:
        db: AsyncSession database connection
        institution_id: Optional institution ID for more specific numbering
        
    Returns:
        str: Generated unique enquiry number
    """
    # Get current date in YYYYMMDD format
    date_str = datetime.utcnow().strftime("%Y%m%d")
    
    # Count existing enquiry numbers for today
    result = await db.execute(
        select(func.count(AdmissionStudent.id)).where(
            AdmissionStudent.enquiry_number.ilike(f"ENQ-{date_str}%")
        )
    )
    count = result.scalar() or 0
    
    # Generate enquiry number with sequence
    sequence = str(count + 1).zfill(4)  # Pad with zeros (e.g., 0001, 0002)
    enquiry_number = f"ENQ-{date_str}-{sequence}"
    
    return enquiry_number
