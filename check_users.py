import asyncio
from sqlalchemy import select
from core.database import async_session_maker
from common.models.master.user import User

async def test():
    async with async_session_maker() as session:
        result = await session.execute(select(User).order_by(User.created_at.desc()).limit(3))
        users = result.scalars().all()
        for u in users:
            print(f"User: {u.username}, Email: {u.email}, Code: {u.user_code}, PwdHash: {u.password[:15]}...")

asyncio.run(test())
