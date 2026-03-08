from uuid import UUID
from components.db.base_model import Base
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import Boolean, ForeignKey, Integer, String, event, insert, select
from logs.logging import logger
from components.utils.password_utils import get_password_hash

class Role(Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))

    # Relationships — lazy="selectin" avoids loading ALL users/permissions on role fetch
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        lazy="selectin",
        foreign_keys="RolePermission.role_id",
        cascade="all, delete-orphan",
    )
    # NEVER cascade delete-orphan on users — deleting a role must NOT delete users
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="role",
        lazy="selectin",
        foreign_keys="User.role_id",
    )


@event.listens_for(Role.__table__, "after_create")
def insert_initial_values(target, connection, **kwargs):  # Add **kwargs
    try:
        initial_roles = [
            {
                "name": "super_admin",
                "description": "Super Administrator with full access",
            },
            {"name": "principal", "description": "Principal user with elevated access"},
            {
                "name": "hod",
                "description": "Head of Department with specialized access",
            },
            {"name": "teacher", "description": "Teacher with standard access"},
            {"name": "staff", "description": "Staff member with limited access"},
            {"name": "student", "description": "Student with limited access"},
            {"name": "cashier", "description": "Cash Counter Staff"},
        ]
        connection.execute(insert(Role), initial_roles)
        logger.info("Inserted initial roles into the roles table.")
    except Exception as e:
        print(f"Failed to insert initial roles: {e}")


class User(Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), index=True)

    # Relationships
    role: Mapped["Role"] = relationship("Role", foreign_keys=[role_id], lazy="selectin")
    user_permissions: Mapped[list["UserPermission"]] = relationship(
        "UserPermission",
        back_populates="user",
        foreign_keys="UserPermission.user_id",
        lazy="selectin",
    )


@event.listens_for(User.__table__, "after_create")
def insert_initial_user(target, connection, **kwargs):
    try:
        # Get super_admin role id
        result = connection.execute(select(Role.id).where(Role.name == "super_admin"))
        super_admin_role_id = result.scalar()

        # Insert initial super_admin user
        super_admin_user = {
            "email": "superadmin@softcell.in",
            "username": "super_admin",
            "user_code": "GCT001",
            "full_name": "Super Administrator",
            "password": get_password_hash("superadmin@123"),  # simple hash for demo
            "is_active": True,
            "is_superuser": True,
            "role_id": super_admin_role_id,
        }
        connection.execute(insert(User), [super_admin_user])
    except Exception as e:
        print(f"Failed to insert initial roles or super_admin user: {e}")
