from uuid import UUID
from datetime import datetime
from components.db.base_model import Base
from sqlalchemy import ForeignKey, String, DateTime, Boolean
from sqlalchemy import JSON, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship


class DemandBatch(Base):
    __tablename__ = "demand_batches"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    admission_year_id: Mapped[UUID | None] = mapped_column(ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_structure_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_structures.id", ondelete="SET NULL"), nullable=True, index=True)
    filters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    demands = relationship("DemandItem", back_populates="batch", cascade="all, delete-orphan", lazy="selectin")


class DemandItem(Base):
    __tablename__ = "demand_items"

    batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("demand_batches.id", ondelete="CASCADE"), nullable=True, index=True)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("admission_students.id", ondelete="CASCADE"), nullable=False, index=True)
    fee_structure_id: Mapped[UUID] = mapped_column(ForeignKey("fee_structures.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_structure_item_id: Mapped[UUID] = mapped_column(ForeignKey("fee_structure_items.id", ondelete="SET NULL"), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12,2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    invoice_id: Mapped[UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fee_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_sub_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_sub_heads.id", ondelete="SET NULL"), nullable=True, index=True)

    batch = relationship("DemandBatch", back_populates="demands", lazy="selectin")
