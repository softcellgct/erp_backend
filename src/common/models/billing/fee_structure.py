from uuid import UUID
from decimal import Decimal
from components.db.base_model import Base
from sqlalchemy import ForeignKey, String, Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship



from sqlalchemy import JSON, Integer, Date, Enum as SAEnum
import enum

from common.models.master.admission.admission_type import AdmissionType
from common.models.master.admission.quota import Quota
from common.models.master.annual_task import AcademicYear, SemesterPeriod
from common.models.billing.financial_year import FinancialYear
from common.models.master.institution import Course, Department

class GenderEnum(str, enum.Enum):
    MALE = "Male"
    FEMALE = "Female"
    TRANSGENDER = "Transgender"
    ALL = "All"

class FineCalculationEnum(str, enum.Enum):
    NOT_APPLICABLE = "Fine not applicable"
    FIXED_AMOUNT = "Fixed amount"
    PERCENTAGE = "Percentage"
    PER_DAY = "Per day"

class FeeStructure(Base):
    __tablename__ = "fee_structures"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    financial_year_id: Mapped[UUID] = mapped_column(ForeignKey("financial_years.id", ondelete="SET NULL"), nullable=True, index=True)
    admission_year_id: Mapped[UUID] = mapped_column(ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # New Fields based on UI
    semester_period_id: Mapped[UUID | None] = mapped_column(ForeignKey("semester_periods.id", ondelete="SET NULL"), nullable=True, index=True)  # Fee Period
    admission_type_id: Mapped[UUID | None] = mapped_column(ForeignKey("admission_types.id", ondelete="SET NULL"), nullable=True, index=True)
    quota_id: Mapped[UUID | None] = mapped_column(ForeignKey("quotas.id", ondelete="SET NULL"), nullable=True, index=True)
    gender: Mapped[GenderEnum] = mapped_column(SAEnum(GenderEnum, name="gender_enum_v2", values_callable=lambda obj: [e.value for e in obj]), default=GenderEnum.ALL, nullable=False)
    
    degree_id: Mapped[UUID | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)
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
    
    # New relationships
    semester_period = relationship("SemesterPeriod", lazy="selectin")
    admission_type = relationship("AdmissionType", lazy="selectin")
    quota = relationship("Quota", lazy="selectin")
    degree = relationship("Course", lazy="selectin")
    department = relationship("Department", lazy="selectin")


class FeeStructureItem(Base):
    __tablename__ = "fee_structure_items"

    fee_structure_id: Mapped[UUID] = mapped_column(ForeignKey("fee_structures.id", ondelete="CASCADE"), nullable=False, index=True)
    fee_head_id: Mapped[UUID | None] = mapped_column(ForeignKey("fee_heads.id", ondelete="SET NULL"), nullable=True, index=True)
    fee_sub_head_id: Mapped[UUID] = mapped_column(ForeignKey("fee_sub_heads.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    
    # New fields for item details
    last_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    fine_calculation: Mapped[FineCalculationEnum] = mapped_column(SAEnum(FineCalculationEnum, name="fine_calculation_enum_v2", values_callable=lambda obj: [e.value for e in obj]), default=FineCalculationEnum.NOT_APPLICABLE, nullable=False)
    fine_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=0)
    fine_ceiling: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True, default=0)
    
    amount_by_year: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    order: Mapped[int] = mapped_column(nullable=True)

    # Relationships
    fee_structure = relationship("FeeStructure", back_populates="items", lazy="selectin")
    fee_head = relationship("FeeHead", lazy="selectin")
    fee_sub_head = relationship("FeeSubHead", back_populates="structure_items", lazy="selectin")

