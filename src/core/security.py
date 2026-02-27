"""
Security helpers: password hashing, JWT tokens, middleware, decorators.

Usage:
    from core.security import hash_password, verify_password
    from core.security import create_access_token, decode_token
    from core.security import AuthMiddleware, public_route, require_superadmin
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional

from fastapi import Depends, Request, status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

from core.config import settings
from core.logging import logger

# ═══════════════════════════════════════════════════════
#  Password hashing
# ═══════════════════════════════════════════════════════
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return _pwd_ctx.verify(plain, hashed)
    except (UnknownHashError, Exception):
        return False


# ═══════════════════════════════════════════════════════
#  JWT tokens
# ═══════════════════════════════════════════════════════
_SECRET = settings.secret_key
_ALGO = settings.algorithm
_DEFAULT_EXPIRE = settings.access_token_expire_minutes


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=_DEFAULT_EXPIRE))
    payload["exp"] = expire
    return jwt.encode(payload, _SECRET, algorithm=_ALGO)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _SECRET, algorithms=[_ALGO])


# ═══════════════════════════════════════════════════════
#  Auth middleware
# ═══════════════════════════════════════════════════════
_http_bearer = HTTPBearer(auto_error=False)

PUBLIC_PATHS = frozenset({"/favicon.ico", "/docs", "/openapi.json", "/redoc"})


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate every request via Bearer JWT, attach user to request.state."""

    # ── helpers ───────────────────────────────────
    @staticmethod
    def _is_public_route(request: Request) -> bool:
        for route in request.app.routes:
            if isinstance(route, APIRoute):
                match, _ = route.matches(request.scope)
                if match == Match.FULL:
                    return bool(getattr(route.endpoint, "is_public", False))
        return False

    # ── main dispatch ─────────────────────────────
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        path, method = request.url.path, request.method

        def _finalise(response):
            ms = (time.perf_counter() - start) * 1000
            response.headers["X-Response-Time"] = f"{ms:.2f}ms"
            logger.info(f"{method} {path} → {response.status_code} ({ms:.1f}ms)")
            return response

        # Skip auth for CORS preflight, public paths, and decorated endpoints
        if method == "OPTIONS" or path in PUBLIC_PATHS or self._is_public_route(request):
            return _finalise(await call_next(request))

        # Authenticate
        user, err = await self._authenticate(request)
        if err:
            return _finalise(err)

        request.state.user = user
        return _finalise(await call_next(request))

    async def _authenticate(self, request: Request):
        auth = request.headers.get("Authorization")
        if not auth:
            return None, JSONResponse({"detail": "Missing authentication token."}, status.HTTP_401_UNAUTHORIZED)

        try:
            scheme, token = auth.split()
            if scheme.lower() != "bearer":
                raise ValueError
        except ValueError:
            return None, JSONResponse({"detail": "Invalid auth header format."}, status.HTTP_401_UNAUTHORIZED)

        try:
            payload = jwt.decode(token, _SECRET, algorithms=[_ALGO])
        except JWTError:
            return None, JSONResponse({"detail": "Invalid or expired token."}, status.HTTP_401_UNAUTHORIZED)

        user_id = payload.get("id")
        token_type = payload.get("type")
        if token_type != "access" or not user_id:
            return None, JSONResponse({"detail": "Invalid token payload."}, status.HTTP_401_UNAUTHORIZED)

        identity_type = payload.get("identity_type", "user")

        from core.database import get_session

        async for session in get_session():
            if identity_type == "cash_counter":
                from common.models.billing.cash_counter import CashCounter
                result = await session.execute(select(CashCounter).where(CashCounter.id == user_id))
                cc = result.scalar_one_or_none()
                if not cc:
                    return None, JSONResponse({"detail": "Cash counter not found."}, status.HTTP_401_UNAUTHORIZED)
                request.state.auth_payload = payload
                request.state.cash_counter = cc
                request.state.user = None
                return cc, None
            else:
                from common.models.master.user import User
                result = await session.execute(
                    select(User).where(User.id == user_id).options(selectinload(User.role))
                )
                user = result.scalar_one_or_none()
                if not user:
                    return None, JSONResponse({"detail": "User not found."}, status.HTTP_401_UNAUTHORIZED)
                request.state.auth_payload = payload
                return user, None


# ═══════════════════════════════════════════════════════
#  Decorators
# ═══════════════════════════════════════════════════════
def public_route(func):
    """Mark an endpoint as public (no auth required)."""
    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
    else:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
    wrapper.is_public = True
    return wrapper


def require_superadmin(func):
    """Decorator: reject non-superadmin callers with 403."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request: Request = kwargs.get("request")
        user = getattr(getattr(request, "state", None), "user", None)
        if not user:
            return JSONResponse({"detail": "Unauthorized"}, status.HTTP_401_UNAUTHORIZED)
        if not user.is_superuser:
            return JSONResponse({"detail": "Superadmin access required"}, status.HTTP_403_FORBIDDEN)
        return await func(*args, **kwargs)
    return wrapper


# ── FastAPI dependency (no-op; auth is handled by middleware) ──
async def get_current_user(token: HTTPAuthorizationCredentials = Depends(_http_bearer)):
    pass
