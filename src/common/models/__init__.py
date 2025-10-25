from .auth.user import (
    User,
    Institution,
    UserPermission,
    Screen,
    Module,
    Role,
)

from common.models.master.academic_year import AcademicYear

__all__ = ["Institution", "User", "Role", "UserPermission", "Screen", "Module", "AcademicYear"]
# __all__ = ["Role"]
