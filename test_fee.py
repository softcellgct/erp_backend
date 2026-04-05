import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/src')

from core.database import async_session_maker
from common.models.admission.admission_entry import AdmissionStudent
from sqlalchemy import select, update

async def main():
    async with async_session_maker() as session:
        # Check an APPLIED student
        stmt = select(AdmissionStudent).where(AdmissionStudent.status == "APPLIED").limit(1)
        res = await session.execute(stmt)
        student = res.scalar_one_or_none()
        if not student:
            print("No student")
            return
            
        print(f"Before: locked={student.is_fee_structure_locked}, id={student.id}")
        
        # update fee structure directly
        update_stmt = (
            update(AdmissionStudent)
            .where(AdmissionStudent.id == student.id)
            .values(fee_structure_id=None)
        )
        await session.execute(update_stmt)
        await session.commit()
        
        # check again
        res = await session.execute(select(AdmissionStudent).where(AdmissionStudent.id == student.id))
        st2 = res.scalar_one_or_none()
        print(f"After: locked={st2.is_fee_structure_locked}")

asyncio.run(main())
