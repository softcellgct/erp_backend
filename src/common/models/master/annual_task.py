from datetime import date
from uuid import UUID
from typing import TYPE_CHECKING, Optional, List
from components.db.base_model import Base
from sqlalchemy import String, Date, Boolean, ForeignKey, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from common.models.master.institution import Course, Institution

class AcademicYear(Base):
    __tablename__ = "academic_years"
    
    year_name: Mapped[str] = mapped_column(String(50), nullable=False)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[bool] = mapped_column(Boolean, default=True) # General active status
    admission_active: Mapped[bool] = mapped_column(Boolean, default=False) # For admission purposes
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"))
    
    # Relationships
    institution: Mapped["Institution"] = relationship("Institution", back_populates="academic_years")
    
    available_courses: Mapped[List["AcademicYearCourse"]] = relationship(
        "AcademicYearCourse", back_populates="academic_year", cascade="all, delete-orphan"
    )
    
    semester_periods: Mapped[List["SemesterPeriod"]] = relationship(
        "SemesterPeriod", back_populates="academic_year", cascade="all, delete-orphan"
    )

class AcademicYearCourse(Base):
    __tablename__ = "academic_year_courses"
    
    academic_year_id: Mapped[UUID] = mapped_column(ForeignKey("academic_years.id"), nullable=False)
    course_id: Mapped[UUID] = mapped_column(ForeignKey("courses.id"), nullable=False)
    application_fee: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", back_populates="available_courses")
    course: Mapped["Course"] = relationship("Course") 

class SemesterPeriod(Base):
    __tablename__ = "semester_periods"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    short_name: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="Semester") # Semester / Trimester / Year
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    academic_year_id: Mapped[UUID] = mapped_column(ForeignKey("academic_years.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", back_populates="semester_periods")
