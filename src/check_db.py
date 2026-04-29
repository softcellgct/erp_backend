
import asyncio
from uuid import UUID
from sqlalchemy import select
from core.database import _async_session_factory
from common.models.master.user import User, Role
from common.models.master.screen import RolePermission, Screen, Module

async def check_db():
    async with _async_session_factory() as session:
        # Check users
        users_result = await session.execute(select(User).options(selectinload(User.role)))
        users = users_result.scalars().all()
        print(f"Total Users: {len(users)}")
        for u in users:
            print(f"User: {u.username}, Role: {u.role.name if u.role else 'None'}, RoleID: {u.role_id}")

        # Check roles
        roles_result = await session.execute(select(Role))
        roles = roles_result.scalars().all()
        print(f"Total Roles: {len(roles)}")
        for r in roles:
            # Count permissions
            perms_result = await session.execute(select(RolePermission).where(RolePermission.role_id == r.id))
            perms = perms_result.scalars().all()
            print(f"Role: {r.name}, Perms Count: {len(perms)}")

        # Check modules
        modules_result = await session.execute(select(Module))
        modules = modules_result.scalars().all()
        print(f"Total Modules: {len(modules)}")
        for m in modules:
            print(f"Module: {m.name}, Active: {m.is_active}")

if __name__ == "__main__":
    from sqlalchemy.orm import selectinload
    asyncio.run(check_db())
