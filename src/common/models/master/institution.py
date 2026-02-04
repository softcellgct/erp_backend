from uuid import UUID
from components.db.base_model import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Boolean, ForeignKey, Integer, String, JSON

class Institution(Base):
    __tablename__ = "institutions"
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    departments: Mapped[list["Department"]] = relationship(
        back_populates="institution", lazy="selectin"
    )
    # Using string forward reference to avoid circular import issues at module level
    academic_years: Mapped[list["AcademicYear"]] = relationship(
        "AcademicYear", back_populates="institution"
    )


class Department(Base):
    __tablename__ = "departments"
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    institution: Mapped["Institution"] = relationship(
        back_populates="departments", lazy="selectin"
    )
    courses: Mapped[list["Course"]] = relationship(back_populates="department")


class Course(Base):
    __tablename__ = "courses"
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    short_name: Mapped[str | None] = mapped_column(
        String(50), unique=True, index=True, nullable=True
    )  # Short name / abbreviation
    level: Mapped[str] = mapped_column(
        String(10), nullable=False, default="UG", server_default="UG"
    )  # "UG" or "PG"
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    course_duration_years: Mapped[int] = mapped_column(Integer, nullable=False)
    total_semesters: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    department: Mapped["Department"] = relationship(back_populates="courses")
    classes: Mapped[list["Class"]] = relationship(back_populates="course")


class Class(Base):
    __tablename__ = "classes"
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    course_id: Mapped[UUID] = mapped_column(ForeignKey("courses.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    course: Mapped["Course"] = relationship(back_populates="classes")


class Hostel(Base):
    __tablename__ = "hostels"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # relationships
    # rooms and structures will reference this table
