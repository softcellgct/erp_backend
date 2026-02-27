from datetime import date
from uuid import UUID
from components.db.base_model import Base
from sqlalchemy import Date, ForeignKey, String, Boolean, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship


class FinancialYear(Base):
    __tablename__ = "financial_years"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships — lazy="select" to avoid loading ALL fee structures on every year fetch
    fee_structures = relationship("FeeStructure", back_populates="financial_year", lazy="select")

    __table_args__ = (
        CheckConstraint("start_date < end_date", name="ck_financial_year_start_lt_end"),
        UniqueConstraint("institution_id", "name", name="uq_institution_financial_year_name"),
    )

