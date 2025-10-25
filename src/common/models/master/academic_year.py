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

