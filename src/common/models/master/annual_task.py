from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import TYPE_CHECKING, Optional, List
from components.db.base_model import Base
from sqlalchemy import String, Date, Boolean, CheckConstraint, ForeignKey, Numeric, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from common.models.master.institution import Course, Institution

class AcademicYear(Base):
    __tablename__ = "academic_years"
    
    year_name: Mapped[str] = mapped_column(String(50), nullable=False)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, default=True)
    admission_active: Mapped[bool] = mapped_column(Boolean, default=False)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"), index=True)
    
    # Relationships
    institution: Mapped["Institution"] = relationship("Institution", back_populates="academic_years", lazy="selectin")
    
    available_courses: Mapped[List["AcademicYearCourse"]] = relationship(
        "AcademicYearCourse", back_populates="academic_year", cascade="all, delete-orphan", lazy="selectin"
    )
    
    semester_periods: Mapped[List["SemesterPeriod"]] = relationship(
        "SemesterPeriod", back_populates="academic_year", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("from_date < to_date", name="ck_academic_year_dates"),
        UniqueConstraint("institution_id", "year_name", name="uq_institution_year_name"),
    )

class AcademicYearCourse(Base):
    __tablename__ = "academic_year_courses"
    
    academic_year_id: Mapped[UUID] = mapped_column(ForeignKey("academic_years.id"), nullable=False, index=True)
    course_id: Mapped[UUID] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    application_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", back_populates="available_courses", lazy="selectin")
    course: Mapped["Course"] = relationship("Course", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("academic_year_id", "course_id", name="uq_academic_year_course"),
        CheckConstraint("application_fee >= 0", name="ck_application_fee_non_negative"),
    )

class SemesterPeriod(Base):
    __tablename__ = "semester_periods"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    short_name: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="Semester")
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    academic_year_id: Mapped[UUID] = mapped_column(ForeignKey("academic_years.id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", back_populates="semester_periods", lazy="selectin")

    __table_args__ = (
        CheckConstraint("from_date < to_date", name="ck_semester_period_dates"),
    )
