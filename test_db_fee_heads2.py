import asyncio
from sqlalchemy import select
from core.database import async_session_maker
from common.models.billing.fee_head import FeeHead

async def test():
    async with async_session_maker() as session:
        result = await session.execute(select(FeeHead))
        heads = result.scalars().all()
        print(f"TOTAL FEE HEADS: {len(heads)}")
        for h in heads:
            print(f"- id: {h.id}, name: {h.name}")

asyncio.run(test())
