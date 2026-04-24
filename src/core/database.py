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
from core.logging import logger

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


async def ensure_admission_gate_entry_link() -> None:
    """Ensure admission_students.gate_entry_id exists and is linked to admission_gate_entries."""
    try:
        async with async_engine.begin() as conn:
            table_exists = await conn.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = 'admission_students'
                    )
                    """
                )
            )
            if not table_exists.scalar():
                return

            gate_table_exists = await conn.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = 'admission_gate_entries'
                    )
                    """
                )
            )
            if not gate_table_exists.scalar():
                return

            await conn.execute(
                text(
                    """
                    ALTER TABLE admission_students
                    ADD COLUMN IF NOT EXISTS gate_entry_id UUID
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_admission_students_gate_entry_id
                    ON admission_students (gate_entry_id)
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM pg_constraint
                            WHERE conname = 'admission_students_gate_entry_id_fkey'
                        ) THEN
                            ALTER TABLE admission_students
                            ADD CONSTRAINT admission_students_gate_entry_id_fkey
                            FOREIGN KEY (gate_entry_id)
                            REFERENCES admission_gate_entries(id)
                            ON DELETE SET NULL;
                        END IF;
                    END
                    $$;
                    """
                )
            )

            # Best-effort backfill for older rows where enquiry_number matches.
            await conn.execute(
                text(
                    """
                    UPDATE admission_students s
                    SET gate_entry_id = g.id
                    FROM admission_gate_entries g
                    WHERE s.gate_entry_id IS NULL
                      AND s.enquiry_number IS NOT NULL
                      AND g.enquiry_number = s.enquiry_number
                    """
                )
            )

        logger.info("Admission gate-entry link schema check complete ✅")
    except Exception as e:
        logger.warning(f"Admission gate-entry link schema check skipped: {e}")


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
        required_modules = {
            "MASTER": "Master",
            "ADMISSION": "Admission",
            "BILLING": "Billing",
            "GATE": "Gate",
            "TRANSPORT": "Transport",
            "HOSTEL": "Hostel",
            "SIS": "Student Information System",
        }

        # Build map of existing modules by name (only those we need)
        module_by_name = {m.name.upper(): m for m in modules if m.name and m.name.upper() in required_modules}
        existing_names = set(module_by_name.keys())

        # Create missing modules; reactivate required ones that were previously
        # deactivated or soft-deleted (idempotent, scoped to required_modules).
        for module_name, module_title in required_modules.items():
            existing = module_by_name.get(module_name)
            if existing is None:
                module = Module(name=module_name, title=module_title, is_active=True)
                session.add(module)
                await session.flush()
                module_by_name[module_name] = module
            else:
                if not existing.is_active:
                    existing.is_active = True
                if getattr(existing, "deleted_at", None) is not None:
                    existing.deleted_at = None

        # ── Screens ───────────────────────────────────
        screens = (await session.execute(select(Screen))).scalars().all()
        screen_by_name = {s.name.upper(): s for s in screens}

        screens_by_module = {
            "MASTER": [
                "INSTITUTIONS",
                "DEPARTMENTS",
                "ADMISSION_TYPE",
                "SEAT_QUOTA",
                "DOCUMENT_TYPE",
                "REQUIRED_CERTIFICATES",
                "HOSTEL_MANAGEMENT",
                "STAFF_MANAGEMENT",
                "COURSES",
                "CLASSES",
                "ACADEMIC_YEARS",
                "SEMESTER_PERIODS",
                "ROLE_MANAGEMENT",
                "USERS_MANAGEMENT",
                "USER_PERMISSIONS",
                "MODULES",
                "SCREENS",
                "SCHOOL_LIST",
                "RELIGION",
                "COMMUNITY",
                "CASTE",
            ],
            "ADMISSION": [
                "PRE_ADMISSION",
                "ADMISSION_ENQUIRY",
                "ADMISSION_BOOKING",
                "ADMISSION_BOOKED_PAID",
                "APPLIED_STUDENTS_DOCS",
                "LEAD_FOLLOW_UP",
                "PRE_ADMISSION_DASHBOARD",
                "PRE_ADMISSION_REPORTS",
                "ADMISSION_ENTRY",
                "STUDENT_PROFILE",
                "STUDENT_PROFILE_EDIT",
                "ADMISSION_REPORTS",
                "REFERENCE_REPORTS",
                "PERFECT_ENTRY",
                "ROLL_NUMBER_GENERATION",
                "SECTION_ALLOCATION",
                "PROVISIONALLY_ALLOTTED_LIST",
                "LOCK_FEE_STRUCTURE",
                "DEPARTMENT_CHANGE",
                "DEPARTMENT_CHANGE_APPROVAL",
                "FEES_STRUCTURE",
                "CONSULTANCY_MANAGEMENT",
            ],
            "BILLING": [
                "PAYMENT",
                "FEES_COLLECTION",
                "EDIT_FEES",
                "FINANCIAL_YEARS",
                "FEE_HEADS_SUBHEADS",
                "CASH_COUNTERS",
                "FEE_STRUCTURES",
                "DEMAND_CREATION",
                "FEES_RECEIPTS",
                "CONSULTANT_MANAGEMENT",
                "REFERRAL_REPORT",
                "COLLECTION_REPORT",
                "STUDENT_REPORT",
                "STUDENTS_REPORT",
                "BILLING_REPORTS",
                "CONCESSION_FEES",
                "CONCESSION_RULES",
                "FEES_HEAD_CREATION",
                "FINANCIAL_YEAR",
                "TRANSPORT_FEES_STRUCTURE",
                "HOSTEL_FEES_STRUCTURE",
                "CREATE_PAYMENT_GATEWAY",
                "ONLINE_PAYMENTS",
                "SCREEN_APPROVAL",
                "SCHOLARSHIPS",
                "SCHOLARSHIP_CONFIGURATION",
                "GOVERNMENT_SCHOLARSHIPS",
                "MANUAL_CONCESSIONS",
                "STAFF_REFERRAL_CONCESSION",
                "REFUNDS",
                "RECALL_RECEIPT",
                "BULK_RECEIPTS",
                "MULTI_RECEIPTS",
                "GENERAL_LEDGER",
                "STUDENT_LEDGER",
                "STUDENT_DEPOSITS",
                "INVOICES",
            ],
            "GATE": [
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
            ],
            "TRANSPORT": [
                "TRANSPORT_REQUESTS",
                "TRANSPORT_VEHICLES",
                "TRANSPORT_DRIVERS",
                "TRANSPORT_ALLOCATIONS",
                "TRANSPORT_REPORTS",
            ],
            "HOSTEL": [
                "HOSTEL_REQUESTS",
                "HOSTEL_ROOMS",
                "HOSTEL_ALLOCATIONS",
                "HOSTEL_MODULE_REPORTS",
            ],
            "SIS": [
                "SIS_STUDENTS",
                "SIS_ACADEMIC_STRUCTURE",
                "SIS_REPORTS",
            ],
        }

        required_screens = []
        for module_name, screen_names in screens_by_module.items():
            for screen_name in screen_names:
                required_screens.append(
                    (
                        screen_name,
                        screen_name.replace("_", " ").title(),
                        module_name,
                    )
                )

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

            seeded_screen_names = {
                screen_name
                for module_screens in screens_by_module.values()
                for screen_name in module_screens
            }

            seeded_screen_ids = [
                screen.id
                for name, screen in screen_by_name.items()
                if name in seeded_screen_names
            ]

            target_screen_ids = set(seeded_screen_ids) | set(added_screen_ids)
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
