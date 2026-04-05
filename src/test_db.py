import sys
import os
import asyncio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.database import async_engine
from sqlalchemy import text

async def run():
    async with async_engine.connect() as conn:
        result = await conn.execute(text("SELECT id, name FROM religions LIMIT 2"))
        rows = result.fetchall()
        print("Rows list:", [dict(r._mapping) for r in rows])

asyncio.run(run())
