from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import and_, delete, null, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from common.models.master.screen import Module, RolePermission, Screen, UserPermission
from common.models.master.user import Role
from common.schemas.master.user import PermissionAssignSchema, UserPermissionAssignSchema

class ScreenService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_modules_and_screens(self):
        try:
            # Get all active modules with their screens
            query = (
                select(Module)
                .where(and_(Module.is_active.is_(True),
                            Module.deleted_at.is_(null())))
                .options(selectinload(Module.screens))
            )
            result = await self.db.execute(query)
            modules = result.scalars().all()

            # Format the response
            modules_data = []
            for module in modules:
                screens_data = [
                    {
                        "id": str(screen.id),
                        "name": screen.name,
                        "title": screen.title,
                        "is_active": screen.is_active,
                        "parent_id": str(screen.parent_id)
                        if screen.parent_id
                        else None,
                    }
                    for screen in module.screens
                ]
                modules_data.append(
                    {
                        "id": str(module.id),
                        "name": module.name,
                        "title": module.title,
                        "screens": screens_data,
                    }
                )

            return modules_data
        except Exception as e:
            raise e

    async def get_permissions(self, role_id: str, user_id: str = None):
        try:
            # Only fetch active modules
            modules_query = select(Module).where(and_(Module.is_active.is_(True)
                                                      , Module.deleted_at.is_(null())))
            modules_result = await self.db.execute(modules_query)
            active_modules = {m.id: m for m in modules_result.scalars().all()}

            # Ensure role_id is a UUID object for consistent querying
            role_uuid = role_id if isinstance(role_id, UUID) else UUID(str(role_id))

            # Query all RolePermission entries for the given role_id, eagerly loading related Screen and Module
            role_query = (
                select(RolePermission)
                .options(
                    selectinload(RolePermission.screen).selectinload(Screen.module)
                )
                .where(RolePermission.role_id == role_uuid)
            )
            role_result = await self.db.execute(role_query)
            role_permissions = role_result.scalars().all()

            # Query all UserPermission entries for the given user_id, if provided
            user_permissions = []
            if user_id:
                user_query = (
                    select(UserPermission)
                    .options(
                        selectinload(UserPermission.screen).selectinload(Screen.module)
                    )
                    .where(UserPermission.user_id == UUID(user_id))
                )
                user_result = await self.db.execute(user_query)
                user_permissions = user_result.scalars().all()

            # Fetch the role itself
            role_query = select(Role).where(Role.id == role_uuid)
            role_result = await self.db.execute(role_query)
            role = role_result.scalar_one_or_none()

            modules = {}
            role_screens = []
            user_screens = []

            for rp in role_permissions:
                screen = rp.screen
                module = screen.module if screen else None
                # Only include screens from active modules
                if screen and module and module.id in active_modules:
                    # Add module to permitted list if any permission is granted
                    if rp.can_view or rp.can_create or rp.can_edit or rp.can_delete:
                        modules[module.id] = {
                            "id": str(module.id),
                            "name": module.name,
                            "title": module.title,
                            "module_img_url": module.module_img_url,
                        }
                    role_screens.append(
                        {
                            "id": str(screen.id),
                            "name": screen.name,
                            "title": screen.title,
                            "module_id": str(screen.module_id),
                            "can_view": rp.can_view,
                            "can_create": rp.can_create,
                            "can_edit": rp.can_edit,
                            "can_delete": rp.can_delete,
                        }
                    )


            for up in user_permissions:
                screen = up.screen
                module = screen.module if screen else None
                if screen and module and module.id in active_modules:
                    user_screens.append(
                        {
                            "id": str(screen.id),
                            "name": screen.name,
                            "title": screen.title,
                            "module_id": str(screen.module_id),
                            "can_view": up.can_view,
                            "can_create": up.can_create,
                            "can_edit": up.can_edit,
                            "can_delete": up.can_delete,
                        }
                    )
            
            response = {
                "role": {
                    "id": str(role.id) if role else None,
                    "name": role.name if role else None,
                    "description": role.description if role else None,
                },
                "all_modules": {
                    str(m.id): {
                        "id": str(m.id),
                        "name": m.name,
                        "title": m.title,
                        "module_img_url": m.module_img_url,
                    }
                    for m in active_modules.values()
                },
                "permitted_modules": list(modules.values()),
                "role_screens": role_screens,
                "user_screens": user_screens,
            }
            
            return response

        except Exception as e:
            raise e

    async def bulk_add_permissions(
        self, permissions_data: list[PermissionAssignSchema], role_id: str = None
    ):
        try:
            if not permissions_data:
                # Remove all permissions for the role
                if not role_id:
                    raise HTTPException(
                        status_code=400,
                        detail="role_id is required when permissions_data is empty",
                    )
                # Ensure role_id is a UUID object
                role_uuid = role_id if isinstance(role_id, UUID) else UUID(str(role_id))
                delete_query = delete(RolePermission).where(
                    RolePermission.role_id == role_uuid
                )
                await self.db.execute(delete_query)
                await self.db.commit()
                return {"detail": "All permissions removed for role"}

            # Validate all permissions have the same role_id
            for perm in permissions_data:
                if perm.role_id != permissions_data[0].role_id:
                    raise HTTPException(
                        status_code=400,
                        detail="All permissions must have the same role_id",
                    )

            # Group incoming permissions by (role_id, screen_id) for easy lookup
            incoming_perms = {
                (permissions_data[0].role_id, perm.screen_id): perm
                for perm in permissions_data
            }

            # Fetch all existing permissions for the role
            query = select(RolePermission).where(
                RolePermission.role_id == permissions_data[0].role_id
            )
            result = await self.db.execute(query)
            existing_permissions = result.scalars().all()

            # Track which permissions to update, add, or delete
            to_update = []
            to_add = []
            to_delete = []

            existing_keys = {
                (perm.role_id, perm.screen_id) for perm in existing_permissions
            }

            # Update or mark for deletion
            for perm in existing_permissions:
                key = (perm.role_id, perm.screen_id)
                if key in incoming_perms:
                    # Update permission
                    new_perm = incoming_perms[key]
                    perm.can_view = new_perm.can_view
                    perm.can_create = new_perm.can_create
                    perm.can_edit = new_perm.can_edit
                    perm.can_delete = new_perm.can_delete
                    to_update.append(perm)
                else:
                    # Permission removed, mark for deletion
                    to_delete.append(perm)

            # Add new permissions
            for key, perm in incoming_perms.items():
                if key not in existing_keys:
                    new_permission = RolePermission(
                        role_id=permissions_data[0].role_id,
                        screen_id=perm.screen_id,
                        can_view=perm.can_view,
                        can_create=perm.can_create,
                        can_edit=perm.can_edit,
                        can_delete=perm.can_delete,
                    )
                    to_add.append(new_permission)

            # Apply changes
            if to_update:
                self.db.add_all(to_update)
            if to_add:
                self.db.add_all(to_add)
            for perm in to_delete:
                await self.db.delete(perm)

            await self.db.commit()
            # Optionally refresh all new permissions
            for perm in to_add:
                await self.db.refresh(perm)
            return {"detail": "Permissions processed successfully"}
        except Exception as e:
            raise e

    async def get_simple_role_permissions(self, role_id: str):
        try:
            query = (
                select(RolePermission)
                .where(RolePermission.role_id == role_id)
                .options(
                    selectinload(RolePermission.screen).selectinload(Screen.module)
                )
            )
            result = await self.db.execute(query)
            permissions = result.scalars().all()

            # Format the response
            permissions_data = []
            for perm in permissions:
                permissions_data.append(
                    {
                        "id": str(perm.id),
                        "role_id": str(perm.role_id),
                        "screen": {
                            "id": str(perm.screen.id),
                            "name": perm.screen.name,
                            "title": perm.screen.title,
                            "module": {
                                "id": str(perm.screen.module.id),
                                "name": perm.screen.module.name,
                                "title": perm.screen.module.title,
                            }
                            if perm.screen.module
                            else None,
                        },
                        "can_view": perm.can_view,
                        "can_create": perm.can_create,
                        "can_edit": perm.can_edit,
                        "can_delete": perm.can_delete,
                    }
                )

            return permissions_data
        except Exception as e:
            raise e

    async def get_simple_user_permissions(self, user_id: str):
        try:
            query = (
                select(UserPermission)
                .where(UserPermission.user_id == UUID(user_id))
                .options(
                    selectinload(UserPermission.screen).selectinload(Screen.module)
                )
            )
            result = await self.db.execute(query)
            permissions = result.scalars().all()

            # Format the response
            permissions_data = []
            for perm in permissions:
                permissions_data.append(
                    {
                        "id": str(perm.id),
                        "user_id": str(perm.user_id),
                        "screen": {
                            "id": str(perm.screen.id),
                            "name": perm.screen.name,
                            "title": perm.screen.title,
                            "module": {
                                "id": str(perm.screen.module.id),
                                "name": perm.screen.module.name,
                                "title": perm.screen.module.title,
                            }
                            if perm.screen.module
                            else None,
                        },
                        "can_view": perm.can_view,
                        "can_create": perm.can_create,
                        "can_edit": perm.can_edit,
                        "can_delete": perm.can_delete,
                    }
                )

            return permissions_data
        except Exception as e:
            raise e

    async def bulk_add_user_permissions(
        self, permissions_data: list[UserPermissionAssignSchema], user_id: str = None
    ):
        try:
            if not permissions_data:
                # Remove all permissions for the user
                if not user_id:
                    raise HTTPException(
                        status_code=400,
                        detail="user_id is required when permissions_data is empty",
                    )
                delete_query = delete(UserPermission).where(
                    UserPermission.user_id == UUID(user_id)
                )
                await self.db.execute(delete_query)
                await self.db.commit()
                return {"detail": "All permissions removed for user"}

            # Payload user_id is already parsed by Pydantic as UUID.
            # Keep explicit conversion fallback for safety if a string slips through.
            payload_user_id = permissions_data[0].user_id
            user_uuid = payload_user_id if isinstance(payload_user_id, UUID) else UUID(str(payload_user_id))

            # If user_id comes from route path, ensure it matches payload user_id.
            if user_id is not None:
                path_user_uuid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
                if path_user_uuid != user_uuid:
                    raise HTTPException(
                        status_code=400,
                        detail="Path user_id does not match payload user_id",
                    )

            # Validate all permissions have the same user_id
            for perm in permissions_data:
                if perm.user_id != permissions_data[0].user_id:
                    raise HTTPException(
                        status_code=400,
                        detail="All permissions must have the same user_id",
                    )

            # Group incoming permissions by (user_id, screen_id) for easy lookup
            incoming_perms = {
                (user_uuid, perm.screen_id): perm
                for perm in permissions_data
            }

            # Fetch all existing permissions for the user
            query = select(UserPermission).where(
                UserPermission.user_id == user_uuid
            )
            result = await self.db.execute(query)
            existing_permissions = result.scalars().all()

            # Track which permissions to update, add, or delete
            to_update = []
            to_add = []
            to_delete = []

            existing_keys = {
                (perm.user_id, perm.screen_id) for perm in existing_permissions
            }

            # Update or mark for deletion
            for perm in existing_permissions:
                key = (perm.user_id, perm.screen_id)
                if key in incoming_perms:
                    # Update permission
                    new_perm = incoming_perms[key]
                    perm.can_view = new_perm.can_view
                    perm.can_create = new_perm.can_create
                    perm.can_edit = new_perm.can_edit
                    perm.can_delete = new_perm.can_delete
                    to_update.append(perm)
                else:
                    # Permission removed, mark for deletion
                    to_delete.append(perm)

            # Add new permissions
            for key, perm in incoming_perms.items():
                if key not in existing_keys:
                    new_permission = UserPermission(
                        user_id=user_uuid,
                        screen_id=perm.screen_id,
                        can_view=perm.can_view,
                        can_create=perm.can_create,
                        can_edit=perm.can_edit,
                        can_delete=perm.can_delete,
                    )
                    to_add.append(new_permission)

            # Apply changes
            if to_update:
                self.db.add_all(to_update)
            if to_add:
                self.db.add_all(to_add)
            for perm in to_delete:
                await self.db.delete(perm)

            await self.db.commit()
            # Optionally refresh all new permissions
            for perm in to_add:
                await self.db.refresh(perm)
            return {"detail": "Permissions processed successfully"}
        except Exception as e:
            raise e

    async def remove_all_permissions_for_user(self, user_id: str):
        try:
            delete_query = delete(UserPermission).where(UserPermission.user_id == UUID(user_id))
            result = await self.db.execute(delete_query)
            await self.db.commit()
            return {"detail": f"Removed {result.rowcount} permissions for user"}
        except Exception as e:
            raise e
