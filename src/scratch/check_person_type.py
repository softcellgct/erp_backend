import asyncio
from sqlalchemy import text
from core.database import async_engine

async def check():
    async with async_engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'visitors' AND column_name = 'person_type'
        """))
        row = result.fetchone()
        if row:
            print(f"Column 'person_type': {row}")
        else:
            print("Column 'person_type' not found.")

if __name__ == "__main__":
    asyncio.run(check())
