from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from apps.auth.services import RoleService, UserService, PermissionService
from common.schemas.auth.role_schemas import RoleCreateSchema
from common.schemas.auth.user_schemas import (
    LoginSchema,
    UserCreateSchema,
    PermissionAssignSchema,
)
from components.db.db import get_db_session
from components.middleware import is_superadmin, public_route

# ===========================================================
# Roles Router
# ===========================================================

roles_router = APIRouter(tags=["Auth - Roles"])


@roles_router.get(
    "/roles",
    name="Get Roles",
    status_code=200,
    description="Retrieve a list of all roles in the system.",
)
async def get_roles(request: Request, db: AsyncSession = Depends(get_db_session)):
    return await RoleService(db).get_roles()


@roles_router.post(
    "/roles",
    name="Create Role",
    status_code=201,
    description="Create a new role in the system.",
)
@is_superadmin
async def create_role(
    request: Request,
    role_data: RoleCreateSchema,
    db: AsyncSession = Depends(get_db_session),
):
    return await RoleService(db).create_role(role_data)


@roles_router.put(
    "/roles/{role_id}",
    name="Update Role",
    status_code=200,
    description="Update an existing role in the system.",
)
@is_superadmin
async def update_role(
    request: Request,
    role_id: UUID,
    role_data: RoleCreateSchema,
    db: AsyncSession = Depends(get_db_session),
):
    return await RoleService(db).update_role(role_id, role_data)


@roles_router.delete(
    "/roles/{role_id}",
    name="Delete Role",
    status_code=200,
    description="Delete an existing role from the system.",
)
@is_superadmin
async def delete_role(
    request: Request, role_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    return await RoleService(db).delete_role(role_id)


# ===========================================================
# Users Router
# ===========================================================

users_router = APIRouter(tags=["Auth - Users"])


@users_router.post(
    "/users",
    name="Create User",
    status_code=201,
    description="Create a new user in the system.",
)
async def create_user(
    request: Request,
    user_data: UserCreateSchema,
    db: AsyncSession = Depends(get_db_session),
):
    return await UserService(db).create_user(user_data)


@users_router.get(
    "/users",
    name="Get Users",
    status_code=200,
    description="Retrieve a list of all users in the system.",
)
@is_superadmin
async def get_users(request: Request, db: AsyncSession = Depends(get_db_session)):
    return await UserService(db).get_users()


@users_router.get(
    "/users/me",
    name="Get Current User",
    status_code=200,
    description="Retrieve information about the currently authenticated user.",
)
async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db_session)
):
    return await UserService(db).get_current_user(request)


@users_router.put(
    "/users/{user_id}",
    name="Update User",
    status_code=200,
    description="Update information for a specific user by user ID.",
)
async def update_current_user(
    request: Request,
    user_id: UUID,
    user_data: UserCreateSchema,
    db: AsyncSession = Depends(get_db_session),
):
    return await UserService(db).update_user(user_id, user_data)


@users_router.delete(
    "/users/{user_id}",
    name="Delete User",
    status_code=200,
    description="Delete a specific user by user ID.",
)
async def delete_user(
    request: Request, user_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    return await UserService(db).delete_user(user_id)


# ===========================================================
# Auth Router
# ===========================================================


auth_router = APIRouter(tags=["Auth - Authentication"])


@auth_router.post("/login")
@public_route
async def user_login(
    request: Request,
    login_data: LoginSchema,
    db: AsyncSession = Depends(get_db_session),
):
    return await UserService(db).login(request, login_data)


@auth_router.get("/role-permissions")
async def get_role_permissions(
    request: Request, db: AsyncSession = Depends(get_db_session)
):
    return await UserService(db).get_role_permissions(
        request.state.user.role.id, request
    )
    # return request.state.user


# ===========================================================
# Permissions Router
# ===========================================================

permissions_router = APIRouter(tags=["Auth - Permissions"])


@permissions_router.post(
    "/permissions/role/{role_id}/assign",
    name="Assign Permission",
    description="Assign permissions for a role on a specific screen/module.",
)
@is_superadmin
async def assign_permission(
    request: Request,
    role_id: str,
    permission_data: List[PermissionAssignSchema],
    db: AsyncSession = Depends(get_db_session),
):
    return await PermissionService(db).bulk_add_permissions(permission_data, role_id)


@permissions_router.get(
    "/modules-screens",
    name="Get Modules and Screens",
    description="Retrieve a list of all active modules and their associated screens.",
)
async def get_modules_and_screens(
    request: Request, db: AsyncSession = Depends(get_db_session)
):
    return await PermissionService(db).get_modules_and_screens()


@permissions_router.get(
    "/permissions/role/{role_id}",
    name="Get Permissions by Role",
    description="Retrieve all permissions assigned to a specific role.",
)
async def get_permissions_by_role(
    request: Request, role_id: UUID, db: AsyncSession = Depends(get_db_session)
):
    return await PermissionService(db).get_role_permissions(role_id)


@permissions_router.delete(
    "/permissions/role/{role_id}",
    name="Delete Permissions by Role",
    description="Delete all permissions assigned to a specific role.",
)
@is_superadmin
async def delete_permissions_by_role(
    request: Request, role_id: str, db: AsyncSession = Depends(get_db_session)
):
    return await PermissionService(db).remove_all_permissions_for_role(role_id)
