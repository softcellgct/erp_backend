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
        existing_roles = (await session.execute(select(Role))).scalars().all()
        admin_role = None

        if not existing_roles:
            roles = [
                Role(name="Super Admin", description="Full access"),
                Role(name="Principal", description="Principal-level access"),
                Role(name="HOD", description="Head of Department access"),
                Role(name="Teacher", description="Teacher access"),
                Role(name="Staff", description="Staff access"),
                Role(name="Student", description="Student access"),
            ]
            session.add_all(roles)
            await session.commit()
            admin_role = roles[0]
            await session.refresh(admin_role)
        else:
            admin_role = next((r for r in existing_roles if r.name == "Super Admin"), None)

        # ── Users ─────────────────────────────────────
        existing_users = (await session.execute(select(User))).scalars().all()
        if not existing_users and admin_role:
            superadmin = User(
                username="superadmin",
                user_code="GCT1",
                email="superadmin@example.com",
                full_name="Super Admin",
                password=hash_password("superadmin@123"),
                is_active=True,
                is_superuser=True,
                role_id=admin_role.id,
            )
            session.add(superadmin)
            await session.commit()

        # ── Modules ───────────────────────────────────
        existing_modules = (await session.execute(select(Module))).scalars().all()
        if not existing_modules:
            modules = [
                Module(name="Admission", description="Student admissions"),
                Module(name="Master", description="System configuration"),
                Module(name="Gate", description="Entry/exit management"),
                Module(name="Billing", description="Fee & finance"),
            ]
            session.add_all(modules)
            await session.commit()
            existing_modules = modules

        # ── Screens ───────────────────────────────────
        existing_screens = (await session.execute(select(Screen))).scalars().all()
        if not existing_screens:
            module_map = {m.name.lower(): m.id for m in existing_modules}
            screens = [
                Screen(name="Dashboard", module_id=module_map.get("admission"), description="Overview statistics"),
                Screen(name="PRE_ADMISSION", title="Pre Admission", module_id=module_map.get("admission")),
                Screen(name="ADMISSION_ENQUIRY", title="Admission Enquiry", module_id=module_map.get("admission")),
                Screen(name="PAYMENT", title="Payment Screen", module_id=module_map.get("billing")),
            ]
            session.add_all(screens)
            await session.commit()
            existing_screens = screens

        # ── Permissions for super-admin ───────────────
        existing_perms = (await session.execute(select(RolePermission))).scalars().all()
        if not existing_perms and admin_role:
            perms = [
                RolePermission(
                    role_id=admin_role.id,
                    screen_id=s.id,
                    can_view=True,
                    can_add=True,
                    can_edit=True,
                    can_delete=True,
                )
                for s in existing_screens
            ]
            session.add_all(perms)
            await session.commit()
