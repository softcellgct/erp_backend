
import asyncio
from sqlalchemy import select
from core.database import _async_session_factory
from common.models.master.screen import Module, Screen

async def check_screens():
    async with _async_session_factory() as session:
        result = await session.execute(select(Module).where(Module.name == 'MASTER'))
        master_module = result.scalar_one_or_none()
        if not master_module:
            print("MASTER module not found")
            return
        
        print(f"MASTER Module ID: {master_module.id}, Active: {master_module.is_active}")
        
        screens_result = await session.execute(select(Screen).where(Screen.module_id == master_module.id))
        screens = screens_result.scalars().all()
        print(f"Total Screens in MASTER: {len(screens)}")
        for s in screens:
            print(f"Screen: {s.name}, ID: {s.id}, ModuleID: {s.module_id}")

if __name__ == "__main__":
    asyncio.run(check_screens())
