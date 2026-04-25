import asyncio
from sqlalchemy import select
from src.database import async_session_maker
from src.common.models.billing.fee_head import FeeHead

async def test():
    async with async_session_maker() as session:
        result = await session.execute(select(FeeHead))
        heads = result.scalars().all()
        print(f"TOTAL FEE HEADS: {len(heads)}")
        for h in heads:
            print(f"- {h.name}")

asyncio.run(test())
