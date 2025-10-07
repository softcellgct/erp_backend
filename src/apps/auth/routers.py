from uuid import UUID
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from apps.auth.services import RoleService, UserService
from common.schemas.auth.user_schemas import LoginSchema, UserCreateSchema
from components.db.db import get_db_session
from components.middleware import is_superadmin, public_route

roles_router = APIRouter(tags=["Auth - Roles"])

@roles_router.get("/roles",
                  name="Get Roles",
                  description="Retrieve a list of all roles in the system.",)
async def get_roles(request:Request, db: AsyncSession = Depends(get_db_session)):
    return await RoleService(db).get_roles()



users_router = APIRouter(tags=["Auth - Users"])

@users_router.post("/users",
                   name="Create User",
                   description="Create a new user in the system.",
                   )
async def create_user(request:Request, user_data:UserCreateSchema, db: AsyncSession = Depends(get_db_session)):
    return await UserService(db).create_user(user_data)

@users_router.get(
    "/users",
    name="Get Users",
    description="Retrieve a list of all users in the system.",
)
@is_superadmin
async def get_users(request: Request, db: AsyncSession = Depends(get_db_session)):
    return await UserService(db).get_users()

@users_router.get(
    "/users/me",
    name="Get Current User",
    description="Retrieve information about the currently authenticated user.",
)
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db_session)):
    return await UserService(db).get_current_user(request)

@users_router.put(
    "/users/{user_id}",
    name="Update User",
    description="Update information for a specific user by user ID.",
)
async def update_current_user(request: Request, user_id: UUID, user_data: UserCreateSchema, db: AsyncSession = Depends(get_db_session)):
    return await UserService(db).update_user(user_id, user_data)

@users_router.delete(
    "/users/{user_id}",
    name="Delete User",
    description="Delete a specific user by user ID.",
)
async def delete_user(request: Request, user_id: UUID, db: AsyncSession = Depends(get_db_session)):
    return await UserService(db).delete_user(user_id)



auth_router = APIRouter(tags=["Auth - Authentication"])

@auth_router.post("/login")
@public_route
async def user_login(request:Request, login_data:LoginSchema ,db: AsyncSession = Depends(get_db_session)):
    return await UserService(db).login(request,login_data)


@auth_router.get("/role-permissions")
async def get_role_permissions(request: Request, db: AsyncSession = Depends(get_db_session)):
    return await UserService(db).get_role_permissions(request.state.user.role.id,request)
    # return request.state.user

# @router.get("/roles")
# @public_route
# async def get_roles(request:Request, db: AsyncSession = Depends(get_db_session)):
#     return await UserService(db).get_roles()