from uuid import UUID
from decimal import Decimal
import enum
from components.db.base_model import Base
from sqlalchemy import ForeignKey, String, Boolean, Numeric, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship


class ScholarshipTypeConfigEnum(str, enum.Enum):
    FG = "FG"                      # First Graduate
    SC_ST = "SC_ST"                # SC/ST Scholarship
    BC = "BC"                      # Backward Class
    MBC = "MBC"                    # Most Backward Class
    STAFF_REFERRAL = "STAFF_REFERRAL"  # Staff Referral Discount
    MERIT_BASED = "MERIT_BASED"    # Merit-based Scholarship
    NEED_BASED = "NEED_BASED"      # Need-based Scholarship
    CUSTOM = "CUSTOM"              # Custom/Other


class ScholarshipConfiguration(Base):
    """
    Configurable scholarship rules per institution.
    Stores the amount or percentage for each scholarship type.
    """
    __tablename__ = "scholarship_configurations"

    institution_id: Mapped[UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scholarship_type: Mapped[ScholarshipTypeConfigEnum] = mapped_column(
        SAEnum(ScholarshipTypeConfigEnum, name="scholarship_type_config_enum",
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    
    # Amount or percentage
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    
    # For fee head specific rules
    fee_head_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fee_heads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # For staff referrals specifically
    reduce_from_tuition: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Relationships
    institution = relationship("Institution", lazy="selectin")
    fee_head = relationship("FeeHead", lazy="selectin")

    def __repr__(self):
        return (
            f"<ScholarshipConfiguration(id={self.id}, institution_id={self.institution_id}, "
            f"type={self.scholarship_type.value})>"
        )


class StaffReferralConcession(Base):
    """
    Tracks staff referrals and the concession granted to referred students.
    Links staff member to student with automatic concession reduction.
    """
    __tablename__ = "staff_referral_concessions"

    staff_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
    
    # Concession amount
    concession_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )
    concession_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    
    # Applied to specific fee head
    fee_head_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fee_heads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Status tracking
    is_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applied_at: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ISO datetime
    
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Relationships
    staff = relationship("User", foreign_keys=[staff_id], lazy="selectin")
    student = relationship("AdmissionStudent", lazy="selectin")
    institution = relationship("Institution", lazy="selectin")
    fee_head = relationship("FeeHead", lazy="selectin")

    def __repr__(self):
        return (
            f"<StaffReferralConcession(id={self.id}, staff_id={self.staff_id}, "
            f"student_id={self.student_id}, amount={self.concession_amount})>"
        )
