import asyncio
from sqlalchemy import text
from core.database import async_engine

async def check():
    async with async_engine.connect() as conn:
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'visitors'"))
        columns = [row[0] for row in result.fetchall()]
        print(f"Columns in visitors: {columns}")

if __name__ == "__main__":
    asyncio.run(check())
