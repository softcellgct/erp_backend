from datetime import date
from uuid import UUID
from components.db.base_model import Base
from sqlalchemy import Date, ForeignKey, String, Boolean
from sqlalchemy.orm import Mapped,relationship,mapped_column

class AcademicYear(Base):
    __tablename__ = "academic_years"

    year_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    admission_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"))

    institution = relationship("Institution", back_populates="academic_years", lazy="selectin")
    semester_periods = relationship(
        "SemesterPeriod", back_populates="academic_year", cascade="all, delete-orphan", lazy="selectin"
    )
    financial_years = relationship(
        "FinancialYear", back_populates="academic_year", cascade="all, delete-orphan", lazy="selectin"
    )


class SemesterPeriod(Base):
    __tablename__ = "semester_periods"

    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "Odd Sem - 2010"
    short_name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "Odd Sem"
    type: Mapped[str] = mapped_column(String(20), default="Semester", nullable=False)  # e.g., "Semester" from dropdown
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Checkbox for "Is Sem-period active"

    # Foreign key to AcademicYear, ensuring cascade delete if AcadYear is removed
    academic_year_id: Mapped[UUID] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )

    # Relationship back to AcademicYear for easy querying (e.g., semester_periods = academic_year.semester_periods)
    academic_year = relationship(
        "AcademicYear", back_populates="semester_periods", lazy="selectin"
    )