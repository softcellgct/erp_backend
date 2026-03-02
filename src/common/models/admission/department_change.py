import enum
from components.db.base_model import Base
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    UUID,
    func,
)
from sqlalchemy.orm import relationship


class DepartmentChangeStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DepartmentChangeRequest(Base):
    """
    Track department change requests for admitted students.
    """

    __tablename__ = "department_change_requests"

    # Student Reference
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Department References
    current_department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    requested_department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Request details
    reason = Column(Text, nullable=False)
    status = Column(
        Enum(DepartmentChangeStatusEnum),
        default=DepartmentChangeStatusEnum.PENDING,
        nullable=False,
        index=True,
    )

    # Tracking — proper FK to users
    requested_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=False,
        index=True,
    )
    requested_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Approval/Rejection
    reviewed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", use_alter=True, deferrable=True, initially="DEFERRED"),
        nullable=True,
        index=True,
    )
    reviewed_at = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)

    # Metadata
    is_active = Column(Boolean, default=True, nullable=False)
    # created_at / updated_at inherited from Base

    # Relationships
    student = relationship("AdmissionStudent", back_populates="department_change_requests", lazy="selectin")
    current_department = relationship(
        "Department",
        foreign_keys=[current_department_id],
        backref="students_changing_from",
        lazy="selectin",
    )
    requested_department = relationship(
        "Department",
        foreign_keys=[requested_department_id],
        backref="students_changing_to",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<DepartmentChangeRequest(student_id={self.student_id}, status={self.status})>"
