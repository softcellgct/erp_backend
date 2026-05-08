import asyncio
from sqlalchemy import text
from core.database import async_engine

async def check_db():
    async with async_engine.connect() as conn:
        result = await conn.execute(text("SELECT * FROM pg_indexes WHERE tablename = 'visitors';"))
        for row in result:
            print(row)
            
        print("\nChecking for duplicate pass numbers:")
        result = await conn.execute(text("SELECT pass_number, COUNT(*) FROM visitors GROUP BY pass_number HAVING COUNT(*) > 1;"))
        for row in result:
            print(row)

if __name__ == "__main__":
    asyncio.run(check_db())
