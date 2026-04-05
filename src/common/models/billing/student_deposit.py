import enum
from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from common.models.admission.admission_entry import AdmissionStudent
    from common.models.master.institution import Institution

from components.db.base_model import Base
from sqlalchemy import (
    ForeignKey,
    String,
    Numeric,
    DateTime,
    Text,
    CheckConstraint,
    func,
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class DepositStatusEnum(str, enum.Enum):
    ACTIVE = "ACTIVE"
    FULLY_USED = "FULLY_USED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    FULLY_REFUNDED = "FULLY_REFUNDED"


class StudentDeposit(Base):
    """
    Tracks advance/deposit payments made by students before final admission.
    
    Consolidates all deposits per student into a single record with balance tracking.
    Automatically applied as credits to invoices when generated.
    """
    __tablename__ = "student_deposits"

    # Foreign Keys
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

    # Denormalized application number for quick lookup
    application_number: Mapped[str] = mapped_column(String(100), nullable=True, index=True)

    # Amount tracking
    total_deposited: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )
    used_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )
    refunds_issued: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    # Status tracking
    status: Mapped[DepositStatusEnum] = mapped_column(
        default=DepositStatusEnum.ACTIVE,
        nullable=False,
    )

    # Audit trail
    deposit_receipts: Mapped[dict] = mapped_column(
        JSON,
        nullable=True,
        comment="List of {date, amount, payment_method, receipt_number, notes}"
    )
    adjustment_history: Mapped[dict] = mapped_column(
        JSON,
        nullable=True,
        comment="List of {date, amount, invoice_id, applied_by}"
    )

    # Metadata
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_modified_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    student: Mapped["AdmissionStudent"] = relationship(
        "AdmissionStudent",
        back_populates="deposits",
        lazy="selectin",
    )
    institution: Mapped["Institution"] = relationship(
        "Institution",
        lazy="selectin",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint("total_deposited >= 0", name="ck_total_deposited_non_negative"),
        CheckConstraint("used_amount >= 0", name="ck_used_amount_non_negative"),
        CheckConstraint("refunds_issued >= 0", name="ck_refunds_issued_non_negative"),
        CheckConstraint(
            "used_amount + refunds_issued <= total_deposited",
            name="ck_deposit_balance_valid"
        ),
        Index("idx_student_institution", "student_id", "institution_id"),
        Index("idx_application_institution", "application_number", "institution_id"),
    )

    @property
    def available_balance(self) -> Decimal:
        """Calculate available balance for new applications."""
        return self.total_deposited - self.used_amount - self.refunds_issued

    def __repr__(self):
        return (
            f"<StudentDeposit("
            f"id={self.id}, "
            f"student_id={self.student_id}, "
            f"total_deposited={self.total_deposited}, "
            f"used_amount={self.used_amount}, "
            f"available_balance={self.available_balance}"
            f")>"
        )
