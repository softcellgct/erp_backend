import enum
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from components.db.base_model import Base
from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Boolean,
    Numeric,
    Text,
    Enum as SAEnum,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class ScholarshipTypeEnum(str, enum.Enum):
    FG = "FG"          # First Graduate
    SC_ST = "SC_ST"    # SC/ST Scholarship
    BC = "BC"          # Backward Class
    MBC = "MBC"        # Most Backward Class
    CUSTOM = "CUSTOM"  # Any other scholarship


class CertificateStatusEnum(str, enum.Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class StudentScholarship(Base):
    __tablename__ = "student_scholarships"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    institution_id: Mapped[UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fee_structure_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fee_structures.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    academic_year_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("academic_years.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    scholarship_type: Mapped[ScholarshipTypeEnum] = mapped_column(
        SAEnum(ScholarshipTypeEnum, name="scholarship_type_enum",
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    certificate_status: Mapped[CertificateStatusEnum] = mapped_column(
        SAEnum(CertificateStatusEnum, name="certificate_status_enum",
               values_callable=lambda obj: [e.value for e in obj]),
        default=CertificateStatusEnum.NOT_SUBMITTED,
        nullable=False,
    )
    certificate_file: Mapped[str | None] = mapped_column(String(500), nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    amount_received: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    amount_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    receipt_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"), nullable=True
    )

    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    student = relationship("AdmissionStudent", lazy="selectin")
    institution = relationship("Institution", lazy="selectin")
    fee_structure = relationship("FeeStructure", lazy="selectin")
    academic_year = relationship("AcademicYear", lazy="selectin")
    reviewer = relationship("User", foreign_keys=[reviewed_by], lazy="selectin")
    receipt = relationship("Payment", lazy="selectin")

    def __repr__(self):
        return (
            f"<StudentScholarship(id={self.id}, student_id={self.student_id}, "
            f"type={self.scholarship_type.value}, status={self.certificate_status.value})>"
        )
