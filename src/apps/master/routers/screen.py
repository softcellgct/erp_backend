from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.master.services.screen import ScreenService
from common.models.master.screen import Module, Screen
from common.schemas.master.user import PermissionAssignSchema, UserPermissionAssignSchema
from common.schemas.master.screen import (
    ModuleCreate, ModuleUpdate, ModuleResponse,
    ScreenCreate, ScreenUpdate, ScreenResponse
)
from components.db.db import get_db_session
from components.generator.routes import create_crud_routes
from components.middleware import is_superadmin

# Permission Router
permissions_router = APIRouter()

@permissions_router.get("/permissions", tags=["Permissions"])
async def get_my_permissions(request: Request, db: AsyncSession = Depends(get_db_session)):
    current_user = request.state.user
    role_id = getattr(current_user, 'role_id', None)
    if not current_user or not role_id:
        return {}
    return await ScreenService(db).get_permissions(role_id, str(current_user.id))

@permissions_router.get("/permissions/role/{role_id}", tags=["Permissions"])
@is_superadmin
async def get_role_permissions(
    role_id: str, request: Request, db: AsyncSession = Depends(get_db_session)
):
    return await ScreenService(db).get_simple_role_permissions(role_id)

@permissions_router.post("/permissions/role/{role_id}/assign", tags=["Permissions"])
@is_superadmin
async def assign_permissions(
    request: Request,
    role_id: str,
    permissions: list[PermissionAssignSchema],
    db: AsyncSession = Depends(get_db_session),
):
    # Ensure role_id in permissions matches path if needed, or just let service handle
    return await ScreenService(db).bulk_add_permissions(permissions, role_id=role_id)

@permissions_router.delete("/permissions/role/{role_id}", tags=["Permissions"])
@is_superadmin
async def remove_role_permissions(

    request: Request,role_id: str, db: AsyncSession = Depends(get_db_session)
):
    return await ScreenService(db).remove_all_permissions_for_role(role_id)

@permissions_router.get("/permissions/user/{user_id}", tags=["Permissions"])
@is_superadmin
async def get_user_permissions(
    user_id: str, request: Request, db: AsyncSession = Depends(get_db_session)
):
    return await ScreenService(db).get_simple_user_permissions(user_id)

@permissions_router.post("/permissions/user/{user_id}/assign", tags=["Permissions"])
@is_superadmin
async def assign_user_permissions(
    request: Request,
    user_id: str,
    permissions: list[UserPermissionAssignSchema],
    db: AsyncSession = Depends(get_db_session),
):
    # Ensure user_id in permissions matches path if needed, or just let service handle
    return await ScreenService(db).bulk_add_user_permissions(permissions, user_id=user_id)

@permissions_router.delete("/permissions/user/{user_id}", tags=["Permissions"])
@is_superadmin
async def remove_user_permissions(

    request: Request,user_id: str, db: AsyncSession = Depends(get_db_session)
):
    return await ScreenService(db).remove_all_permissions_for_user(user_id)

@permissions_router.get("/modules-screens", tags=["Permissions"])
async def get_all_modules_and_screens_alias(db: AsyncSession = Depends(get_db_session)):
    return await ScreenService(db).get_modules_and_screens()


# Module Router
module_router = APIRouter()
module_crud = create_crud_routes(
    Module,
    ModuleCreate,
    ModuleUpdate,
    ModuleResponse,
    ModuleResponse,
    decorators=[is_superadmin],
)
module_router.include_router(module_crud, prefix="/modules", tags=["Modules"])

@module_router.get("/screens", tags=["Modules"])  # GET /api/master/modules/screens
async def get_all_modules_and_screens(request: Request,db: AsyncSession = Depends(get_db_session)):
    return await ScreenService(db).get_modules_and_screens()


# Screen Router
screen_router = APIRouter()
screen_crud = create_crud_routes(
    Screen,
    ScreenCreate,
    ScreenUpdate,
    ScreenResponse,
    ScreenResponse,
    decorators=[is_superadmin],
)
screen_router.include_router(screen_crud, prefix="/screens", tags=["Screens"])
