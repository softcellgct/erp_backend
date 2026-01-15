from fastapi import Depends, FastAPI, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.routing import Match
from starlette.middleware.base import BaseHTTPMiddleware
from functools import wraps
from common.models.auth.user import User
from components.db.db import get_db_session
from components.settings import settings
from logs.logging import logger
import asyncio
import time
from jose import JWTError, jwt

app = FastAPI()
http_bearer = HTTPBearer(auto_error=False)


SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


class PermissionMiddleware(BaseHTTPMiddleware):
    def _is_public_route(self, request: Request) -> bool:
        """
        Because HTTP middleware runs before routing, endpoint isn't in scope yet.
        We manually match the incoming request against the app's routes and
        check for the `is_public` attribute on the matched route's endpoint.
        """
        # Iterate through all registered routes and find a full match
        for route in request.app.routes:
            if isinstance(route, APIRoute):
                match, _ = route.matches(request.scope)
                if match == Match.FULL:
                    return bool(getattr(route.endpoint, "is_public", False))
        return False


    # Add logging to the dispatch method to debug the flow
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        start_time = time.perf_counter()

        def log_and_return_response(response):
            response_time = (time.perf_counter() - start_time) * 1000
            response.headers["X-Response-Time"] = f"{response_time:.2f} ms"
            response.headers["X-Powered-By"] = "BloomSkillTech"
            logger.info(
                f"Received request: {method} {path} - Response status: {response.status_code}, Time taken: {response_time:.2f} ms"
            )
            return response

        # Allow favicon/docs/openapi/redoc without auth
        public_paths = {"/favicon.ico", "/docs", "/openapi.json", "/redoc"}
        if request.method == "OPTIONS":
            response = await call_next(request)
            return log_and_return_response(response)

        if request.url.path in public_paths or self._is_public_route(request):
            response = await call_next(request)
            return log_and_return_response(response)

        # Authenticate user
        user, error_response = await self.authenticate_user(request)
        if error_response:
            logger.error("Authentication failed. Returning error response.")
            response = error_response
            return log_and_return_response(response)

        # Attach user object to request
        logger.info(f"Authenticated user: {user.username if user else 'None'}")
        request.state.user = user

        # Proceed with the request
        response = await call_next(request)
        return log_and_return_response(response)

    async def authenticate_user(self, request: Request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None, JSONResponse(
                content={
                    "detail": "Authentication token is missing. Please log in to obtain a valid token."
                },
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                raise ValueError(
                    "Invalid authentication scheme. Expected 'Bearer' token."
                )
        except ValueError:
            return None, JSONResponse(
                content={
                    "detail": "Invalid authentication header format. Expected format: 'Authorization: Bearer <token>'"
                },
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError:
            return None, JSONResponse(
                content={
                    "detail": "The provided token is invalid or has expired. Please log in again to obtain a new token."
                },
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        user_id = payload.get("id")
        token_type = payload.get("type")

        if token_type != "access" or not user_id:
            return None, JSONResponse(
                content={
                    "detail": "Invalid token type. Please provide a valid `access` token to proceed."
                },
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        # Fetch user from DB
        async for session in get_db_session():
            query = await session.execute(
                select(User).where(User.id == user_id).options(selectinload(User.role))
            )
            user = query.scalar_one_or_none()

            if not user:
                return None, JSONResponse(
                    content={
                        "detail": "The user associated with the provided token could not be found. Please ensure you are using a valid token or contact support for assistance."
                    },
                    status_code=status.HTTP_401_UNAUTHORIZED,
                )

            request.state.auth_payload = payload
            return user, None


def public_route(func):
    """
    Decorator to mark a route as public (no auth required).
    Preserves async/sync behavior and function metadata.
    """
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


def is_superadmin(func):
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        request: Request = kwargs.get("request")
        if not hasattr(request, "state") or not getattr(request.state, "user", None):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized: User information missing in request"},
            )

        user = request.state.user
        if not user.is_superuser:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Forbidden: Superadmin access required"},
            )

        return await func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        request: Request = kwargs.get("request")
        if not hasattr(request, "state") or not getattr(request.state, "user", None):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Unauthorized: User information missing in request"},
            )

        user = request.state.user
        if not user.is_superuser:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Forbidden: Superadmin access required"},
            )

        return func(*args, **kwargs)

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(http_bearer),
):
    pass


# async def has_permission(role_id: str, permission_key: str, db: AsyncSession) -> bool:
#     stmt = (
#         select(Permission.id)
#         .join(UserPermission, Permission.id == UserPermission.permission_id)
#         .where(UserPermission.role_id == role_id)
#         .where(Permission.key == permission_key)
#     )
#     result = await db.execute(stmt)
#     return result.scalar_one_or_none() is not None


# def check_permission(permission_key: str):
#     def decorator(func):
#         @wraps(func)
#         async def wrapper(*args, **kwargs):
#             request: Request = kwargs.get("request")
#             db: AsyncSession = kwargs.get("db", None)

#             if not hasattr(request, "state"):
#                 logger.error("Request object is missing 'state'.")
#                 return JSONResponse(
#                     status_code=500,
#                     content={"detail": "Internal server error"},
#                 )

#             if not getattr(request.state, "public", False):
#                 if not hasattr(request.state, "user") or not request.state.user:
#                     return JSONResponse(
#                         status_code=401,
#                         content={
#                             "detail": "Unauthorized: User information missing in request"
#                         },
#                     )

#                 role_id = getattr(request.state.user.role, "id", None)
#                 if not role_id:
#                     return JSONResponse(
#                         status_code=401,
#                         content={
#                             "detail": "Unauthorized: User role information is missing or invalid"
#                         },
#                     )

#                 if not await has_permission(role_id, permission_key, db):
#                     return JSONResponse(
#                         status_code=403,
#                         content={"detail": "Permission denied"},
#                     )

#             return await func(*args, **kwargs)

#         return wrapper

#     return decorator
