"""Backward-compat shim — use `core.security` in new code."""
from core.security import (  # noqa: F401
    AuthMiddleware as PermissionMiddleware,
    get_current_user,
    public_route,
    require_superadmin as is_superadmin,
)
