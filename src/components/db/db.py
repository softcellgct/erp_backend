from contextlib import contextmanager
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import create_engine as create_sync_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from common.models.auth.user import RolePermission
from components.settings import settings
from typing import AsyncGenerator
from sqlalchemy_utils import create_database, database_exists


create_db_url = settings.database_url.replace("+asyncpg", "")


def setup_schemas(conn, metadata):
    inspector = inspect(conn)
    all_schemas = inspector.get_schema_names()
    for schema in metadata._schemas:
        if schema not in all_schemas:
            _create_schema(conn, schema)
    
def _create_schema(conn, schema) -> None:
    stmt = text(f"CREATE SCHEMA {schema}")
    conn.execute(stmt)

def create_engine(url, **kwargs):
    """Create an asynchronous SQLAlchemy engine."""
    return create_async_engine(url, echo=False, **kwargs)


def create_database_if_not_exists():
    if not database_exists(create_db_url):
        create_database(create_db_url)
        return True
    return False


# Use a single async engine for both read and write
db_engine = create_engine(settings.database_url)

# Single async sessionmaker
async_session = async_sessionmaker(
    bind=db_engine, autocommit=False, autoflush=False, expire_on_commit=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to provide a database session (read/write).
    """
    async with async_session() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()


# ===============================================
#               SYNC Session for CELERY
# ===============================================
# Create a regular / blocking engine

sync_engine = create_sync_engine(
    create_db_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@contextmanager
def get_sync_session():
    """
    Yields a sync SQLAlchemy session.
    Commits on success, rolls back on error, always closes.
    """
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()


async def create_roles_and_users():
    from common.models.auth.user import User,Module,Role,Screen
    from sqlalchemy.future import select
    from components.utils.password_utils import get_password_hash

    async with async_session() as session:
        # Check if roles exist
        result = await session.execute(select(Role))
        roles = result.scalars().all()

        if not roles:
            # Create all required roles
            initial_roles = [
            Role(name="Super Admin", description="Super Administrator with full access"),
            Role(name="Principal", description="Principal user with elevated access"),
            Role(name="HOD", description="Head of Department with specialized access"),
            Role(name="Teacher", description="Teacher with standard access"),
            Role(name="Staff", description="Staff member with limited access"),
            Role(name="Student", description="Student with limited access"),
            ]
            await session.add_all(initial_roles)
            await session.commit()
            # Refresh the super_admin role for later use
            admin_role = next((role for role in initial_roles if role.name == "super_admin"), None)
            if admin_role:
                await session.refresh(admin_role)

        # Find the super_admin role if roles already exist
        users = await session.execute(select(User))
        users = users.scalars().all()
        if not users:

            # Create a default superadmin user
            superadmin_user = User(
                username="superadmin",
                user_code="GCT1",
                email="superadmin@example.com",
                full_name="Super Admin",
                password=get_password_hash("superadmin@123"),
                is_active=True,
                is_superuser=True,
                role_id=admin_role.id,
            )
            await session.add(superadmin_user)
            await session.commit()
            await session.refresh(superadmin_user)

        modules = await session.execute(select(Module))
        modules = modules.scalars().all()

        if not modules:
            # Create all required modules
            initial_modules = [
                Module(name="Admission", description="Manage student admissions"),
                Module(name="User Management", description="Manage users and roles"),
                Module(name="Course Management", description="Manage courses and related entities"),
                Module(name="Examination", description="Manage examinations and results"),
                Module(name="Library", description="Manage library resources"),
                Module(name="Hostel Management", description="Manage hostel accommodations"),
                Module(name="Transport Management", description="Manage transportation services"),
                Module(name="Inventory Management", description="Manage inventory and supplies"),
                Module(name="Finance", description="Manage financial transactions and records"),
                Module(name="Attendance", description="Manage attendance records"),
                Module(name="Timetable", description="Manage class schedules and timetables"),
            ]
            await session.add_all(initial_modules)
            await session.commit()

        screens = await session.execute(select(Screen))
        screens = screens.scalars().all()

        if not screens:
            # Get module ids for mapping
            module_map = {m.name.lower(): m.id for m in initial_modules} if modules == [] else {m.name.lower(): m.id for m in modules}
            # Create all required screens with correct module_id references
            initial_screens = [
            Screen(name="Dashboard", module_id=module_map.get("admission"), description="View overall statistics and summaries"),
            Screen(name="User List", module_id=module_map.get("user management"), description="View and manage user accounts"),
            Screen(name="Role Management", module_id=module_map.get("user management"), description="Create and manage user roles"),
            Screen(name="Course Catalog", module_id=module_map.get("course management"), description="View and manage course offerings"),
            Screen(name="Examination Schedule", module_id=module_map.get("examination"), description="View and manage exam schedules"),
            Screen(name="Library Catalog", module_id=module_map.get("library"), description="View and manage library resources"),
            Screen(name="Hostel Allocation", module_id=module_map.get("hostel management"), description="Manage hostel room assignments"),
            Screen(name="Transport Routes", module_id=module_map.get("transport management"), description="Manage transportation routes and schedules"),
            Screen(name="Inventory List", module_id=module_map.get("inventory management"), description="View and manage inventory items"),
            Screen(name="Financial Reports", module_id=module_map.get("finance"), description="View financial statements and reports"),
            Screen(name="Attendance Records", module_id=module_map.get("attendance"), description="View and manage attendance data"),
            Screen(name="Timetable Management", module_id=module_map.get("timetable"), description="Create and manage class timetables"),
            # Example screens from your event-based structure:
            Screen(name="PRE_ADMISSION", title="Pre Admission", module_id=module_map.get("admission"), parent_id=None),
            Screen(name="ADMISSION_ENQUIRY", title="Admission Enquiry", module_id=module_map.get("admission"), parent_id=None),
            Screen(name="PAYMENT", title="Payment Screen", module_id=module_map.get("finance"), parent_id=None),
            ]
            await session.add_all(initial_screens)
            await session.commit()

        role_permissions = await session.execute(select(RolePermission))
        role_permissions = role_permissions.scalars().all()

        if not role_permissions:
            # Assign all permissions to superadmin role
            if admin_role:
                all_screens = await session.execute(select(Screen))
                all_screens = all_screens.scalars().all()
                permissions = [
                    RolePermission(
                        role_id=admin_role.id,
                        screen_id=screen.id,
                        can_view=True,
                        can_add=True,
                        can_edit=True,
                        can_delete=True,
                    )
                    for screen in all_screens
                ]
                await session.add_all(permissions)
                await session.commit()

        