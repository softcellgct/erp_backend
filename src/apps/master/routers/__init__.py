from .institution import (
    institution_router,
    department_router,
    course_router,
    class_router,
    hostel_router
)
from .annual_task import (
    academic_year_router,
    sem_period_router
)
from .user import (
    user_router,
    role_router
)
from .screen import (
    permissions_router,
    module_router,
    screen_router
)

# Import remaining routers from the old file until refactored
# role_router moved to new .user module

