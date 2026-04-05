from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.master.user import Role, User
from common.schemas.master.user import RoleCreateSchema, UserCreateSchema
from components.utils.password_utils import get_password_hash

class RoleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_roles(self):
        try:
            query = select(Role)
            result = await self.db.execute(query)
            roles = result.scalars().all()
            return roles
        except Exception as e:
            raise e

    async def create_role(self, role_data: RoleCreateSchema):
        try:
            data = Role(**role_data.model_dump())
            self.db.add(data)
            await self.db.commit()
            await self.db.refresh(data)
            return data
        except Exception as e:
            raise e

    async def update_role(self, role_id: UUID, role_data: RoleCreateSchema):
        try:
            query = select(Role).where(Role.id == role_id)
            result = await self.db.execute(query)
            role = result.scalar_one_or_none()
            if not role:
                raise HTTPException(status_code=404, detail="Role not found")
            for key, value in role_data.model_dump().items():
                setattr(role, key, value)
            self.db.add(role)
            await self.db.commit()
            await self.db.refresh(role)
            return role
        except Exception as e:
            raise e

    async def delete_role(self, role_id: UUID):
        try:
            query = select(Role).where(Role.id == role_id)
            result = await self.db.execute(query)
            role = result.scalar_one_or_none()
            if not role:
                raise HTTPException(status_code=404, detail="Role not found")
            await self.db.delete(role)
            await self.db.commit()
            return {"detail": "Role deleted successfully"}
        except Exception as e:
            raise e


class MasterUserService: # Renamed to avoid confusion with Auth UserService
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, user_data: UserCreateSchema):
        try:
            hashed_password = get_password_hash(user_data.password)
            user_data.password = hashed_password
            data = User(**user_data.model_dump())
            self.db.add(data)
            await self.db.commit()
            await self.db.refresh(data)
            return data
        except Exception as e:
            raise e

    async def get_users(self):
        try:
            query = select(User).options()
            result = await self.db.execute(query)
            users = result.scalars().all()
            return users
        except Exception as e:
            raise e

    async def update_user(self, user_id: UUID, user_data: UserCreateSchema):
        try:
            query = select(User).where(User.id == user_id)
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            for key, value in user_data.model_dump().items():
                if key == "password":
                    value = get_password_hash(value)
                setattr(user, key, value)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except Exception as e:
            raise e

    async def delete_user(self, user_id: UUID):
        try:
            query = select(User).where(User.id == user_id)
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            await self.db.delete(user)
            await self.db.commit()
            return {"detail": "User deleted successfully"}
        except Exception as e:
            raise e
