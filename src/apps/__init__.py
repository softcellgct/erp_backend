from .gate.routers import router as gate_router
from .auth.routers import users_router, auth_router, roles_router, permissions_router
from .master.routers import router as master_router

ROUTERS = [
    (auth_router, "/api"),
    (users_router, "/api"),
    (roles_router, "/api"),
    (permissions_router, "/api"),
    (gate_router, "/api"),
    (master_router, "/api/master")
]