import enum
from uuid import UUID
import uuid
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from common.models.master.academic_year import AcademicYear
    from common.models.billing.cash_counter import CashCounter
from components.db.base_model import Base
from sqlalchemy import (
    ForeignKey,
    String,
    Float,
    Date,
    DateTime,
    Enum as SAEnum,
    Text,
    # UniqueConstraint,  # keep commented if needed later
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class FeeHead(Base):
    __tablename__ = "fee_heads"

    institution_id: Mapped[UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # Link fee head to an academic year (nullable for migration safety)
    academic_year_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=True, index=True
    )
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", lazy="selectin")
    # Relationships
    line_items: Mapped[list["InvoiceLineItem"]] = relationship(
        "InvoiceLineItem", back_populates="fee_head", lazy="selectin"
    )


class PaymentStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    PARTIAL = "partial"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class Invoice(Base):
    __tablename__ = "invoices"

    institution_id: Mapped[UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("admission_students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    amount: Mapped[float] = mapped_column(Float(precision=2), nullable=False)
    paid_amount: Mapped[float] = mapped_column(Float(precision=2), default=0.0)
    balance_due: Mapped[float] = mapped_column(Float(precision=2), default=0.0)
    status: Mapped[PaymentStatusEnum] = mapped_column(SAEnum(PaymentStatusEnum), default=PaymentStatusEnum.PENDING, nullable=False)
    issue_date: Mapped[Date] = mapped_column(Date, nullable=False)
    due_date: Mapped[Date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    line_items: Mapped[list["InvoiceLineItem"]] = relationship(
        "InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )
    status_history: Mapped[list["InvoiceStatusHistory"]] = relationship(
        "InvoiceStatusHistory", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self):
        return f"<Invoice(id={self.id}, invoice_number='{self.invoice_number}', amount={self.amount}, status='{self.status.value}')>"


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    fee_head_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float(precision=2), nullable=False)
    discount_amount: Mapped[float | None] = mapped_column(Float(precision=2), default=0.0)
    tax_amount: Mapped[float | None] = mapped_column(Float(precision=2), default=0.0)
    net_amount: Mapped[float] = mapped_column(Float(precision=2), nullable=False)

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="line_items")
    fee_head: Mapped["FeeHead"] = relationship("FeeHead", back_populates="line_items", lazy="selectin")

    def __repr__(self):
        return f"<InvoiceLineItem(id={self.id}, invoice_id={self.invoice_id}, amount={self.amount})>"


class Payment(Base):
    __tablename__ = "payments"

    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    cash_counter_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("cash_counters.id", ondelete="SET NULL"), nullable=True)
    amount: Mapped[float] = mapped_column(Float(precision=2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    payment_date: Mapped[DateTime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    receipt_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")
    cash_counter: Mapped["CashCounter"] = relationship("CashCounter")

    def __repr__(self):
        return f"<Payment(id={self.id}, invoice_id={self.invoice_id}, amount={self.amount})>"


class InvoiceStatusHistory(Base):
    __tablename__ = "invoice_status_history"

    invoice_id: Mapped[UUID] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status: Mapped[Optional[PaymentStatusEnum]] = mapped_column(SAEnum(PaymentStatusEnum), nullable=True)
    to_status: Mapped[PaymentStatusEnum] = mapped_column(SAEnum(PaymentStatusEnum), nullable=False)
    changed_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    changed_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="status_history")

    def __repr__(self):
        return f"<InvoiceStatusHistory(id={self.id}, invoice_id={self.invoice_id}, from='{self.from_status}', to='{self.to_status}')>"


class ApplicationTransaction(Base):
    __tablename__ = "application_transactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    
    # Student Details (Captured at time of payment)
    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    student_mobile: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Configuration Links
    academic_year_id: Mapped[UUID] = mapped_column(ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Payment Details
    amount: Mapped[float] = mapped_column(Float(precision=2), nullable=False)
    payment_mode: Mapped[str] = mapped_column(String(50), nullable=False) # Cash, UPI, Card
    transaction_date: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Counter & Staff
    cash_counter_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("cash_counters.id", ondelete="SET NULL"), nullable=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Receipt Info
    receipt_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    payment_status: Mapped[PaymentStatusEnum] = mapped_column(SAEnum(PaymentStatusEnum), default=PaymentStatusEnum.PAID, nullable=False)
    
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear")
    department: Mapped["Department"] = relationship("Department") # Assuming Department is imported or available via string
    cash_counter: Mapped["CashCounter"] = relationship("CashCounter")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<ApplicationTransaction(id={self.id}, receipt='{self.receipt_number}', student='{self.student_name}')>"
    
