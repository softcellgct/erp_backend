
import asyncio
from sqlalchemy import text
from core.database import async_engine

async def check_schema():
    async with async_engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'admission_student_previous_academic_details';
        """))
        columns = [row[0] for row in result.fetchall()]
        print(f"Columns in admission_student_previous_academic_details: {columns}")

if __name__ == "__main__":
    asyncio.run(check_schema())
