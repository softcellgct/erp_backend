from uuid import UUID
from components.db.base_model import Base
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, event, insert, select
from logs.logging import logger

class Module(Base):
    __tablename__ = "modules"
    name: Mapped[str] = mapped_column(
        String(50), unique=True, index=True
    )  # e.g., ADMISSION, FINANCE
    title: Mapped[str] = mapped_column(String(255))
    module_img_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    screens: Mapped[list["Screen"]] = relationship(back_populates="module", lazy="selectin")


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
    )
    title: Mapped[str] = mapped_column(String(255))
    module_id: Mapped[UUID] = mapped_column(ForeignKey("modules.id"), index=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("screens.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships — lazy="selectin" avoids recursive N+1 on parent/children tree
    module: Mapped["Module"] = relationship(back_populates="screens", lazy="selectin")
    parent: Mapped["Screen"] = relationship(
        "Screen", back_populates="children", remote_side="Screen.id", lazy="selectin"
    )
    children: Mapped[list["Screen"]] = relationship(
        "Screen",
        back_populates="parent", lazy="selectin"
    )
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="screen",
        foreign_keys="RolePermission.screen_id",
        lazy="selectin",
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


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id"), nullable=False, index=True)
    screen_id: Mapped[UUID] = mapped_column(ForeignKey("screens.id"), nullable=False, index=True)
    can_view: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_create: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="role_permissions", lazy="selectin")
    screen: Mapped["Screen"] = relationship("Screen", back_populates="role_permissions", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("role_id", "screen_id", name="uq_role_screen"),
    )


@event.listens_for(RolePermission.__table__, "after_create")
def insert_initial_role_permissions(target, connection, **kwargs):
    from common.models.master.user import Role # Late import to avoid circular dependency
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



