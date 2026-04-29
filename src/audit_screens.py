
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.database import _async_session_factory
from common.models.master.screen import Module, Screen

async def audit_screens():
    async with _async_session_factory() as session:
        result = await session.execute(select(Screen).options(selectinload(Screen.module)))
        screens = result.scalars().all()
        print(f"Total Screens: {len(screens)}")
        for s in screens:
            m_name = s.module.name if s.module else "NO MODULE"
            print(f"Screen: {s.name}, Module: {m_name}")

if __name__ == "__main__":
    asyncio.run(audit_screens())
