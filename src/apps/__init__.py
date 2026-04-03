from .gate.routers import (
    router as gate_router,
    person_type_router,
    visitor_router,
    admission_visitor_router,
)
from .auth.routers import (
    auth_router,
)
from .master.routers import (
    institution_router,
    department_router,
    course_router,
    class_router,
    academic_year_router,
    sem_period_router,
    role_router,
    user_router as users_router,
    permissions_router,
    module_router,
    screen_router,
    admission_masters_router,
    staff_router,
    school_router
)
from .master.required_certificates_routers import required_certificates_router
from .master.files.routers import router as file_router
from .admission.routers import consultancy_router, admission_entry_router, admission_router, lead_followup_router
from .admission.verification_routers import verification_router
from .admission.department_change_routers import department_change_router
from .admission.ocr_router import ocr_router
from .billing.routers import router as billing_router
from .billing.scholarship_routers import router as scholarship_router
from .billing.refund_routers import router as refund_router
from .billing.finance_routers import router as finance_router
from .meta.routers import religion_router, community_router, caste_router
from .master.routers import hostel_router

ROUTERS = [
    (auth_router, "/api"),
    (users_router, "/api/users"),
    (role_router, "/api"),
    (permissions_router, "/api"),
    (gate_router, "/api"),
    (institution_router, "/api/master"),
    (department_router, "/api/master"),
    (course_router, "/api/master"),
    (class_router, "/api/master"),
    (academic_year_router, "/api/master"),
    (sem_period_router, "/api/master"),
    (required_certificates_router, "/api/master"),
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
    (admission_router, "/api/admission/admitted"),
    (lead_followup_router, "/api/admission/follow-up"),
    (verification_router, "/api/admission"),
    (ocr_router, "/api/admission"),
    (department_change_router, "/api/admission"),
    (billing_router, "/api/billing"),
    (scholarship_router, "/api/billing/scholarships"),
    (refund_router, "/api/billing/refunds"),
    (finance_router, "/api/finance"),
    (hostel_router, "/api/master"),
    (admission_masters_router, "/api/master"),
    (school_router, "/api/master"),
    (staff_router, "/api/master"),
]
