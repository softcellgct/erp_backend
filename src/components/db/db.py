from contextlib import contextmanager
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import create_engine as create_sync_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
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
