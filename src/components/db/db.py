"""Backward-compat shim — use `core.database` in new code."""
from core.database import (  # noqa: F401
    async_engine as db_engine,
    sync_engine,
    get_session as get_db_session,
    get_session as get_db,
    _async_session_factory as async_session,
    ensure_database_exists as create_database_if_not_exists,
    create_schemas as setup_schemas,
    seed_initial_data as create_roles_and_users,
    get_sync_session,
)