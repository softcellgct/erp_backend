import enum
from datetime import datetime
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
)
from sqlalchemy.orm import relationship


class DepartmentChangeStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DepartmentChangeRequest(Base):
    """
    Model to track department change requests for admitted students.
    Students can request to change their department after admission.
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
    )

    requested_department_id = Column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Request details
    reason = Column(Text, nullable=False)  # Reason for department change
    status = Column(
        Enum(DepartmentChangeStatusEnum),
        default=DepartmentChangeStatusEnum.PENDING,
        nullable=False,
        index=True,
    )

    # Tracking
    requested_by = Column(
        UUID(as_uuid=True), nullable=False
    )  # User ID who created the request (staff/student)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Approval/Rejection
    reviewed_by = Column(UUID(as_uuid=True), nullable=True)  # Admin/Staff who reviewed
    reviewed_at = Column(DateTime, nullable=True)
    remarks = Column(Text, nullable=True)  # Admin remarks

    # Metadata
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    student = relationship("AdmissionStudent", back_populates="department_change_requests")
    current_department = relationship(
        "Department",
        foreign_keys=[current_department_id],
        backref="students_changing_from",
    )
    requested_department = relationship(
        "Department",
        foreign_keys=[requested_department_id],
        backref="students_changing_to",
    )

    def __repr__(self):
        return f"<DepartmentChangeRequest(student_id={self.student_id}, status={self.status})>"
