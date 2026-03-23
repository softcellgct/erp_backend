from datetime import datetime
from decimal import Decimal
from uuid import UUID

from components.db.base_model import Base
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.models.billing.fee_structure import PayerTypeEnum


class MultiReceipt(Base):
    """
    Consolidated receipt that applies one payment run across multiple students.
    """

    __tablename__ = "multi_receipts"

    institution_id: Mapped[UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fee_head_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    fee_sub_head_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fee_sub_heads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payer_type: Mapped[PayerTypeEnum] = mapped_column(
        SAEnum(
            PayerTypeEnum,
            name="payer_type_enum",
            values_callable=lambda obj: [e.value for e in obj],
            create_constraint=False,
        ),
        default=PayerTypeEnum.GOVERNMENT,
        nullable=False,
    )
    receipt_number: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    amount_per_student: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    student_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="processed")
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    items: Mapped[list["MultiReceiptItem"]] = relationship(
        "MultiReceiptItem",
        back_populates="multi_receipt",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    institution = relationship("Institution", lazy="selectin")
    fee_head = relationship("FeeHead", lazy="selectin")
    fee_sub_head = relationship("FeeSubHead", lazy="selectin")
    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")

    __table_args__ = (
        CheckConstraint("amount_per_student > 0", name="ck_multi_receipt_amount_per_student_positive"),
        CheckConstraint("total_amount > 0", name="ck_multi_receipt_total_amount_positive"),
        CheckConstraint("student_count >= 0", name="ck_multi_receipt_student_count_non_negative"),
    )


class MultiReceiptItem(Base):
    __tablename__ = "multi_receipt_items"

    multi_receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("multi_receipts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    demand_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("demand_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    invoice_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    demanded_amount_before: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    demanded_amount_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    multi_receipt: Mapped["MultiReceipt"] = relationship(
        "MultiReceipt", back_populates="items", lazy="selectin"
    )
    student = relationship("AdmissionStudent", lazy="selectin")
    demand_item = relationship("DemandItem", lazy="selectin")
    invoice = relationship("Invoice", lazy="selectin")
    payment = relationship("Payment", lazy="selectin")

    __table_args__ = (
        CheckConstraint("paid_amount >= 0", name="ck_multi_receipt_item_paid_non_negative"),
        CheckConstraint("demanded_amount_before >= 0", name="ck_multi_receipt_item_before_non_negative"),
        CheckConstraint("demanded_amount_after >= 0", name="ck_multi_receipt_item_after_non_negative"),
    )
