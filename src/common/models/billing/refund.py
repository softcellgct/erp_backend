import enum
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from components.db.base_model import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Numeric,
    Text,
    Enum as SAEnum,
    JSON,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class RefundStatusEnum(str, enum.Enum):
    INITIATED = "INITIATED"
    APPROVED = "APPROVED"
    PROCESSED = "PROCESSED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class RefundMethodEnum(str, enum.Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    UPI = "UPI"
    CHEQUE = "CHEQUE"


class Refund(Base):
    __tablename__ = "refunds"

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
    original_payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    original_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cancellation_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    refund_method: Mapped[RefundMethodEnum | None] = mapped_column(
        SAEnum(RefundMethodEnum, name="refund_method_enum",
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
    )
    refund_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)

    cancellation_receipt_number: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )
    refund_receipt_number: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )

    status: Mapped[RefundStatusEnum] = mapped_column(
        SAEnum(RefundStatusEnum, name="refund_status_enum",
               values_callable=lambda obj: [e.value for e in obj]),
        default=RefundStatusEnum.INITIATED,
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    initiated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    student = relationship("AdmissionStudent", lazy="selectin")
    institution = relationship("Institution", lazy="selectin")
    original_payment = relationship("Payment", lazy="selectin")
    original_invoice = relationship("Invoice", lazy="selectin")
    initiator = relationship("User", foreign_keys=[initiated_by], lazy="selectin")
    approver = relationship("User", foreign_keys=[approved_by], lazy="selectin")

    __table_args__ = (
        CheckConstraint("original_amount >= 0", name="ck_refund_original_amount"),
        CheckConstraint("cancellation_fee >= 0", name="ck_refund_cancellation_fee"),
        CheckConstraint("refund_amount >= 0", name="ck_refund_amount"),
    )

    def __repr__(self):
        return (
            f"<Refund(id={self.id}, student_id={self.student_id}, "
            f"refund={self.refund_amount}, status={self.status.value})>"
        )
