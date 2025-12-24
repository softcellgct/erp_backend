from uuid import UUID
from decimal import Decimal
from components.db.base_model import Base
from sqlalchemy import ForeignKey, String, Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship


from sqlalchemy import JSON, Integer


class FeeStructure(Base):
    __tablename__ = "fee_structures"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year_id: Mapped[UUID] = mapped_column(ForeignKey("financial_years.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_year_id: Mapped[UUID] = mapped_column(ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True, index=True)
    degree_id: Mapped[UUID | None] = mapped_column(ForeignKey("degrees.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    course_duration_years: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    fg_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sc_st_scholarship: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    batch: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relationships
    items = relationship("FeeStructureItem", back_populates="fee_structure", cascade="all, delete-orphan", lazy="selectin")
    financial_year = relationship("FinancialYear", back_populates="fee_structures", lazy="selectin")
    admission_year = relationship("AcademicYear", lazy="selectin")


class FeeStructureItem(Base):
    __tablename__ = "fee_structure_items"

    fee_structure_id: Mapped[UUID] = mapped_column(ForeignKey("fee_structures.id", ondelete="CASCADE"), nullable=False, index=True)
    fee_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_sub_head_id: Mapped[UUID] = mapped_column(ForeignKey("fee_sub_heads.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    amount_by_year: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    order: Mapped[int] = mapped_column(nullable=True)

    # Relationships
    fee_structure = relationship("FeeStructure", back_populates="items", lazy="selectin")
    fee_head = relationship("FeeHead", lazy="selectin")
    fee_sub_head = relationship("FeeSubHead", back_populates="structure_items", lazy="selectin")
