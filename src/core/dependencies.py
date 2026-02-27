"""
Shared FastAPI dependency providers.

Usage in routers:
    from core.dependencies import DbSession, CurrentUser
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session


# ── Type aliases for cleaner router signatures ────────
DbSession = Annotated[AsyncSession, Depends(get_session)]


def _get_user(request: Request):
    return getattr(request.state, "user", None)


CurrentUser = Annotated[object, Depends(_get_user)]
