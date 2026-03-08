from common.models.admission.admission_entry import AdmissionStatusEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Enum as SQLEnum,
    func,
)
from components.db.base_model import Base
from uuid import UUID
from datetime import datetime
import enum

# Import from existing models
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.models.master.institution import Institution, Department


class VisitorType(str, enum.Enum):
    """Enum for visitor types"""

    GENERAL = "general"
    VENDOR = "vendor"
    ADMISSION = "admission"


class VisitStatus(str, enum.Enum):
    """Enum for visit status"""

    PENDING = "pending"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"


class ReferenceType(str, enum.Enum):
    """Enum for reference types"""

    CONSULTANCY = "consultancy"
    STAFF = "staff"
    STUDENT = "student"
    OTHER = "other"


class PersonType(Base):
    """
    Model to store person types (e.g., Student, Faculty, Staff, etc.)
    that visitors can meet during their visit
    """

    __tablename__ = "person_types"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    visitors: Mapped[list["Visitor"]] = relationship(
        "Visitor", back_populates="person_type", lazy="selectin"
    )


class Visitor(Base):
    """
    Model to store visitor information and generate visitor passes
    """

    __tablename__ = "visitors"

    # Basic Information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_number: Mapped[str] = mapped_column(String(20), nullable=False)
    members_count: Mapped[int] = mapped_column(nullable=False, default=1)

    # Visitor Type (General/Vendor/Admission)
    visitor_type: Mapped[VisitorType] = mapped_column(
        SQLEnum(VisitorType, native_enum=False),
        nullable=False,
        default=VisitorType.GENERAL,
    )

    # Institution/Department/Person Details
    institution_id: Mapped[UUID] = mapped_column(
        ForeignKey("institutions.id"), nullable=False, index=True
    )
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id"), nullable=False, index=True
    )
    person_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("person_types.id"), nullable=False, index=True
    )
    person_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Purpose and Details
    purpose_of_visit: Mapped[str] = mapped_column(Text, nullable=False)

    # Vehicle Information
    has_vehicle: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vehicle_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Photo/Document Storage
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Pass Information
    pass_number: Mapped[str | None] = mapped_column(
        String(50), unique=True, nullable=True
    )
    pass_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=func.now()
    )

    # Visit Status and Timestamps
    visit_status: Mapped[VisitStatus] = mapped_column(
        SQLEnum(VisitStatus, native_enum=False),
        nullable=False,
        default=VisitStatus.PENDING,
    )
    check_in_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=False, default=func.now()
    )
    check_out_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Additional Information
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    institution: Mapped["Institution"] = relationship(
        "Institution", foreign_keys=[institution_id], lazy="selectin"
    )
    department: Mapped["Department"] = relationship(
        "Department", foreign_keys=[department_id], lazy="selectin"
    )
    person_type: Mapped["PersonType"] = relationship(
        "PersonType", back_populates="visitors", foreign_keys=[person_type_id], lazy="selectin"
    )


class ConsultancyReference(Base):
    """
    Model to link students referred by consultancies
    """

    __tablename__ = "consultancy_references"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_students.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    consultancy_id: Mapped[UUID] = mapped_column(
        ForeignKey("consultancies.id"), nullable=False, index=True
    )

    reference_staff_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_staff_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_staff_3: Mapped[str | None] = mapped_column(String(255), nullable=True)


class StaffReference(Base):
    __tablename__ = "staff_references"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_students.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_members.id"), nullable=True, index=True
    )


class StudentReference(Base):
    __tablename__ = "student_references"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_students.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    roll_number: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_number: Mapped[str] = mapped_column(String(20), nullable=False)


class OtherReference(Base):
    __tablename__ = "other_references"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_students.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    description: Mapped[str] = mapped_column(String(255), nullable=False)

