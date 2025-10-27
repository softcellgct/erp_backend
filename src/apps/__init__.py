from .gate.routers import router as gate_router
from .auth.routers import users_router, auth_router,  permissions_router
from .master.routers import institution_router, department_router, course_router, class_router, academic_year_router,sem_period_router,role_router

ROUTERS = [
    (auth_router, "/api"),
    (users_router, "/api"),
    (role_router, "/api"),
    (permissions_router, "/api"),
    (gate_router, "/api"),
    (institution_router, "/api/master"),
    (department_router, "/api/master"),
    (course_router, "/api/master"),
    (class_router, "/api/master"),
    (academic_year_router, "/api/master"),
    (sem_period_router, "/api/master"),
]