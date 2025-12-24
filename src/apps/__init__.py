from .gate.routers import (
    router as gate_router,
    person_type_router,
    visitor_router,
    admission_visitor_router,
)
from .auth.routers import (
    users_router,
    auth_router,
    permissions_router,
    module_router,
    screen_router,
)
from .master.routers import (
    institution_router,
    department_router,
    course_router,
    class_router,
    academic_year_router,
    sem_period_router,
    role_router,
)
from .master.files.routers import router as file_router
from .admission.routers import consultancy_router, admission_entry_router,admission_router
from .billing.routers import router as billing_router
from .meta.routers import religion_router, community_router, caste_router

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
    (file_router, "/api/master/files"),
    (person_type_router, "/api/gate"),
    (visitor_router, "/api/gate"),
    (admission_visitor_router, "/api/gate"),
    (consultancy_router, "/api/admission"),
    (religion_router, "/api/meta"),
    (community_router, "/api/meta"),
    (caste_router, "/api/meta"),
    (module_router, "/api/master"),
    (screen_router, "/api/master"),
    (admission_entry_router, "/api/admission"),
    (admission_router, "/api/admission/admitted")
    ,(billing_router, "/api/billing")
]
