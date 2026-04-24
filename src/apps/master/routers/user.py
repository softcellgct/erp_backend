from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.master.services.user import MasterUserService
from common.models.master.user import Role
from common.schemas.master.user import (
    UserCreateSchema,
    UserResponseSchema,
    UserUpdateSchema,
    RoleCreateSchema,
    RoleResponse,
    RoleUpdateSchema,
)
from components.db.db import get_db_session
from components.generator.routes import create_crud_routes
from components.middleware import is_superadmin

# User Router
user_router = APIRouter()

# Manual routes for users to use Service logic (hashing pw etc)
@user_router.post("/", response_model=UserResponseSchema, tags=["Users"])

async def create_new_user(request: Request, user: UserCreateSchema, db: AsyncSession = Depends(get_db_session)):
    return await MasterUserService(db).create_user(user)

@user_router.get("/", response_model=List[UserResponseSchema], tags=["Users"])

async def get_all_users(request: Request, db: AsyncSession = Depends(get_db_session)):
    return await MasterUserService(db).get_users()

@user_router.put("/{user_id}", response_model=UserResponseSchema, tags=["Users"])

async def update_existing_user(
    request: Request, user_id: UUID, user: UserUpdateSchema, db: AsyncSession = Depends(get_db_session)
):
    return await MasterUserService(db).update_user(user_id, user)

@user_router.delete("/{user_id}", tags=["Users"])

async def delete_existing_user(request: Request, user_id: UUID, db: AsyncSession = Depends(get_db_session)):
    return await MasterUserService(db).delete_user(user_id)


# Role Router
role_router = APIRouter()
role_crud = create_crud_routes(
    Role,
    RoleCreateSchema,
    RoleUpdateSchema,
    RoleResponse,
    RoleResponse,
    decorators=[is_superadmin],
)
role_router.include_router(role_crud, prefix="/roles", tags=["Role"])
