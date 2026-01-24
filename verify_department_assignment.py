import asyncio
from uuid import uuid4
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from components.db.db import get_db_session
from apps.master.services import MasterService
from common.models.auth.user import Institution, Department
from common.models.master.academic_year import AcademicYear
from common.schemas.master.academic_year import AcademicYearDepartmentCreate, AcademicYearSchema

async def verify_assignment():
    async for db in get_db_session():
        service = MasterService(db)
        
        # 1. Create Data
        inst_id = uuid4()
        inst = Institution(id=inst_id, code=f"TEST_INST_{uuid4().hex[:8]}", name="Test Inst", is_active=True)
        db.add(inst)
        
        dept_id = uuid4()
        dept = Department(id=dept_id, code=f"TEST_DEPT_{uuid4().hex[:8]}", name="Test Dept", institution_id=inst_id, is_active=True)
        db.add(dept)
        
        ay_id = uuid4()
        ay = AcademicYear(
            id=ay_id, 
            year_name=f"2025-2026-{uuid4().hex[:8]}", 
            from_date=date(2025, 6, 1), 
            to_date=date(2026, 5, 31),
            institution_id=inst_id,
            status=True,
            admission_active=True
        )
        db.add(ay)
        await db.commit()
        
        print(f"Created AY: {ay_id}, Dept: {dept_id}")

        # 2. Assign Department
        assignment_data = AcademicYearDepartmentCreate(
            department_id=dept_id,
            application_fee=500.0,
            is_active=True
        )
        
        # Call the new service method
        try:
            result = await service.assign_department_to_academic_year(ay_id, assignment_data)
            print("Assignment successful")
            
            # 3. Verify
            # Fetch directly or via service if method exists
            # We can inspect the relationship or query the table
            from sqlalchemy import select
            from common.models.master.academic_year import AcademicYearDepartment
            
            stmt = select(AcademicYearDepartment).where(
                AcademicYearDepartment.academic_year_id == ay_id,
                AcademicYearDepartment.department_id == dept_id
            )
            result = await db.execute(stmt)
            record = result.scalar_one_or_none()
            
            assert record is not None, "Record not found in DB"
            assert record.application_fee == 500.0, f"Expected fee 500.0, got {record.application_fee}"
            print("Verification passed: Record found with correct fee")

        except Exception as e:
            print(f"Verification failed: {e}")
            raise e
        finally:
            # Cleanup
            # Deleting parent (Institution) should cascade delete children if configured, 
            # but let's be explicit to avoid constraints issues if cascades aren't set up perfectly.
            # Based on models, ondelete="CASCADE" is present on keys.
            await db.delete(inst) # Should cascade to Dept and AY?
            # Let's delete explicitly to be safe as Institution delete logic might be soft delete in service but hard delete here
            # Actually models have cascade delete.
            # But let's delete strictly dependencies first
            try:
                if record: await db.delete(record)
                await db.delete(ay)
                await db.delete(dept)
                await db.delete(inst)
                await db.commit()
            except Exception as e:
                print(f"Cleanup warning: {e}")

if __name__ == "__main__":
    asyncio.run(verify_assignment())
