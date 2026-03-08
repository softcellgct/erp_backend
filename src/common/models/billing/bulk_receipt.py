from uuid import UUID
from decimal import Decimal
from datetime import datetime

from components.db.base_model import Base
from sqlalchemy import (
    ForeignKey,
    String,
    Numeric,
    DateTime,
    Text,
    Enum as SAEnum,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.models.billing.fee_structure import PayerTypeEnum


class BulkReceipt(Base):
    """
    Represents a bulk payment received from a single payer (e.g. government)
    covering multiple students at once.
    """
    __tablename__ = "bulk_receipts"

    institution_id: Mapped[UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    payer_type: Mapped[PayerTypeEnum] = mapped_column(
        SAEnum(PayerTypeEnum, name="payer_type_enum", values_callable=lambda obj: [e.value for e in obj], create_constraint=False),
        default=PayerTypeEnum.GOVERNMENT,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reference_number: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="processed", nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    items: Mapped[list["BulkReceiptItem"]] = relationship(
        "BulkReceiptItem", back_populates="bulk_receipt",
        cascade="all, delete-orphan", lazy="selectin"
    )
    institution = relationship("Institution", lazy="selectin")
    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_bulk_receipt_amount_positive"),
    )

    def __repr__(self):
        return (
            f"<BulkReceipt(id={self.id}, ref='{self.reference_number}', "
            f"amount={self.amount}, payer={self.payer_type.value})>"
        )


class BulkReceiptItem(Base):
    """
    Individual line item within a bulk receipt, linking a portion of the
    bulk payment to a specific student's invoice.
    """
    __tablename__ = "bulk_receipt_items"

    bulk_receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("bulk_receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Relationships
    bulk_receipt: Mapped["BulkReceipt"] = relationship(
        "BulkReceipt", back_populates="items", lazy="selectin"
    )
    invoice = relationship("Invoice", lazy="selectin")
    student = relationship("AdmissionStudent", lazy="selectin")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_bulk_receipt_item_amount_positive"),
    )

    def __repr__(self):
        return (
            f"<BulkReceiptItem(id={self.id}, bulk_receipt_id={self.bulk_receipt_id}, "
            f"student_id={self.student_id}, amount={self.amount})>"
        )
