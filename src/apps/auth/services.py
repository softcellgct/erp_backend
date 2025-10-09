from ast import List
from datetime import timedelta
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import selectinload
from common.models.auth.user import Module, RolePermission, Screen, User, Role
from common.schemas.auth.user_schemas import LoginSchema, PermissionAssignSchema, UserCreateSchema
from components.utils.password_utils import get_password_hash, verify_password
from components.utils.security import create_access_token


class RoleService:
    def __init__(self, db):
        self.db = db

    async def get_roles(self):
        try:
            query = select(Role)  # Eager load users
            result = await self.db.execute(query)
            roles = result.scalars().all()
            return roles
        except Exception as e:
            raise e


class UserService:
    def __init__(self, db):
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

    async def login(self, request: Request, login_data: LoginSchema):
        try:
            query = select(User).where(
                or_(
                    User.username == login_data.identifier,
                    User.email == login_data.identifier,
                )
            )
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()
            if not user or not verify_password(login_data.password, user.password):
                raise HTTPException(
                    status_code=401, detail="Invalid username or password"
                )
            access_token = create_access_token(
                data={"id": str(user.id), "type": "access"},
                expires_delta=timedelta(days=1),
            )
            request.state.user = user
            return {
                "detail": f"Welcome, {user.username}",
                "access_token": access_token,
                "token_type": "bearer",
            }
        except Exception as e:
            raise e

    async def get_current_user(self, request):
        try:
            user = request.state.user
            if not user:
                raise HTTPException(status_code=401, detail="Unauthorized")
            return user
        except Exception as e:
            raise e

    async def get_roles(self):
        try:
            query = select(Role)  # Eager load users
            result = await self.db.execute(query)
            roles = result.scalars().all()
            return roles
        except Exception as e:
            raise e

    async def get_users(self):
        try:
            query = select(User).options()  # Eager load roles
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

    async def get_role_permissions(self, role_id: str, request):
            try:
                # Only fetch active modules
                modules_query = select(Module).where(Module.is_active.is_(True))
                modules_result = await self.db.execute(modules_query)
                active_modules = {m.id: m for m in modules_result.scalars().all()}

                # Query all RolePermission entries for the given role_id, eagerly loading related Screen and Module
                query = select(RolePermission).options(
                    selectinload(RolePermission.screen).selectinload(Screen.module)
                ).where(
                    RolePermission.role_id == role_id
                )
                result = await self.db.execute(query)
                role_permissions = result.scalars().all()

                # Fetch the role itself
                role_query = select(Role).where(Role.id == role_id)
                role_result = await self.db.execute(role_query)
                role = role_result.scalar_one_or_none()

                modules = {}
                screens = []

                for rp in role_permissions:
                    screen = rp.screen
                    module = screen.module if screen else None
                    # Only include active modules
                    if module and module.id in active_modules:
                        modules[module.id] = {
                            "id": str(module.id),
                            "name": module.name,
                            "title": module.title,
                        }
                    if screen and module and module.id in active_modules:
                        screens.append(
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
                return {
                    "role": {
                        "id": str(role.id) if role else None,
                        "name": role.name if role else None,
                        "description": role.description if role else None,
                    },
                    "user": {
                        "id": str(request.state.user.id),
                        "username": request.state.user.username,
                        "email": request.state.user.email,
                        "role_id": str(request.state.user.role_id) if request.state.user.role_id else None,
                    },
                    "all_modules": {str(m.id): {"id": str(m.id), "name": m.name, "title": m.title} for m in active_modules.values()},
                    "permitted_modules": list(modules.values()),
                    "screens": screens
                }
            except Exception as e:
                raise e


class PermissionService:
    def __init__(self, db):
        self.db = db

    async def bulk_add_permissions(self, permissions_data: list[PermissionAssignSchema], role_id: str = None):
        try:
            if not permissions_data:
                # Remove all permissions for the role
                if not role_id:
                    raise HTTPException(status_code=400, detail="role_id is required when permissions_data is empty")
                delete_query = delete(RolePermission).where(RolePermission.role_id == role_id)
                await self.db.execute(delete_query)
                await self.db.commit()
                return {"detail": "All permissions removed for role"}
            
            # Validate all permissions have the same role_id
            for perm in permissions_data:
                if perm.role_id != permissions_data[0].role_id:
                    raise HTTPException(status_code=400, detail="All permissions must have the same role_id")
            
            # Group incoming permissions by (role_id, screen_id) for easy lookup
            incoming_perms = {(permissions_data[0].role_id, perm.screen_id): perm for perm in permissions_data}

            # Fetch all existing permissions for the role
            query = select(RolePermission).where(RolePermission.role_id == permissions_data[0].role_id)
            result = await self.db.execute(query)
            existing_permissions = result.scalars().all()

            # Track which permissions to update, add, or delete
            to_update = []
            to_add = []
            to_delete = []

            existing_keys = {(perm.role_id, perm.screen_id) for perm in existing_permissions}

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
                        can_delete=perm.can_delete
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
    async def remove_all_permissions_for_role(self, role_id: str):
        # Now calls bulk_add_permissions with empty list and role_id
        return await self.bulk_add_permissions([], role_id=role_id)
        # Now calls bulk_add_permissions with empty list
        return await self.bulk_add_permissions([])

    async def _remove_all_permissions_for_role(self, role_id: str):
        # Updated helper to remove all permissions for a given role
        delete_query = delete(RolePermission).where(RolePermission.role_id == role_id)
        await self.db.execute(delete_query)
        await self.db.commit()

    async def get_modules_and_screens(self):
        try:
            # Get all active modules with their screens
            query = select(Module).where(Module.is_active.is_(True)).options(
                selectinload(Module.screens.and_(Screen.is_active.is_(True)))
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
                        "parent_id": str(screen.parent_id) if screen.parent_id else None
                    }
                    for screen in module.screens
                ]
                modules_data.append({
                    "id": str(module.id),
                    "name": module.name,
                    "title": module.title,
                    "screens": screens_data
                })
            
            return modules_data
        except Exception as e:
            raise e

    async def get_role_permissions(self, role_id):
        try:
            query = select(RolePermission).where(RolePermission.role_id == role_id).options(
                selectinload(RolePermission.screen).selectinload(Screen.module)
            )
            result = await self.db.execute(query)
            permissions = result.scalars().all()
            
            # Format the response
            permissions_data = []
            for perm in permissions:
                permissions_data.append({
                    "id": str(perm.id),
                    "role_id": str(perm.role_id),
                    "screen": {
                        "id": str(perm.screen.id),
                        "name": perm.screen.name,
                        "title": perm.screen.title,
                        "module": {
                            "id": str(perm.screen.module.id),
                            "name": perm.screen.module.name,
                            "title": perm.screen.module.title
                        } if perm.screen.module else None
                    },
                    "can_view": perm.can_view,
                    "can_create": perm.can_create,
                    "can_edit": perm.can_edit,
                    "can_delete": perm.can_delete
                })
            
            return permissions_data
        except Exception as e:
            raise e                            