from components.db.base_model import Base
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    JSON,
    String,
    UUID,
    UniqueConstraint,
)


class RollNumberTemplate(Base):
    """Saved roll-number format template.

    Reusable per (department + academic year). The ``tokens`` column stores an
    ordered list describing how a roll number is composed, e.g.::

        [
          {"type": "academic_year", "digits": 4},
          {"type": "department_code"},
          {"type": "running_number", "padding": 3, "start": 1,
           "reset_scope": "course_year"}
        ]

    See ``apps/sis/roll_number.py`` for the authoritative token vocabulary and
    the pure ``render_roll_number`` renderer.
    """

    __tablename__ = "sis_roll_number_templates"

    institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True, index=True)
    academic_year_id = Column(UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=True, index=True)

    name = Column(String(150), nullable=True)
    tokens = Column(JSON, nullable=False)
    separator = Column(String(5), nullable=True, default="")
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("department_id", "academic_year_id", name="uq_roll_template_dept_year"),
    )

    def __repr__(self):
        return (
            f"<RollNumberTemplate(department_id={self.department_id}, "
            f"academic_year_id={self.academic_year_id})>"
        )
