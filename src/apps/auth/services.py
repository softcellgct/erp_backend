from datetime import timedelta
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from common.models.auth.user import Module, RolePermission, Screen, User, Role
from common.schemas.auth.user_schemas import LoginSchema, UserCreateSchema
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