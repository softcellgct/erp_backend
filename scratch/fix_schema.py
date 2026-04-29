
import asyncio
from sqlalchemy import text
from core.database import async_engine

async def fix_schema():
    async with async_engine.begin() as conn:
        print("Adding missing columns to admission_student_previous_academic_details...")
        await conn.execute(text("""
            ALTER TABLE admission_student_previous_academic_details 
            ADD COLUMN IF NOT EXISTS sslc_total_marks FLOAT,
            ADD COLUMN IF NOT EXISTS sslc_obtained_marks FLOAT,
            ADD COLUMN IF NOT EXISTS hsc_total_marks FLOAT,
            ADD COLUMN IF NOT EXISTS hsc_obtained_marks FLOAT;
        """))
        print("Successfully added columns.")

if __name__ == "__main__":
    asyncio.run(fix_schema())
