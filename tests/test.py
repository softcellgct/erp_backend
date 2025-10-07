# Updated crud.py
# Now handles roles and screen-specific permissions.
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User, Role, Screen, Permission
from .schemas import PermissionCreate, UserCreate, RoleCreate
from passlib.context import CryptContext
from uuid import uuid4

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_user(db: AsyncSession, user_id: UUID):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()

async def get_user_by_login(db: AsyncSession, login_name: str):
    result = await db.execute(select(User).where(User.login_name == login_name))
    return result.scalars().first()

async def create_user(db: AsyncSession, user: UserCreate):
    # Assuming hashed_password added to User model; extend User with hashed_password: Mapped[str] = mapped_column(String)
    hashed_password = pwd_context.hash(user.password)
    db_user = User(
        login_name=user.login_name,
        welcome_name=user.welcome_name,
        days=user.days,
        role_id=user.role_id,
        hashed_password=hashed_password  # Add this field to model
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def create_role(db: AsyncSession, role: RoleCreate):
    db_role = Role(name=role.name)
    db.add(db_role)
    await db.commit()
    await db.refresh(db_role)
    return db_role

async def create_permission(db: AsyncSession, role_id: UUID, permission: PermissionCreate):
    db_permission = Permission(
        role_id=role_id,
        screen_id=permission.screen_id,
        can_view=permission.can_view,
        can_create=permission.can_create,
        can_edit=permission.can_edit,
        can_delete=permission.can_delete
    )
    db.add(db_permission)
    await db.commit()
    await db.refresh(db_permission)
    return db_permission

async def get_permissions_for_role(db: AsyncSession, role_id: UUID):
    result = await db.execute(select(Permission).where(Permission.role_id == role_id))
    return result.scalars().all()

async def get_screen(db: AsyncSession, screen_id: UUID):
    result = await db.execute(select(Screen).where(Screen.id == screen_id))
    return result.scalars().first()

# Helper to check if user has permission via their role
async def has_permission(db: AsyncSession, user_id: UUID, screen_id: UUID, action: str):
    user = await get_user(db, user_id)
    if not user or not user.role:
        return False
    permissions = await get_permissions_for_role(db, user.role.id)
    for perm in permissions:
        if perm.screen_id == screen_id:
            if action == "view" and perm.can_view:
                return True
            elif action == "create" and perm.can_create:
                return True
            elif action == "edit" and perm.can_edit:
                return True
            elif action == "delete" and perm.can_delete:
                return True
    return False