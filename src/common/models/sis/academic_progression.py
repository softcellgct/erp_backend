"""Academic progression history.

Every academic transition a student goes through — initial admission, an annual
promotion, a lateral entry, or graduation — is recorded as one immutable row in
``sis_student_academic_history``.  The student's *current* position is
denormalised onto :class:`SISStudentProfile` (current_year_of_study /
current_semester / current_academic_year_id / academic_status); this table is the
full audit trail and the source of truth for transcripts, attendance, exams,
hall tickets, semester registration and alumni tracking.

CRITICAL: never overwrite a student's year/semester without first appending a
record here.  Prior rows are not rewritten (only ``effective_to`` is closed when
a newer record supersedes them).
"""
import enum

from components.db.base_model import Base
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UUID,
)
from sqlalchemy.orm import relationship

from common.models.sis.sis_student import AcademicStatusEnum, EntryModeEnum


class PromotionTypeEnum(str, enum.Enum):
    """The kind of transition a history record represents."""
    ADMISSION = "ADMISSION"
    PROMOTION = "PROMOTION"
    LATERAL_ENTRY = "LATERAL_ENTRY"
    GRADUATION = "GRADUATION"


class SISStudentAcademicHistory(Base):
    """One immutable record per academic transition for a student."""
    __tablename__ = "sis_student_academic_history"

    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Program snapshot at the time of the transition (denormalised for history).
    institution_id = Column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=True, index=True
    )
    department_id = Column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True, index=True
    )
    course_id = Column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=True, index=True
    )
    academic_year_id = Column(
        UUID(as_uuid=True), ForeignKey("academic_years.id"), nullable=True, index=True
    )

    # Position resulting from this transition.
    semester = Column(Integer, nullable=True)
    year_of_study = Column(Integer, nullable=True)
    section = Column(String(50), nullable=True)
    roll_number = Column(String(50), nullable=True, index=True)
    register_number = Column(String(100), nullable=True, index=True)

    promotion_type = Column(
        Enum(PromotionTypeEnum, name="promotion_type_enum"), nullable=False
    )
    entry_mode = Column(Enum(EntryModeEnum, name="entry_mode_enum"), nullable=True)
    status = Column(Enum(AcademicStatusEnum, name="academic_status_enum"), nullable=True)

    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    remarks = Column(Text, nullable=True)

    # Relationships (lazy="selectin" — load names without N+1 on lists).
    student = relationship(
        "AdmissionStudent", lazy="selectin", foreign_keys=[student_id]
    )
    institution = relationship(
        "Institution", lazy="selectin", foreign_keys=[institution_id]
    )
    department = relationship(
        "Department", lazy="selectin", foreign_keys=[department_id]
    )
    course = relationship("Course", lazy="selectin", foreign_keys=[course_id])
    academic_year = relationship(
        "AcademicYear", lazy="selectin", foreign_keys=[academic_year_id]
    )

    def __repr__(self):
        return (
            f"<SISStudentAcademicHistory(student_id={self.student_id}, "
            f"type={self.promotion_type}, year={self.year_of_study}, "
            f"sem={self.semester})>"
        )
