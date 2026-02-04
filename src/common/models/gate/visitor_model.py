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
        "Visitor", back_populates="person_type"
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
        ForeignKey("institutions.id"), nullable=False
    )
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id"), nullable=False
    )
    person_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("person_types.id"), nullable=False
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
        "Institution", foreign_keys=[institution_id]
    )
    department: Mapped["Department"] = relationship(
        "Department", foreign_keys=[department_id]
    )
    person_type: Mapped["PersonType"] = relationship(
        "PersonType", back_populates="visitors", foreign_keys=[person_type_id]
    )


class VendorVisitor(Base):
    """
    Model to store vendor-specific visitor information
    Extends visitor information with vendor-specific details
    """

    __tablename__ = "vendor_visitors"

    visitor_id: Mapped[UUID] = mapped_column(
        ForeignKey("visitors.id"), nullable=False, unique=True
    )

    # Vendor-specific Information
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_contact: Mapped[str | None] = mapped_column(String(20), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Material/Items Information
    carrying_materials: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    material_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    visitor: Mapped["Visitor"] = relationship("Visitor", foreign_keys=[visitor_id])



class AdmissionVisitor(Base):
    """
    Model to store admission-specific visitor information
    For prospective students and their guardians
    """

    __tablename__ = "admission_visitors"

    gate_pass_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Prospective Student Information
    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile_number: Mapped[str] = mapped_column(String, nullable=False)
    parent_or_guardian_name: Mapped[str | None] = mapped_column(
        String(255), nullable=False
    )
    aadhar_number: Mapped[str] = mapped_column(String, nullable=False)
    native_place: Mapped[str] = mapped_column(String(255), nullable=False)
    image_url : Mapped[str] = mapped_column(String,nullable=False)
    reference_type: Mapped[ReferenceType] = mapped_column(
        SQLEnum(ReferenceType, native_enum=False), nullable=False
    )
    vehicle: Mapped[bool] = mapped_column(default=False, nullable=False)

    vehicle_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    institution_id: Mapped[UUID] = mapped_column(
        ForeignKey("institutions.id"), nullable=False
    )
    status: Mapped[AdmissionStatusEnum] = mapped_column(
        SQLEnum(AdmissionStatusEnum, native_enum=False),
        default=AdmissionStatusEnum.APPLIED,
        nullable=False,
    )

    # Relationship
    institution: Mapped["Institution"] = relationship(
        "Institution", foreign_keys=[institution_id]
    )
    consultancy_reference: Mapped["ConsultancyReference"] = relationship(
        "ConsultancyReference", uselist=False
    )
    staff_reference: Mapped["StaffReference"] = relationship(uselist=False)
    student_reference: Mapped["StudentReference"] = relationship(uselist=False)
    other_reference: Mapped["OtherReference"] = relationship(uselist=False)


class ConsultancyReference(Base):
    """
    Model to link visitors referred by consultancies
    """

    __tablename__ = "consultancy_references"

    admission_visitor_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_visitors.id"), nullable=False, unique=True
    )

    consultancy_id: Mapped[UUID] = mapped_column(
        ForeignKey("consultancies.id"), nullable=False
    )

    reference_staff_1: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_staff_2: Mapped[str] = mapped_column(String(255), nullable=True)
    reference_staff_3: Mapped[str] = mapped_column(String(255), nullable=True)
    contact_number: Mapped[str] = mapped_column(String(20), nullable=False)
    # Relationships
    # visitor: Mapped["Visitor"] = relationship(
    #     "Visitor", foreign_keys=[admission_visitor_id]
    # )



class StaffReference(Base):
    __tablename__ = "staff_references"

    reference_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_visitors.id", ondelete="CASCADE"), primary_key=True
    )

    staff_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_number: Mapped[str] = mapped_column(String(20), nullable=False)

class StudentReference(Base):
    __tablename__ = "student_references"

    reference_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_visitors.id", ondelete="CASCADE"), primary_key=True
    )

    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    course: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_number: Mapped[str] = mapped_column(String(20), nullable=False)


class OtherReference(Base):
    __tablename__ = "other_references"

    reference_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_visitors.id", ondelete="CASCADE"), primary_key=True
    )

    description: Mapped[str] = mapped_column(String(255), nullable=False)