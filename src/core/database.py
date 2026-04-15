"""
Database engine, session factories, and startup helpers.

Usage:
    from core.database import get_session          # async DI dependency
    from core.database import async_engine         # for lifespan
"""

from contextlib import contextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine as _create_sync_engine, inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import create_database, database_exists

from core.config import settings

# ── URL variants ──────────────────────────────────────
_sync_url = settings.database_url.replace("+asyncpg", "")

# ── Engines ───────────────────────────────────────────
async_engine = create_async_engine(settings.database_url, echo=False)
sync_engine = _create_sync_engine(_sync_url, pool_size=5, max_overflow=10, pool_pre_ping=True)

# ── Session factories ─────────────────────────────────
_async_session_factory = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

_sync_session_factory = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


# ── Async DI dependency ──────────────────────────────
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI `Depends()` provider — yields one session per request."""
    async with _async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Backward-compat aliases used by existing code
get_db_session = get_session
get_db = get_session


# ── Sync session (Celery / scripts) ──────────────────
@contextmanager
def get_sync_session():
    session = _sync_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Startup helpers ───────────────────────────────────
def ensure_database_exists() -> bool:
    """Create the Postgres database if it doesn't already exist. Returns True if created."""
    if not database_exists(_sync_url):
        create_database(_sync_url)
        return True
    return False


def create_schemas(conn, metadata) -> None:
    """Create any missing Postgres schemas used by the metadata."""
    existing = set(inspect(conn).get_schema_names())
    for schema in metadata._schemas:
        if schema not in existing:
            conn.execute(text(f"CREATE SCHEMA {schema}"))


async def seed_initial_data() -> None:
    """Idempotent seed: roles, super-admin user, modules, screens, permissions."""
    from sqlalchemy.future import select
    from core.security import hash_password
    from common.models.master.user import Role, User
    from common.models.master.screen import Module, Screen, RolePermission

    async with _async_session_factory() as session:
        # ── Roles ─────────────────────────────────────
        roles = (await session.execute(select(Role))).scalars().all()
        admin_role = next((r for r in roles if r.name == "super_admin"), None)
        if admin_role is None:
            admin_role = next((r for r in roles if r.name == "Super Admin"), None)

        if admin_role is None:
            admin_role = Role(name="super_admin", description="Super Administrator with full access")
            session.add(admin_role)
            await session.flush()

        # ── Users ─────────────────────────────────────
        existing_users = (await session.execute(select(User))).scalars().all()
        superadmin_user = next(
            (u for u in existing_users if u.username in {"super_admin", "superadmin"}),
            None,
        )
        if superadmin_user is None:
            session.add(
                User(
                    username="super_admin",
                    user_code="GCT001",
                    email="superadmin@softcell.in",
                    full_name="Super Administrator",
                    password=hash_password("superadmin@123"),
                    is_active=True,
                    is_superuser=True,
                    role_id=admin_role.id,
                )
            )

        # ── Modules ───────────────────────────────────
        modules = (await session.execute(select(Module))).scalars().all()
        module_by_name = {m.name.upper(): m for m in modules}
        required_modules = {
            "ADMISSION": "Admission Module",
            "FINANCE": "Finance Module",
            "GATE": "Gate Module",
        }
        for module_name, module_title in required_modules.items():
            if module_name not in module_by_name:
                module = Module(name=module_name, title=module_title)
                session.add(module)
                await session.flush()
                module_by_name[module_name] = module

        # ── Screens ───────────────────────────────────
        screens = (await session.execute(select(Screen))).scalars().all()
        screen_by_name = {s.name.upper(): s for s in screens}

        required_screens = [
            ("PRE_ADMISSION", "Pre Admission", "ADMISSION"),
            ("ADMISSION_ENQUIRY", "Admission Enquiry", "ADMISSION"),
            ("PAYMENT", "Payment Screen", "FINANCE"),
            ("GATE", "Gate", "GATE"),
            ("VISITOR_PASS_IN", "Visitor Pass", "GATE"),
            ("VISITOR_PASS_OUT", "Visitor Pass Out", "GATE"),
            ("VISITOR_REPORTS", "Visitor Reports", "GATE"),
            ("HOSTEL_STUDENT_OUT", "Hostel Student Pass", "GATE"),
            ("HOSTEL_STUDENT_IN", "Hostel Student In", "GATE"),
            ("HOSTEL_REPORTS", "Hostel Reports", "GATE"),
            ("STAFF_OUT", "Staff Out/In", "GATE"),
            ("STAFF_IN", "Staff In", "GATE"),
            ("STAFF_REPORTS", "Staff Reports", "GATE"),
            ("MATERIAL_OUT_IN", "Material In/Out", "GATE"),
            ("NEW_MATERIAL", "New Material", "GATE"),
            ("MATERIAL_SCRAP", "Scrap Material", "GATE"),
            ("MATERIAL_REPORTS", "Material Reports", "GATE"),
            ("VEHICLE_OUT", "Vehicle Out/In", "GATE"),
            ("VEHICLE_IN", "Vehicle In", "GATE"),
            ("VEHICLE_REPORTS", "Vehicle Reports", "GATE"),
        ]

        added_screen_ids = []
        for screen_name, screen_title, module_name in required_screens:
            if screen_name not in screen_by_name:
                module = module_by_name.get(module_name)
                if module is None:
                    continue
                screen = Screen(
                    name=screen_name,
                    title=screen_title,
                    module_id=module.id,
                    parent_id=None,
                )
                session.add(screen)
                await session.flush()
                screen_by_name[screen_name] = screen
                added_screen_ids.append(screen.id)

        # ── Permissions for super-admin ───────────────
        if admin_role is not None:
            existing_perms = (
                await session.execute(
                    select(RolePermission).where(RolePermission.role_id == admin_role.id)
                )
            ).scalars().all()
            existing_perm_screen_ids = {perm.screen_id for perm in existing_perms}

            gate_screen_ids = [
                screen.id
                for name, screen in screen_by_name.items()
                if name in {
                    "GATE",
                    "VISITOR_PASS_IN",
                    "VISITOR_PASS_OUT",
                    "VISITOR_REPORTS",
                    "HOSTEL_STUDENT_OUT",
                    "HOSTEL_STUDENT_IN",
                    "HOSTEL_REPORTS",
                    "STAFF_OUT",
                    "STAFF_IN",
                    "STAFF_REPORTS",
                    "MATERIAL_OUT_IN",
                    "NEW_MATERIAL",
                    "MATERIAL_SCRAP",
                    "MATERIAL_REPORTS",
                    "VEHICLE_OUT",
                    "VEHICLE_IN",
                    "VEHICLE_REPORTS",
                }
            ]

            target_screen_ids = set(gate_screen_ids) | set(added_screen_ids)
            for screen_id in target_screen_ids:
                if screen_id in existing_perm_screen_ids:
                    continue
                session.add(
                    RolePermission(
                        role_id=admin_role.id,
                        screen_id=screen_id,
                        can_view=True,
                        can_create=True,
                        can_edit=True,
                        can_delete=True,
                    )
                )

        await session.commit()
