from uuid import UUID
from components.db.base_model import Base
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import Boolean, ForeignKey, Integer, String, event
from components.utils.password_utils import get_password_hash
from sqlalchemy import insert, select
from logs.logging import logger


class Role(Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(255))

    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        lazy="selectin",
        foreign_keys="[RolePermission.role_id]",
        cascade="all, delete-orphan",
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="role",
        lazy="selectin",
        foreign_keys="[User.role_id]",
        cascade="all, delete-orphan",
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
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"))

    # Relationships
    role: Mapped["Role"] = relationship("Role", foreign_keys=[role_id], lazy="selectin")
    # user_permissions: Mapped[list["UserPermission"]] = relationship("UserPermission", back_populates="user", foreign_keys="[UserPermission.user_id]")


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


class Institution(Base):
    from ..master.academic_year import AcademicYear

    __tablename__ = "institutions"
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    departments: Mapped[list["Department"]] = relationship(back_populates="institution")
    academic_years: Mapped[list["AcademicYear"]] = relationship(
        "AcademicYear", back_populates="institution"
    )


class Department(Base):
    __tablename__ = "departments"
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    institution: Mapped["Institution"] = relationship(back_populates="departments")
    courses: Mapped[list["Course"]] = relationship(back_populates="department")


class Course(Base):
    __tablename__ = "courses"
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    short_name: Mapped[str | None] = mapped_column(
        String(50), unique=True, index=True, nullable=True
    )  # Short name / abbreviation
    level: Mapped[str] = mapped_column(
        String(10), nullable=False, default="UG", server_default="UG"
    )  # "UG" or "PG"
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    course_duration_years: Mapped[int] = mapped_column(Integer, nullable=False)
    total_semesters: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    department: Mapped["Department"] = relationship(back_populates="courses")
    classes: Mapped[list["Class"]] = relationship(back_populates="course")


class Class(Base):
    __tablename__ = "classes"
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    course_id: Mapped[UUID] = mapped_column(ForeignKey("courses.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="classes")


class Module(Base):
    __tablename__ = "modules"
    name: Mapped[str] = mapped_column(
        String(50), unique=True, index=True
    )  # e.g., ADMISSION, FINANCE
    title: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    screens: Mapped[list["Screen"]] = relationship(back_populates="module")


@event.listens_for(Module.__table__, "after_create")
def insert_initial_modules(target, connection, **kwargs):
    try:
        initial_modules = [
            {"name": "ADMISSION", "title": "Admission Module"},
            {"name": "FINANCE", "title": "Finance Module"},
            # Add more modules as needed
        ]
        connection.execute(insert(Module), initial_modules)
        logger.info("Inserted initial modules into the modules table.")
    except Exception as e:
        print(f"Failed to insert initial modules: {e}")


class Screen(Base):
    __tablename__ = "screens"
    name: Mapped[str] = mapped_column(
        String(50), unique=True, index=True
    )  # e.g., PRE_ADMISSION, ADMISSION_ENQUIRY
    title: Mapped[str] = mapped_column(String(255))
    module_id: Mapped[UUID] = mapped_column(ForeignKey("modules.id"))
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("screens.id"), nullable=True
    )  # For hierarchy
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    module: Mapped["Module"] = relationship(back_populates="screens")
    parent: Mapped["Screen"] = relationship(
        back_populates="children", remote_side="Screen.id"
    )
    children: Mapped[list["Screen"]] = relationship(back_populates="parent")
    # permissions: Mapped[list["Permission"]] = relationship(back_populates="screen")
    # user_permissions: Mapped[list["UserPermission"]] = relationship("UserPermission", back_populates="screen", foreign_keys="[UserPermission.screen_id]")
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="screen",
        foreign_keys="[RolePermission.screen_id]",
    )


@event.listens_for(Screen.__table__, "after_create")
def insert_initial_screens(target, connection, **kwargs):
    try:
        # Get module ids
        result = connection.execute(select(Module.id).where(Module.name == "ADMISSION"))
        admission_id = result.scalar()

        result = connection.execute(select(Module.id).where(Module.name == "FINANCE"))
        finance_id = result.scalar()

        initial_screens = [
            {
                "name": "PRE_ADMISSION",
                "title": "Pre Admission",
                "module_id": admission_id,
                "parent_id": None,
            },
            {
                "name": "ADMISSION_ENQUIRY",
                "title": "Admission Enquiry",
                "module_id": admission_id,
                "parent_id": None,
            },
            {
                "name": "PAYMENT",
                "title": "Payment Screen",
                "module_id": finance_id,
                "parent_id": None,
            },
            # Add more screens as needed, including hierarchies if required
        ]
        connection.execute(insert(Screen), initial_screens)
        logger.info("Inserted initial screens into the screens table.")
    except Exception as e:
        print(f"Failed to insert initial screens: {e}")


class Permission(Base):
    __tablename__ = "permissions"
    key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    path: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(String(255))
    tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Relationships
    # screen: Mapped["Screen"] = relationship(back_populates="permissions")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    screen_id: Mapped[UUID] = mapped_column(ForeignKey("screens.id"), primary_key=True)
    can_view: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_create: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    role: Mapped["Role"] = relationship(back_populates="role_permissions")
    screen: Mapped["Screen"] = relationship(back_populates="role_permissions")


@event.listens_for(RolePermission.__table__, "after_create")
def insert_initial_role_permissions(target, connection, **kwargs):
    try:
        # Get super_admin role id
        result = connection.execute(select(Role.id).where(Role.name == "super_admin"))
        super_admin_id = result.scalar()

        # Get all screen ids
        screen_results = connection.execute(select(Screen.id))
        screen_ids = screen_results.scalars().all()

        initial_permissions = []
        for screen_id in screen_ids:
            initial_permissions.append(
                {
                    "role_id": super_admin_id,
                    "screen_id": screen_id,
                    "can_view": True,
                    "can_create": True,
                    "can_edit": True,
                    "can_delete": True,
                }
            )

        if initial_permissions:
            connection.execute(insert(RolePermission), initial_permissions)
            logger.info("Inserted initial role permissions for super_admin.")
    except Exception as e:
        print(f"Failed to insert initial role permissions: {e}")


class UserPermission(Base):
    __tablename__ = "user_permissions"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    screen_id: Mapped[UUID] = mapped_column(ForeignKey("screens.id"), primary_key=True)
    can_view: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )  # None means "inherit from role"
    can_create: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    can_edit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    can_delete: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Relationships
    # user: Mapped["User"] = relationship(back_populates="user_permissions")
    # screen: Mapped["Screen"] = relationship(back_populates="user_permissions")
